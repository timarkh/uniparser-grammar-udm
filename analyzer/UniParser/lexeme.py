import copy
import json
import re
import grammar
import wordform

rxStemParts = re.compile('(\\.|[^.]+)')


def check_compatibility(sublex, flex, errorHandler=None):
    """
    Check if the given SubLexeme and the given Inflexion
    are compatible.
    """
    if flex.stemNum is not None and len(sublex.numStem & flex.stemNum) <= 0 and\
            sublex.lex.num_stems() > 1:
        return False
    for rxTest in flex.regexTests:
        if not check_for_regex(sublex, rxTest, errorHandler):
            return False
    return True


def check_for_regex(item, rxTest, errorHandler=None, checkWordform=False):
    """
    Perform the given RegexTest against the given item (SubLexeme or Wordform).
    """
    if rxTest.field == 'stem' or rxTest.field == 'prev':
        if not rxTest.perform(item.stem):
            return False
    elif rxTest.field == 'paradigm':
        if errorHandler is not None:
            errorHandler.raise_error('Paradigm names cannot be subject to '
                                     'regex tests.')
        return False
    elif not checkWordform and rxTest.field in Lexeme.propertyFields:
        searchField = rxTest.field
        if searchField == 'lex':
            searchField = 'lemma'
        if not rxTest.perform(item.lex.__dict__[searchField]):
            return False
    elif checkWordform and rxTest.field in wordform.Wordform.propertyFields:
        searchField = rxTest.field
        if searchField == 'lex':
            searchField = 'lemma'
        if not rxTest.perform(item.__dict__[searchField]):
            return False
    else:
        if not checkWordform:
            testResults = [rxTest.perform(d[1])
                           for d in item.lex.otherData
                           if d[0] == rxTest.field]
        else:
            testResults = [rxTest.perform(d[1])
                           for d in item.otherData
                           if d[0] == rxTest.field]
        if len(testResults) <= 0 or not all(testResults):
            return False
    return True


class SubLexeme:
    """
    A class that describes a part of lexeme with a single
    stem and a single paradigm link. Each lexeme is deconstructed
    into one or several sublexemes.
    """

    def __init__(self, numStem, stem, paradigm, gramm, gloss, lex,
                 noIncorporation=False):
        self.numStem = numStem      # the number of the stem
        # (If several stems are equal, store them as one SubLexeme.
        # {-1} means the stem can only be incorporated)
        if type(self.numStem) == int:
            self.numStem = {self.numStem}
        self.stem = stem
        self.paradigm = paradigm
        self.gramm = gramm
        self.gloss = gloss
        self.lex = lex          # the Lexeme object this SubLexeme is a part of
        self.noIncorporation = noIncorporation

    def make_stem(self, flexInTable):
        """
        Insert the inflexion parts from the (middle) inflexion
        into the current stem and return the result
        or None if the inflexion and the stem aren't compatible.
        If the stem starts with a dot, or ends with a dot, those are deleted.
        The function is intended for future use.
        """
        if not check_compatibility(self, flexInTable.afx):
            return None
        middleStem = self.stem
        if middleStem.startswith('.'):
            middleStem = middleStem[1:]
        if middleStem.endswith('.'):
            middleStem = middleStem[:-1]
        wf, wfGlossed, gloss = wordform.join_stem_flex(middleStem,
                                                       self.gloss,
                                                       flexInTable.afx,
                                                       bStemStarted=True)
        return wf, wfGlossed, gloss

    def __repr__(self):
        res = '<SubLexeme>\n'
        res += 'stem: ' + self.stem + '\n'
        res += 'paradigm: ' + self.paradigm + '\n'
        res += 'gramm: ' + self.gramm + '\n'
        res += 'gloss: ' + self.gloss + '\n'
        res += '</SubLexeme>\n'
        return res


class ExceptionForm:
    """
    A class that describes an irregular wordform.
    """

    def __init__(self, dictDescr, errorHandler=None):
        self.form = ''
        self.gramm = ''
        self.coexist = False    # whether the same combination of grammatical
                                # values has a regular equivalent
        self.errorHandler = errorHandler
        try:
            self.gramm = dictDescr['value']
            if dictDescr['content'] is not None:
                for obj in dictDescr['content']:
                    if obj['name'] == 'coexist':
                        if obj['value'] == 'yes':
                            self.coexist = True
                        elif obj['value'] == 'no':
                            self.coexist = False
                        elif self.errorHandler is not None:
                            self.errorHandler.raise_error('The coexist field must '
                                                          'have yes or no as its value: ',
                                                          dictDescr)
                    elif obj['name'] == 'form':
                        self.form = obj['value']
        except KeyError:
            if self.errorHandler is not None:
                self.errorHandler.raise_error('Exception description error: ', dictDescr)
                return
        if len(self.form) <= 0 and self.errorHandler is not None:
            self.errorHandler.raise_error('No form provided in an exception description: ',
                                          dictDescr)

    def __eq__(self, other):
        if type(other) != ExceptionForm:
            return False
        if other.form == self.form and other.gramm == self.gramm and\
           other.coexist == self.coexist:
            return True
        return False

    def __neq__(self, other):
        return not self.__eq__(other)


class Lexeme:
    """
    A class that describes one lexeme.
    """
    obligFields = {'lex', 'stem', 'paradigm'}
    propertyFields = {'lex', 'stem', 'paradigm', 'gramm', 'gloss',
                      'lexref', 'stem-incorp', 'gramm-incorp',
                      'gloss-incorp'}
    defaultGlossFields = ['transl_en', 'transl_ru']  # property whose value is used as the stem gloss
                                     # by default if no gloss is provided
        
    def __init__(self, dictDescr, errorHandler=None):
        self.lemma = ''
        self.lexref = ''
        self.stem = ''
        self.stemIncorp = ''
        self.paradigms = []
        self.gramm = ''
        self.grammIncorp = ''
        self.gloss = ''
        self.glossIncorp = ''
        self.subLexemes = []
        self.exceptions = {}    # set of tags -> ExceptionForm object
        self.otherData = []     # list of tuples (name, value)
        self.key2func = {'lex': self.add_lemma, 'lexref': self.add_lexref,
                         'stem': self.add_stem, 'paradigm': self.add_paradigm,
                         'gramm': self.add_gramm, 'gloss': self.add_gloss,
                         'except': self.add_except, 'stem-incorp': self.add_stem_incorp,
                         'gramm-incorp': self.add_gramm_incorp,
                         'gloss-incorp': self.add_gloss_incorp}
        self.errorHandler = errorHandler
        try:
            keys = set(obj['name'] for obj in dictDescr['content'])
        except KeyError:
            self.raise_error('No content in a lexeme: ', dictDescr)
            return
        if len(Lexeme.obligFields & keys) < len(Lexeme.obligFields):
            self.raise_error('No obligatory fields in a lexeme: ',
                             dictDescr['content'])
            return
        for obj in sorted(dictDescr['content'], key=self.fields_sorting_key):
            try:
                self.key2func[obj['name']](obj)
            except KeyError:
                self.add_data(obj)
        self.check_gloss()
        self.generate_sublexemes()

    def raise_error(self, message, data=None):
        if self.errorHandler is not None:
            self.errorHandler.raise_error(message, data)

    @staticmethod
    def fields_sorting_key(obj):
        if type(obj) != dict or 'name' not in obj:
            return ''
        key = obj['name']
        try:
            order = ['lex', 'lexref', 'stem', 'paradigm', 'gramm',
                     'gloss'].index(key)
            return '!' + str(order)
        except ValueError:
            return key

    def num_stems(self):
        """Return the number of different stem numbers."""
        if len(self.subLexemes) <= 0:
            return 0
        stemNums = set()
        for i in range(len(self.subLexemes)):
            stemNums |= self.subLexemes[i].numStem
        return len(stemNums)
    
    def add_lemma(self, obj):
        lemma = obj['value']
        if type(lemma) != str or len(lemma) <= 0:
            self.raise_error('Wrong lemma: ', lemma)
            return
        if len(self.lemma) > 0:
            self.raise_error('Duplicate lemma: ' + lemma)
        self.lemma = lemma

    def add_lexref(self, obj):
        lexref = obj['value']
        if type(lexref) != str or len(lexref) <= 0:
            self.raise_error('Wrong lexical reference: ', lexref)
            return
        if len(self.lexref) > 0:
            self.raise_error('Duplicate lexical reference: ' +
                             lexref + ' in ' + self.lemma)
        self.lexref = lexref

    def add_stem(self, obj):
        stem = obj['value']
        if type(stem) != str or len(stem) <= 0:
            self.raise_error('Wrong stem in ' + self.lemma + ': ', stem)
            return
        if len(self.stem) > 0:
            self.raise_error('Duplicate stem in ' + self.lemma + ': ', stem)
        self.stem = stem

    def add_stem_incorp(self, obj):
        stemIncorp = obj['value']
        if type(stemIncorp) != str or len(stemIncorp) <= 0:
            self.raise_error('Wrong incorporated stem in ' + self.lemma + ': ', stemIncorp)
            return
        if len(self.stemIncorp) > 0:
            self.raise_error('Duplicate incorporated stem in ' + self.lemma + ': ', stemIncorp)
        self.stemIncorp = stemIncorp

    def add_gramm(self, obj):
        gramm = obj['value']
        if type(gramm) != str or len(gramm) <= 0:
            self.raise_error('Wrong gramtags in ' + self.lemma + ': ', gramm)
            return
        if len(self.gramm) > 0:
            self.raise_error('Duplicate gramtags: ' + gramm +
                             ' in ' + self.lemma)
        self.gramm = gramm

    def add_gramm_incorp(self, obj):
        grammIncorp = obj['value']
        if type(grammIncorp) != str or len(grammIncorp) <= 0:
            self.raise_error('Wrong incorporated gramtags in ' + self.lemma +
                             ': ', grammIncorp)
            return
        if len(self.gramm) > 0:
            self.raise_error('Duplicate incorporated gramtags: ' + grammIncorp +
                             ' in ' + self.lemma)
        self.grammIncorp = grammIncorp

    def add_gloss(self, obj):
        gloss = obj['value']
        if type(gloss) != str or len(gloss) <= 0:
            self.raise_error('Wrong gloss in ' + self.lemma + ': ', gloss)
            return
        if len(self.gloss) > 0:
            self.raise_error('Duplicate gloss: ' + gloss +
                             ' in ' + self.lemma)
        self.gloss = gloss

    def add_gloss_incorp(self, obj):
        glossIncorp = obj['value']
        if type(glossIncorp) != str or len(glossIncorp) <= 0:
            self.raise_error('Wrong incorporated gloss in ' + self.lemma + ': ', glossIncorp)
            return
        if len(self.glossIncorp) > 0:
            self.raise_error('Duplicate incorporated gloss: ' + glossIncorp +
                             ' in ' + self.lemma)
        self.glossIncorp = glossIncorp

    def check_gloss(self):
        """
        Check if there is a gloss associated with the lexeme,
        otherwise use the English translation (if any) or another
        default property as a gloss. If none are found, use 'ROOT'
        for a gloss.
        """
        if len(self.gloss) <= 0:
            for field in self.defaultGlossFields:
                defaultValue = self.get_data(field)
                if len(defaultValue) > 0:
                    self.gloss = defaultValue[0]
                    break
        if len(self.gloss) <= 0:
            self.gloss = 'STEM'

    def add_paradigm(self, obj):
        paradigm = obj['value']
        if type(paradigm) != str or len(paradigm) <= 0:
            self.raise_error('Wrong paradigm in ' + self.lemma +
                             ': ', paradigm)
            return
        self.paradigms.append(paradigm)

    def add_except(self, obj):
        ex2add = ExceptionForm(obj, self.errorHandler)
        tagSet = set(ex2add.gramm.split(','))
        try:
            if all(ex != ex2add for ex in self.exceptions[tagSet]):
                self.exceptions[tagSet].append(ex2add)
        except KeyError:
            self.exceptions[tagSet] = [ex2add]

    def add_data(self, obj):
        try:
            self.otherData.append((obj['name'], obj['value']))
        except KeyError:
            self.raise_error('Wrong key-value pair in ' + self.lemma +
                             ': ', obj)
        
    def get_data(self, field):
        return [d[1] for d in self.otherData if d[0] == field]

    def generate_sublexemes(self):
        self.subLexemes = []
        stems = self.separate_parts(self.stem)
        paradigms = [self.separate_parts(p) for p in self.paradigms]
        grams = self.separate_parts(self.gramm)
        glosses = self.separate_parts(self.gloss)

        # Add conversion links from the descriptions of the paradigms:
        for pGroup in paradigms:
            for p in pGroup:
                for pVariant in p:
                    try:
                        newStemConversionLinks = grammar.Grammar.paradigms[pVariant].conversion_links
                        for cl in newStemConversionLinks:
                            self.otherData.append(['conversion-link', cl])
                    except KeyError:
                        pass
        self.generate_stems(stems)
        
        if len(grams) not in [1, len(stems)]:
            self.raise_error('Wrong number of gramtags (' + self.gramm +
                             ') in ' + self.lemma)
            return
        if len(glosses) not in [0, 1, len(stems)]:
            self.raise_error('Wrong number of glosses (' + self.gloss +
                             ') in ' + self.lemma)
            return
        for p in paradigms:
            if len(p) not in [1, len(stems)]:
                self.raise_error('Wrong number of paradigms in ' +
                                 self.lemma + ': ', p)
                return
        noIncorporation = False     # whether ordinary stems can be incorporated
        if len(self.stemIncorp) > 0:
            noIncorporation = True
            curGloss, curGramm = '', ''
            if self.glossIncorp is not None:
                curGloss = self.glossIncorp
            elif len(glosses) == 1:
                curGloss = glosses[0][0]  # no variants for glosses
            elif len(glosses) > 1:
                curGloss = glosses[-1][0]
            if self.grammIncorp is not None:
                curGramm = self.grammIncorp
            elif len(grams) == 1:
                curGramm = grams[0][0]    # no variants for grams either
            elif len(grams) > 1:
                curGramm = grams[-1][0]
            self.append_sublexeme(-1, self.stemIncorp, '',
                                  curGramm, curGloss, False)
        for iStem in range(len(stems)):
            curGloss, curGramm = '', ''
            if len(glosses) == 1:
                curGloss = glosses[0][0]  # no variants for glosses
            elif len(glosses) > 1:
                curGloss = glosses[iStem][0]
            if len(grams) == 1:
                curGramm = grams[0][0]    # no variants for grams either
            elif len(grams) > 1:
                curGramm = grams[iStem][0]
            curParadigms = []
            for p in paradigms:
                if len(p) == 1:
                    curParadigms += p[0]
                else:
                    curParadigms += p[iStem]
            for curStem in stems[iStem]:
                for curParadigm in curParadigms:
                    self.append_sublexeme(iStem, curStem, curParadigm,
                                          curGramm, curGloss, noIncorporation)

    def append_sublexeme(self, iStem, curStem, curParadigm, curGramm, curGloss, noIncorporation):
        for sl in self.subLexemes:
            if (sl.stem == curStem and sl.paradigm == curParadigm
                    and sl.gramm == curGramm and sl.gloss == curGloss
                    and sl.noIncorporation == noIncorporation):
                sl.numStem.add(iStem)
                return
        self.subLexemes.append(SubLexeme(iStem, curStem, curParadigm,
                                         curGramm, curGloss, self,
                                         noIncorporation=noIncorporation))

    @staticmethod
    def separate_parts(s, sepParts='|', sepVars='//'):
        return [part.split(sepVars) for part in s.split(sepParts)]

    def generate_stems(self, stems):
        """Fill in the gaps in the stems description with the help of
        automatic stem conversion."""
        stemConversionNames = set(t[1] for t in self.otherData
                                  if t[0] == 'conversion-link')
        for scName in stemConversionNames:
            try:
                grammar.Grammar.stemConversions[scName].convert(stems)
            except KeyError:
                self.raise_error('No stem conversion named ' + scName)

    def generate_redupl_paradigm(self):
        """Create new paradigms with reduplicated parts of this particular
        lexeme or change the references if they already exist."""
        if len(grammar.Grammar.paradigms) <= 0:
            self.raise_error('Paradigms must be loaded before lexemes.')
            return
        for sl in self.subLexemes:
            if sl.paradigm not in grammar.Grammar.paradigms:
                self.raise_error('No paradigm named ' + sl.paradigm)
                continue
            paraReduplName = grammar.Grammar.paradigms[sl.paradigm].fork_redupl(sl)
            sl.paradigm = paraReduplName

    def generate_regex_paradigm(self):
        """Create new paradigms where all inflexions with regexes that
        don't match to the particular stem of this lexeme are deleted
        or change the references if they already exist."""
        if len(grammar.Grammar.paradigms) <= 0:
            self.raise_error('Paradigms must be loaded before lexemes.')
            return
        for sl in self.subLexemes:
            if sl.paradigm not in grammar.Grammar.paradigms:
                self.raise_error('No paradigm named ' + sl.paradigm)
                continue
            paraRegexName = grammar.Grammar.paradigms[sl.paradigm].fork_regex(sl)
            sl.paradigm = paraRegexName

    def generate_wordforms(self):
        """Generate a list of all possible wordforms with this lexeme."""
        if len(grammar.Grammar.paradigms) <= 0:
            self.raise_error('Paradigms must be loaded before lexemes.')
            return
        wordforms = []
        for sl in self.subLexemes:
            if sl.paradigm not in grammar.Grammar.paradigms:
                self.raise_error('No paradigm named ' + sl.paradigm)
                continue
            for flex in grammar.Grammar.paradigms[sl.paradigm].flex:
                wf = wordform.Wordform(sl, flex, self.errorHandler)
                if wf.wf is None:
                    continue
                # TODO: exceptions
                wordforms.append(wf)
        return wordforms

    def add_derivations(self):
        """Add sublexemes with links to derivations."""
        subLexemes2add = []
        for sl in self.subLexemes:
            derivName = '#deriv#paradigm#' + sl.paradigm
            if derivName in grammar.Grammar.paradigms:
                slNew = copy.deepcopy(sl)
                slNew.paradigm = derivName
                subLexemes2add.append(slNew)
        self.subLexemes += subLexemes2add
        # TODO: deriv-links in the lexeme
