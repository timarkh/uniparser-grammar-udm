import grammar
import reduplication
import wordform

SIDE_PROCLITIC = 0
SIDE_ENCLITIC = 1
SIDE_OTHER = -1


def check_for_regex(wf, rxTest, errorHandler=None):
    """
    Perform the given RegexTest against the given Wordform.
    """
    searchField = rxTest.field
    if searchField == 'lex':
        searchField = 'lemma'
    if searchField in wordform.Wordform.propertyFields:
        try:
            if not rxTest.perform(wf.__dict__[searchField]):
                return False
        except KeyError:
            return False
    else:
        testResults = [rxTest.perform(d[1])
                       for d in wf.otherData
                       if d[0] == rxTest.field]
        if len(testResults) <= 0 or not all(testResults):
            return False
    return True


class Clitic:
    obligFields = {'lex'}
    propertyFields = {'lex', 'stem', 'paradigm', 'gramm', 'gloss', 'lexref'}
        
    def __init__(self, dictDescr, errorHandler=None):
        self.lemma = ''
        self.lexref = ''
        self.stem = None
        self.paradigms = []     # TODO: use paradigms
        self.gramm = ''
        self.gloss = ''
        self.side = SIDE_ENCLITIC
        self.regexTests = []
        self.otherData = []     # list of tuples (name, value)
        self.key2func = {'lex': self.add_lemma, 'lexref': self.add_lexref,
                         'stem': self.add_stem, 'paradigm': self.add_paradigm,
                         'gramm': self.add_gramm, 'gloss': self.add_gloss,
                         'type': self.add_side}
        if errorHandler is None:
            errorHandler = grammar.Grammar.errorHandler
        self.errorHandler = errorHandler
        try:
            keys = set(obj['name'] for obj in dictDescr['content'])
        except KeyError:
            self.raise_error('No content in a clitic: ', dictDescr)
            return
        if len(Clitic.obligFields & keys) < len(Clitic.obligFields):
            self.raise_error('No obligatory fields in a clitic: ',
                             dictDescr['content'])
            return
        # print(dictDescr['content'])
        for obj in sorted(dictDescr['content'], key=self.fields_sorting_key):
            try:
                self.key2func[obj['name']](obj)
            except KeyError:
                if obj['name'].startswith('regex-'):
                    self.add_regex_test(obj)
                else:
                    self.add_data(obj)
        if self.stem is None:
            self.stem = self.lemma

    def raise_error(self, message, data=None):
        if self.errorHandler is not None:
            self.errorHandler.raise_error(message, data)

    @staticmethod
    def fields_sorting_key(obj):
        try:
            key = obj['name']
        except KeyError:
            return ''
        try:
            order = ['lex', 'lexref', 'stem', 'paradigm', 'gramm',
                     'gloss'].index(key)
            return '!' + str(order)
        except ValueError:
            return key
    
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
        if self.stem is not None:
            self.raise_error('Duplicate stem in ' + self.lemma + ': ', stem)
        self.stem = stem

    def add_gramm(self, obj):
        gramm = obj['value']
        if type(gramm) != str or len(gramm) <= 0:
            self.raise_error('Wrong gramtags in ' + self.lemma + ': ', gramm)
            return
        if len(self.gramm) > 0:
            self.raise_error('Duplicate gramtags: ' + gramm +
                             ' in ' + self.lemma)
        self.gramm = gramm

    def add_gloss(self, obj):
        gloss = obj['value']
        if type(gloss) != str or len(gloss) <= 0:
            self.raise_error('Wrong gloss in ' + self.lemma + ': ', gloss)
            return
        if len(self.gloss) > 0:
            self.raise_error('Duplicate gloss: ' + gloss +
                             ' in ' + self.lemma)
        self.gloss = gloss

    def add_paradigm(self, obj):
        paradigm = obj['value']
        if type(paradigm) != str or len(paradigm) <= 0:
            self.raise_error('Wrong paradigm in ' + self.lemma +
                             ': ', paradigm)
            return
        self.paradigms.append(paradigm)

    def add_side(self, obj):
        side = obj['value']
        if type(side) != str or len(side) <= 0 or\
           side not in ('pro', 'en'):
            self.raise_error('Wrong type in ' + self.lemma + ': ', side)
            return
        if side == 'pro':
            self.side = SIDE_PROCLITIC
        elif side == 'en':
            self.side = SIDE_ENCLITIC

    def add_data(self, obj):
        try:
            self.otherData.append((obj['name'], obj['value']))
        except KeyError:
            self.raise_error('Wrong key-value pair in ' + self.lemma +
                             ': ', obj)
    
    def add_regex_test(self, obj):
        if not obj['name'].startswith('regex-'):
            return
        self.regexTests.append(reduplication.RegexTest(obj['name'][6:], obj['value'],
                                                       self.errorHandler))
        
    def get_data(self, field):
        return [v for k, v in self.otherData if k == field]
    
    def separate_parts(self, s, sepParts='|', sepVars='//'):
        return [part.split(sepVars) for part in s.split(sepParts)]

    def generate_stems(self, stems):
        """
        Fill in the gaps in the stems description with the help of
        automatic stem conversion.
        """
        stemConversionNames = {t[1] for t in self.otherData
                               if t[0] == 'conversion-link'}
        for scName in stemConversionNames:
            try:
                grammar.Grammar.stemConversions[scName].convert(stems)
            except KeyError:
                self.raise_error('No stem conversion named ' + scName)

    def is_compatible_str(self, strWf):
        """
        Check if the clitic is compatible with the given host word.
        """
        if len(strWf) <= 0:
            return False
        for rxTest in self.regexTests:
            if rxTest.field == 'wf' and not rxTest.perform(strWf):
                return False
        return True

    def is_compatible(self, wf, errorHandler=None):
        """
        Check if the clitic is compatible with the given Wordform.
        """
        for rxTest in self.regexTests:
            if not check_for_regex(wf, rxTest, errorHandler):
                return False
        return True
