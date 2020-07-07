import grammar
import lexeme
import paradigm
import re
import copy

rxCleanL = re.compile('([>~\\-])-+')
rxCleanR = re.compile('-+([<~])$')


def join_stem_flex(stem, stemGloss, flex, bStemStarted=False):
    """
    Join a stem and an inflexion.
    """
    wfGlossed = ''
    gloss = ''
    wf = ''
    pfxPart = ''
    ifxs = ''
    mainPart = ''
    curStemParts = lexeme.rxStemParts.findall(stem)
    curFlexParts = flex.flexParts[0]
    stemSpecs = ''.join(['.' + fp.gloss for fp in curFlexParts
                         if fp.glossType == paradigm.GLOSS_STEM_SPEC])
    parts = [curStemParts, curFlexParts]
    pos = [0, 0]    # current position in [stem, flex]
    iSide = 0       # 0 = stem, 1 = flex
    glossType = paradigm.GLOSS_STEM
    while any(pos[i] < len(parts[i]) for i in [0, 1]):
        if iSide == 0 and pos[iSide] == len(parts[iSide]):
            iSide = 1
        elif iSide == 1 and pos[iSide] == len(parts[iSide]):
            iSide = 0
        if (iSide == 0 and parts[iSide][pos[iSide]] in ['.', '[.]']) or\
           (iSide == 1 and parts[iSide][pos[iSide]].flex in ['.', '[.]']):
            pos[iSide] += 1
            if iSide == 0:
                iSide = 1
            elif iSide == 1:
                if pos[1] == 1 and not pos[0] == 1:
                    continue
                glossType = parts[iSide][pos[iSide] - 1].glossType
                iSide = 0
            continue
        elif iSide == 1 and\
           parts[iSide][pos[iSide]].glossType == paradigm.GLOSS_STARTWITHSELF:
            pos[iSide] += 1
            continue
        curPart = parts[iSide][pos[iSide]]
        if iSide == 0:
            wf += curPart
            bStemStarted = True
            wfGlossed += curPart
            if glossType in [paradigm.GLOSS_STEM, paradigm.GLOSS_STEM_FORCED]:
                mainPart += stemGloss + stemSpecs
        elif iSide == 1:
            wf += curPart.flex.replace('0', '')
            curFlex = curPart.flex
            if len(curFlex) <= 0 and not curPart.glossType == paradigm.GLOSS_EMPTY:
                curFlex = '∅'
            if curPart.glossType == paradigm.GLOSS_AFX:
                if bStemStarted:
                    mainPart += '-' + curPart.gloss + '-'
                else:
                    pfxPart += '-' + curPart.gloss + '-'
                wfGlossed += '-' + curFlex + '-'
            elif curPart.glossType == paradigm.GLOSS_IFX:
                ifxs += '<' + curPart.gloss + '>'
                wfGlossed += '<' + curFlex + '>'
            elif curPart.glossType == paradigm.GLOSS_REDUPL_R:
                # if bStemStarted:
                bStemStarted = True
                mainPart += '-' + curPart.gloss + '~'
                # else:
                #     pfxPart += '-' + curPart.gloss + '~'
                wfGlossed += '-' + curPart.flex + '~'
            elif curPart.glossType == paradigm.GLOSS_REDUPL_L:
                # if bStemStarted:
                bStemStarted = True
                mainPart += '~' + curPart.gloss + '-'
                # else:
                #     pfxPart += '~' + curPart.gloss + '-'
                wfGlossed += '~' + curPart.flex + '-'
            elif curPart.glossType == paradigm.GLOSS_STEM_SPEC:
                wfGlossed += curPart.flex
            elif curPart.glossType in [paradigm.GLOSS_STEM,
                                       paradigm.GLOSS_STEM_FORCED]:
                bStemStarted = True
                wfGlossed += curPart.flex
                mainPart += stemGloss + stemSpecs
            elif curPart.glossType == paradigm.GLOSS_EMPTY:
                bStemStarted = True
                wfGlossed += curPart.flex
        pos[iSide] += 1
        gloss = pfxPart + ifxs + mainPart
    try:
        gloss = rxCleanL.sub('\\1', gloss).strip('-~')
        gloss = rxCleanR.sub('\\1', gloss).strip('-~')
        wfGlossed = rxCleanL.sub('\\1', wfGlossed).strip('-~')
        wfGlossed = rxCleanR.sub('\\1', wfGlossed).strip('-~')
    except:
        pass
    return wf, wfGlossed, gloss


class Wordform:
    propertyFields = {'wf', 'gloss', 'lemma', 'gramm', 'wfGlossed'}
    printableOtherFields = {'trans_ru', 'trans_en', 'trans_de', 'lex2', 'gramm2',
                            'trans_ru2', 'trans_en2', 'trans_de2', 'root'}
    errorHandler = None
    verbosity = 0
    
    def __init__(self, sublex=None, flex=None, errorHandler=None):
        if self.errorHandler is None:
            if errorHandler is None:
                self.errorHandler = grammar.Grammar.errorHandler
            else:
                self.errorHandler = errorHandler
        self.wf = None
        self.wfGlossed = ''
        self.gloss = ''
        self.lemma = ''
        self.gramm = ''
        self.stem = ''
        self.otherData = []     # list of tuples (name, value)
        if sublex is None or flex is None:
            return
        if flex.stemNum is not None and len(flex.stemNum) > 0 and 1 < sublex.lex.num_stems() <= max(flex.stemNum):
            self.raise_error('Incorrect stem number: lexeme ' +
                             sublex.lex.lemma + ', inflexion ' +
                             flex.flex)
            return
        # elif flex.stemNum is None and sublex.lex.num_stems() > 1:
        #     self.raise_error('Unspecified stem number: lexeme ' +
        #                      sublex.lex.lemma + ', inflexion ' +
        #                      flex.flex)
        #     return

        elif len(flex.flexParts) > 1:
            self.raise_error('The inflexion ' + flex.flex +
                             ' is not fully compiled.')
            return
        elif not lexeme.check_compatibility(sublex, flex):
            return
        self.add_gramm(sublex, flex)
        self.build_value(sublex, flex)
        self.add_lemma(sublex.lex, flex)
        self.add_other_data(sublex.lex, flex)
        self.otherData = copy.deepcopy(sublex.lex.otherData)

    def raise_error(self, message, data=None):
        if self.errorHandler is not None:
            self.errorHandler.raise_error(message, data)

    def add_lemma(self, lex, flex):
        if flex.lemmaChanger is None:
            self.lemma = lex.lemma
            return
        suitableSubLex = [sl for sl in lex.subLexemes
                          if flex.lemmaChanger.stemNum is None or
                             len(sl.numStem & flex.lemmaChanger.stemNum) > 0]
        if len(suitableSubLex) <= 0:
            if lex.num_stems() == 1:
                suitableSubLex = lex.subLexemes
        if len(suitableSubLex) <= 0:
            self.raise_error('No stems available to create the new lemma ' +
                             flex.lemmaChanger.flex)
            self.lemma = ''
            return
        if len(suitableSubLex) > 1:
            if self.verbosity > 0:
                self.raise_error('Several stems available to create the new lemma ' +
                                 flex.lemmaChanger.flex)
        wfLemma = Wordform(suitableSubLex[0], flex.lemmaChanger,
                           self.errorHandler)
        self.lemma = wfLemma.wf

    def add_gramm(self, sublex, flex):
        self.stem = sublex.stem
        if not flex.replaceGrammar:
            self.gramm = sublex.gramm
            if len(sublex.gramm) > 0 and len(flex.gramm) > 0:
                self.gramm += ','
            self.gramm += flex.gramm
        else:
            self.gramm = flex.gramm
    
    def add_other_data(self, lex, flex):
        if flex.keepOtherData:
            self.otherData = copy.deepcopy(lex.otherData)

    def get_lemma(self, lex, flex):
        # TODO: lemma changers
        self.lemma = lex.lemma

    def build_value(self, sublex, flex):
        subLexStem = sublex.stem
        if flex.startWithSelf and not subLexStem.startswith('.'):
            subLexStem = '.' + subLexStem
        self.wf, self.wfGlossed, self.gloss = join_stem_flex(subLexStem,
                                                             sublex.gloss,
                                                             flex)

    def to_xml(self, glossing=True):
        """
        Return an XML representation of the analysis in the format of
        Russian National Corpus.
        If glossing is True, include the glossing information.
        """
        r = '<ana lex="' + self.lemma + '" gr="' + self.gramm + '"'
        if glossing:
            r += ' parts="' + self.wfGlossed + '" gloss="' + self.gloss + '"'
        for field, value in self.otherData:
            if field in Wordform.printableOtherFields:
                r += ' ' + field + '="' + value.replace('"', "'") + '"'
        return r + '></ana>'

    def __repr__(self):
        r = '<Wordform object>\n'
        if self.wf is not None:
            r += self.wf + '\n'
        if self.lemma is None:
            self.lemma = ''
        if self.gramm is None:
            self.gramm = ''
        r += self.lemma + '; ' + self.gramm + '\n'
        r += self.wfGlossed + '\n'
        r += self.gloss + '\n'
        for field, value in self.otherData:
            r += field + '\t' + value + '\n'
        return r

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, other):
        if self.wf != other.wf or self.lemma != other.lemma:
            return False
        return str(self) == str(other)

    def __ne__(self, other):
        return not self.__eq__(other)
