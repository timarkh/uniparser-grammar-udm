import grammar
from reduplication import RegexTest, Reduplication, REDUPL_SIDE_RIGHT, REDUPL_SIDE_LEFT
import lexeme
import re
import copy
import time

POS_UNSPECIFIED = -1
POS_NONFINAL = 0
POS_FINAL = 1
POS_BOTH = 1

GLOSS_EMPTY = 0
GLOSS_AFX = 1
GLOSS_IFX = 2
GLOSS_REDUPL_R = 3
GLOSS_REDUPL_L = 4
GLOSS_STEM = 5
GLOSS_STEM_FORCED = 6
GLOSS_STEM_SPEC = 7
GLOSS_NEXT_FLEX = 8
GLOSS_STARTWITHSELF = 100


class ParadigmLink:
    """
    A class that describes a single paradigm link inside
    another paradigm or inflexion.
    The instances of this class do not allow deep copy (otherwise the
    derivations compilation would be too resource consuming) and therefore
    should be immutable.
    """
    
    def __init__(self, dictDescr, errorHandler=None):
        self.errorHandler = errorHandler
        try:
            self.name = dictDescr['value']
        except KeyError:
            self.raise_error('Wrong paradigm link', dictDescr)
            return
        self.subsequent = []
        self.position = POS_UNSPECIFIED
        if 'content' not in dictDescr or dictDescr['content'] is None:
            return
        for obj in dictDescr['content']:
            if obj['name'] == 'paradigm':
                self.subsequent.append(ParadigmLink(obj, errorHandler))
            elif obj['name'] == 'position':
                self.add_position(obj)
            else:
                self.raise_error('Unrecognized field in a link to a paradigm',
                                 obj)
    
    def raise_error(self, message, data=None):
        if self.errorHandler is not None:
            self.errorHandler.raise_error(message, data)

    def add_position(self, obj):
        v = obj['value']
        if v == 'final':
            self.position = POS_FINAL
        elif v == 'both':
            self.position = POS_BOTH
        elif v == 'non-final':
            self.position = POS_NONFINAL
        else:
            self.raise_error('Wrong position value: ', obj)

    def __deepcopy__(self, memo):
        return self


class InflexionPart:
    def __init__(self, flex, gloss, glossType):
        self.flex = flex
        self.gloss = gloss
        self.glossType = glossType


class Inflexion:
    """
    A class that describes an inflexion.
    """
    rxFlexSplitter = re.compile('(<\\.>|\\.|\\[[^\\[\\]]*\\]|[^.<>|\\[\\]]+)')
    rxStemNumber = re.compile('^<([0-9,]+)>(.*)')
    rxCleanGloss = re.compile('[\\[\\]!~]+')
    rxMeta = re.compile('[<>\\[\\]().0-9~!|,]')
    
    def __init__(self, dictDescr, errorHandler=None):
        self.flex = ''
        self.stemNum = None     # what stems it can attach to
        self.stemNumOut = None  # what stems the subsequent inflexions
                                # should be able to attach to
        self.passStemNum = True     # True iff stemNum must coincide with stemNumOut at any time
        self.gramm = ''         # grammatical tags separated by commas
        self.gloss = ''
        self.position = POS_UNSPECIFIED
        self.reduplications = {}    # number -> Reduplication object
        self.regexTests = []
        self.subsequent = []
        self.flexParts = [[]]   # list of consequently applied inflexions;
                                # when reduplications have been dealt with,
                                # this list should have length of 1
        self.errorHandler = errorHandler
        self.replaceGrammar = False     # if False, the grammar of the inflexion
                                        # is added to the grammar od the stem
                                        # or the previous inflexion
        self.keepOtherData = True   # if True, pass all the data from the lexeme
                                    # to the wordform
        self.otherData = []
        self.lemmaChanger = None    # an inflexion object which changes the lemma
        self.startWithSelf = False  # if true, start with the inflexion when joining
                                    # itself to a stem or to a previous inflexion
        try:
            self.flex = dictDescr['value']
        except KeyError:
            self.raise_error('Wrong inflexion: ', dictDescr)
            return
        # The length of the inflexion can equal zero, so we don't check for it.
        if 'content' not in dictDescr or dictDescr['content'] is None:
            return
        self.key2func = {'gramm': self.add_gramm, 'gloss': self.add_gloss,
                         'paradigm': self.add_paradigm_link,
                         'redupl': self.add_reduplication,
                         'lex': self.add_lemma_changer}
        for obj in dictDescr['content']:
            try:
                self.key2func[obj['name']](obj)
            except KeyError:
                if obj['name'].startswith('regex-'):
                    self.add_regex_test(obj)
                else:
                    self.add_data(obj)
        self.generate_parts()

    def raise_error(self, message, data=None):
        if self.errorHandler is not None:
            self.errorHandler.raise_error(message, data)

    def add_gramm(self, obj):
        gramm = obj['value']
        if type(gramm) != str:
            self.raise_error('Wrong gramtags in ' + self.flex + ': ', gramm)
            return
        if len(self.gramm) > 0:
            self.raise_error('Duplicate gramtags: ' + gramm +
                             ' in ' + self.flex)
        self.gramm = gramm

    def add_gloss(self, obj):
        gloss = obj['value']
        if type(gloss) != str or len(gloss) <= 0:
            self.raise_error('Wrong gloss in ' + self.flex + ': ', gloss)
            return
        if len(self.gloss) > 0:
            self.raise_error('Duplicate gloss: ' + gloss +
                             ' in ' + self.flex)
        self.gloss = gloss.replace('|', '¦')

    def add_position(self, obj):
        v = obj['value']
        if v == 'final':
            self.position = POS_FINAL
        elif v == 'both':
            self.position = POS_BOTH
        elif v == 'non-final':
            self.position = POS_NONFINAL
        else:
            self.raise_error('Wrong position value: ', obj)
    
    def add_paradigm_link(self, obj, checkIfExists=False):
        if checkIfExists and any(p.name == obj['value']
                                 for p in self.subsequent):
            return
        self.subsequent.append(ParadigmLink(obj, self.errorHandler))

    def add_reduplication(self, obj):
        try:
            numRedupl = int(obj['value'])
        except (KeyError, ValueError):
            self.raise_error('Wrong reduplication: ', obj)
            return
        if 'content' not in obj or obj['content'] is None:
            obj['content'] = []
        if numRedupl in self.reduplications:
            self.raise_error('Duplicate reduplication: ', obj)
        self.reduplications[numRedupl] = Reduplication(obj['content'],
                                                       self.errorHandler)

    def add_regex_test(self, obj):
        if not obj['name'].startswith('regex-'):
            return
        self.regexTests.append(RegexTest(obj['name'][6:], obj['value'],
                                         self.errorHandler))

    def add_data(self, obj):
        self.otherData.append((obj['name'], obj['value']))

    def add_lemma_changer(self, obj):
        newLemma = obj['value']
        if type(newLemma) != str:
            self.raise_error('Wrong lemma in ' + self.flex + ': ', newLemma)
            return
        dictDescr = {'name': 'flex', 'value': newLemma, 'content': []}
        self.lemmaChanger = Inflexion(dictDescr, self.errorHandler)
        self.lemmaChanger.startWithSelf = True

    def remove_stem_number(self):
        flex = self.flex
        mStemNumber = self.rxStemNumber.search(flex)
        if mStemNumber is not None:
            try:
                self.stemNum = set(int(x.strip()) for x in mStemNumber.group(1).split(','))
                if self.stemNumOut is None:
                    self.stemNumOut = copy.deepcopy(self.stemNum)
                flex = mStemNumber.group(2)
            except ValueError:
                self.raise_error('Wrong stem number: ' + flex)
                flex = re.sub('^<[0-9,]*>', '', flex)
        return flex
    
    def generate_parts(self):
        """
        Split the inflexion into parts each of which is
        either a string segment, or a part of the stem or
        of another inflexion that should be eventually applied
        to the current one. Each part is represented with an
        InflexionPart instance.
        self.flexParts is a list whose members are descriptions of
        affixes that should be applied consequently, each
        description being a list of InflexionPart objects.
        This function only fills the first element of this list,
        while other elements may be added during paradigm compilation.
        A fully compiled inflexion has only one element in
        this list.
        """

        self.flexParts = [[]]
        flex = self.remove_stem_number()
        flexParts = self.rxFlexSplitter.findall(flex)
        if len(self.gloss) <= 0:
            glossParts = [''] * len(flexParts)
        else:
            glossParts = self.gloss.split('¦')
        iGlossPart = 0
        iRedupl = 0
        bStemStarted = False
        bStemForcedRepeat = False
        for flexPart in flexParts:
            # 1. Look at the gloss.
            if ('.' not in flexPart and not (flexPart.startswith('[')
                                             and flexPart.endswith(']'))):
                if iGlossPart >= len(glossParts):
                    self.raise_error('No correspondence between the inflexion ' +
                                     '(' + self.flex + ') and the glosses ' +
                                     '(' + self.gloss + ') ')
                    return
                if glossParts[iGlossPart].startswith('!'):
                    bStemForcedRepeat = True
                    # glossParts[iGlossPart] = glossParts[iGlossPart][1:]
                if bStemStarted and not bStemForcedRepeat:
                    glossType = GLOSS_IFX
                else:
                    glossType = GLOSS_AFX
                if len(glossParts[iGlossPart]) >= 2 and\
                   glossParts[iGlossPart][0] == '[' and\
                   glossParts[iGlossPart][-1] == ']':
                    # glossParts[iGlossPart] = glossParts[iGlossPart][1:len(glossParts[iGlossPart])-1]
                    glossType = GLOSS_STEM_SPEC
                elif glossParts[iGlossPart].startswith('~'):
                    glossType = GLOSS_REDUPL_L
                    # glossParts[iGlossPart] = glossParts[iGlossPart][1:]
                elif glossParts[iGlossPart].endswith('~'):
                    glossType = GLOSS_REDUPL_R
                    # glossParts[iGlossPart] = glossParts[iGlossPart][:-1]
            
            # 2. Look at the inflexion.
            if len(flexPart) == 0:
                self.flexParts[0].append(InflexionPart('', '', GLOSS_EMPTY))
            elif flexPart == '0':
                self.flexParts[0].append(InflexionPart('', glossParts[iGlossPart],
                                                       glossType))
                iGlossPart += 1
            elif flexPart.startswith('[~') and flexPart.endswith(']'):
                try:
                    m = re.search('^\\[~([^\\[\\]]*)\\]$', flexPart)
                    if len(m.group(1)) <= 0:
                        curReduplNum = iRedupl
                        flexPart = '[~' + str(curReduplNum) + ']'
                        iRedupl += 1
                    else:
                        curReduplNum = int(m.group(1))
                except:
                    self.raise_error('Wrong reduplication: ' + flex)
                    return
                try:
                    side = self.reduplications[curReduplNum].side
                except KeyError:
                    self.raise_error('No reduplication #' + str(curReduplNum) +
                                     ': ' + flex)
                    return
                if side == REDUPL_SIDE_RIGHT:
                    glossType = GLOSS_REDUPL_R
                elif side == REDUPL_SIDE_LEFT:
                    glossType = GLOSS_REDUPL_L
                #if bStemStarted:
                bStemStarted = True
                bStemForcedRepeat = True
                self.flexParts[0].append(InflexionPart(flexPart,
                                                       glossParts[iGlossPart], glossType))
                iGlossPart += 1
            elif flexPart == '.' or flexPart == '[.]':
                glossType = GLOSS_STEM
                if bStemForcedRepeat:
                    glossType = GLOSS_STEM_FORCED
                elif bStemStarted:
                    glossType = GLOSS_EMPTY
                bStemStarted = True
                bStemForcedRepeat = False
                self.flexParts[0].append(InflexionPart(flexPart, '.', glossType))
            elif flexPart.startswith('[') and flexPart.endswith(']'):
                glossType = GLOSS_STEM
                if bStemForcedRepeat:
                    glossType = GLOSS_STEM_FORCED
                elif bStemStarted:
                    glossType = GLOSS_EMPTY
                bStemStarted = True
                bStemForcedRepeat = False
                self.flexParts[0].append(InflexionPart(flexPart[1:len(flexPart)-1],
                                                    '', glossType))
            elif flexPart == '<.>':
                self.flexParts[0].append(InflexionPart('<.>', '<.>', GLOSS_NEXT_FLEX))
            else:
                self.flexParts[0].append(InflexionPart(flexPart,
                    self.rxCleanGloss.sub('', glossParts[iGlossPart]),
                                                       glossType))
                iGlossPart += 1

        self.ensure_infixes()
        self.rebuild_value()

    def ensure_infixes(self):
        """
        Make sure that the inflexion parts that follow the stem
        aren't called infixes.
        """
        for flexPartsSet in self.flexParts:
            for iFlexPart in range(len(flexPartsSet))[::-1]:
                if flexPartsSet[iFlexPart].glossType in\
                   [GLOSS_STEM, GLOSS_STEM_FORCED, GLOSS_EMPTY,
                    GLOSS_REDUPL_L, GLOSS_REDUPL_R]:
                    return
                elif flexPartsSet[iFlexPart].glossType == GLOSS_IFX:
                    flexPartsSet[iFlexPart].glossType = GLOSS_AFX

    def make_final(self):
        """Prohibit subsequent extension of the inflexion."""
        self.position = POS_FINAL
        self.subsequent = []
        if len(self.flexParts) <= 0:
            return
        self.flexParts[-1] = [part for part in self.flexParts[-1]
                              if part.flex != '<.>']
        self.rebuild_value()

    def rebuild_value(self):
        """
        Rebuild the self.flex value using the information from
        self.flexParts list.
        self.flexParts is what's responsible for the behaviour of the
        inflexion. The self.flex property can be used as a string
        representation of the inflexion, but the user must ensure
        it is up to date every time they use it.
        """
        newFlex = ''
        specialChars = {'.', '[', ']', '<', '>'}
        for fps in self.flexParts:
            curFlex = ''
            if self.stemNum is not None and len(self.stemNum) > 0:
                curFlex = '<' + ','.join(str(x) for x in sorted(self.stemNum)) + '>'
            for fp in fps:
                if len(fp.flex) > 0 and len(curFlex) > 0 and\
                   fp.flex[0] not in specialChars and\
                   curFlex[-1] not in specialChars:
                    curFlex += '|'
                curFlex += fp.flex
            if len(newFlex) > 0:
                newFlex += ' + '
            newFlex += curFlex
        self.flex = newFlex

    def get_length(self):
        """Return the length of the inflexion without metacharacters."""
        self.rebuild_value()
        return len(self.rxMeta.sub('', self.flex))

    def simplify_redupl(self, sublex):
        """Replace [~...]'s with actual segments for the given SubLexeme."""
        if len(self.flexParts) == 1 and all(not fp.flex.startswith('[~')
                                            for fp in self.flexParts[0]):
            return []
        reduplParts = []
        pTmp = Paradigm({'name': 'paradigm', 'value': 'tmp',
                         'content': None}, self.errorHandler)
        subLexStem = sublex.stem
        if self.startWithSelf and not subLexStem.startswith('.'):
            subLexStem = '.' + subLexStem
        curStemParts = re.findall('(\\.|[^.]+)', subLexStem)
        for iFlexPart in range(len(self.flexParts)):
            strForm = ''
            reduplNumbers = set()
            curFlexParts = [fp.flex for fp in self.flexParts[0]
                            if fp.glossType != GLOSS_STARTWITHSELF]
            parts = [curStemParts, curFlexParts]
            pos = [0, 0]  # current position in [stem, flex]
            iSide = 0     # 0 = stem, 1 = flex
            while any(pos[i] < len(parts[i]) for i in [0, 1]):
                if iSide == 0 and pos[iSide] == len(parts[iSide]):
                    iSide = 1
                elif iSide == 1 and pos[iSide] == len(parts[iSide]):
                    iSide = 0
                if parts[iSide][pos[iSide]] in ['.', '[.]']:
                    pos[iSide] += 1
                    if iSide == 0:
                        iSide = 1
                    elif iSide == 1:
                        if pos[1] == 1 and not pos[0] == 1:
                            continue
                        iSide = 0
                    continue
                if iSide == 1 and parts[iSide][pos[iSide]].startswith('[~'):
                    try:
                        m = re.search('^\\[~([^\\[\\]]*)\\]$',
                                      parts[iSide][pos[iSide]])
                        reduplNum = int(m.group(1))
                        reduplNumbers.add(reduplNum)
                    except:
                        self.raise_error('Wrong reduplication: ', parts[iSide][pos[iSide]])
                strForm += parts[iSide][pos[iSide]]
                pos[iSide] += 1
            reduplParts += self.reduplicate_str(strForm, reduplNumbers)
            if len(self.flexParts) > 1:
                self.flexParts = pTmp.join_inflexion_parts([self.flexParts[0]],
                                                           self.flexParts[1:])
        self.rebuild_value()
        return reduplParts

    def reduplicate_str(self, strForm, reduplNumbers):
        reduplParts = {}
        for reduplNum in sorted(reduplNumbers):
            m = re.search('^(.*?)\\[~' + str(reduplNum) + '\\](.*)$',
                          strForm)
            if m is None:
                self.raise_error('Reduplication impossible: form ' + strForm +
                                 ', reduplication #' + str(reduplNum))
                return
            segment2reduplicate = ''
            if self.reduplications[reduplNum].side == REDUPL_SIDE_RIGHT:
                segment2reduplicate = m.group(2)
            elif self.reduplications[reduplNum].side == REDUPL_SIDE_LEFT:
                segment2reduplicate = m.group(1)
            segment2reduplicate = re.sub('\\[~[^\\[\\]]*\\]', '',
                                         segment2reduplicate)
            segment2reduplicate = self.reduplications[reduplNum].perform(segment2reduplicate)
            reduplParts[reduplNum] = segment2reduplicate
            strForm = m.group(1) + segment2reduplicate + m.group(2)
        self.replace_redupl_parts(reduplParts, 0)
        return [reduplParts[reduplNum] for reduplNum in sorted(reduplNumbers)]

    def replace_redupl_parts(self, reduplParts, flexPartNum=0):
        """
        Replace [~...]'s whose numbers are among the keys of the
        reduplParts dictionary with actual strings in the flexPart list
        with the given number.
        """
        if flexPartNum < 0 or flexPartNum >= len(self.flexParts):
            return
        for iFp in range(len(self.flexParts[flexPartNum])):
            fp = self.flexParts[flexPartNum][iFp]
            if fp.flex.startswith('[~'):
                try:
                    m = re.search('^\\[~([^\\[\\]]*)\\]$', fp.flex)
                    reduplNum = int(m.group(1))
                    if reduplNum in reduplParts:
                        # fp.flex = reduplParts[reduplNum]
                        self.insert_redupl_part(reduplParts[reduplNum],
                                                iFp, flexPartNum)
                except:
                    self.raise_error('Wrong reduplication: ', fp.flex)

    def insert_redupl_part(self, reduplPart, iFp, flexPartNum):
        """
        Insert a reduplicated string in self.flexParts instead of
        a [~...] element.
        """
        if flexPartNum < 0 or flexPartNum >= len(self.flexParts):
            return
        fpRedupl = self.flexParts[flexPartNum].pop(iFp)
        reduplFragmentParts = re.findall('(<\\.>|[^<>]+)', reduplPart)
        for iReduplFragmentPart in range(len(reduplFragmentParts)):
            fpTmp = copy.deepcopy(fpRedupl)
            if reduplFragmentParts[iReduplFragmentPart] == '<.>':
                fpTmp.gloss = '<.>'
                fpTmp.glossType = GLOSS_NEXT_FLEX
            elif iReduplFragmentPart > 1:
                fpTmp.gloss = ''
            fpTmp.flex = reduplFragmentParts[iReduplFragmentPart]
            self.flexParts[flexPartNum].insert(iFp + iReduplFragmentPart, fpTmp)
        # if len(reduplFragmentParts) > 1:
        #     print(str(self))

    def get_middle(self):
        """
        Return an Inflexion object containig only the middle parts
        (those inside the stem).
        """
        flexMiddle = copy.deepcopy(self)
        # middle: everything from the first stem part or infix to the last ones
        beginMiddle = 0
        endMiddle = 0
        for iFP in range(len(flexMiddle.flexParts[0])):
            fp = flexMiddle.flexParts[0][iFP]
            if fp.glossType in [GLOSS_STEM, GLOSS_STEM_FORCED,
                                GLOSS_IFX, GLOSS_STEM_SPEC]:
                if beginMiddle == 0:
                    beginMiddle = iFP
                endMiddle = iFP + 1
        flexMiddle.flexParts[0] = flexMiddle.flexParts[0][beginMiddle:endMiddle]
        return flexMiddle

    def get_pfx(self):
        """
        Return a tuple containig the initial part of the
        inflexion (before the first stem part or infix).
        Works correctly only if len(self.flexParts) == 1.
        Intended for future use.
        """
        if len(self.flexParts) <= 0:
            return None
        afx = ''
        afxGlossed = ''
        gloss = ''
        for fp in self.flexParts[0]:
            if fp.glossType in [GLOSS_EMPTY, GLOSS_STARTWITHSELF]:
                continue
            elif fp.glossType in [GLOSS_STEM, GLOSS_STEM_FORCED,
                                  GLOSS_IFX, GLOSS_STEM_SPEC]:
                break
            afx += fp.flex
            afxGlossed += fp.flex + '-'
            gloss += fp.gloss + '-'
        return afx, afxGlossed, gloss

    def get_sfx(self):
        """
        Return a tuple containig the caudal part of the
        inflexion (after the last stem part or infix).
        Works correctly only if len(self.flexParts) == 1.
        Intended for future use.
        """
        if len(self.flexParts) <= 0:
            return None
        afx = ''
        afxGlossed = ''
        gloss = ''
        for fp in self.flexParts[0][::-1]:
            if fp.glossType in [GLOSS_EMPTY, GLOSS_STARTWITHSELF]:
                continue
            elif fp.glossType in [GLOSS_STEM, GLOSS_STEM_FORCED,
                                  GLOSS_IFX, GLOSS_STEM_SPEC]:
                break
            afx = fp.flex + afx
            afxGlossed = '-' + fp.flex + afxGlossed
            gloss = '-' + fp.gloss + gloss
        return afx, afxGlossed, gloss

    def __str__(self):
        r = '<Inflexion object>\n'
        r += 'flex: ' + self.flex + '\n'
        r += 'gramm: ' + self.gramm + '\n'
        for iFPs in range(len(self.flexParts)):
            if len(self.flexParts) > 1:
                r += 'Inflexion parts list #' + str(iFPs) +\
                     ' out of' + str(len(self.flexParts)) + ':\n'
            for fp in self.flexParts[iFPs]:
                r += fp.flex + '\t' + fp.gloss + '\t' +\
                     str(fp.glossType) + '\n'
            r += '\n'
            if len(self.subsequent) > 0:
                r += 'links: ' + '; '.join(pl.name for pl in self.subsequent) + '\n'
        return r


class Paradigm:
    """
    A class that describes one paradigm. A paradigm
    is basically a list of inflexions which can
    have links to subsequent inflexions.
    Paradigm instances are also used to represent
    derivations.
    """
    rxEmptyFlex = re.compile('^[.<>\\[\\]0-9,]*$')
    errorHandler = None
    
    def __init__(self, dictDescr, errorHandler=None):
        if self.errorHandler is None:
            self.errorHandler = errorHandler
        self.name = dictDescr['value']
        self.flex = []
        self.subsequent = []
        self.derivLinks = []
        self.conversion_links = []
        self.position = POS_UNSPECIFIED
        self.regexTests = None  # (field, regex as string) -> [RegexTest,
                                # set of numbers of inflexions which rely on
                                # that regex]
                                # (the actual dictionary is built later)
        self.containsReduplications = False
        if 'content' not in dictDescr or dictDescr['content'] is None:
            return
        if dictDescr['name'] == 'paradigm':
            self.init_paradigm(dictDescr['content'])
        elif dictDescr['name'] == 'deriv-type':
            self.init_derivation(dictDescr['content'])
        self.redistribute_paradigms()

    @classmethod
    def raise_error(cls, message, data=None):
        if cls.errorHandler is not None:
            cls.errorHandler.raise_error(message, data)

    def init_derivation(self, data):
        """Create an inflexion for each stem of the derivation."""
        stems = ['']
        glosses = ['']
        gramms = ['']
        newData = []
        for obj in self.separate_variants(data):
            if obj['name'] == 'stem':
                stems = obj['value'].split('|')
            elif obj['name'] == 'gloss':
                glosses = obj['value'].split('|')
            elif obj['name'] == 'gramm':
                gramms = obj['value'].split('|')
            else:
                newData.append(obj)
        if len(glosses) == 1 and len(stems) > 1:
            glosses *= len(stems)
        if len(gramms) == 1 and len(stems) > 1:
            gramms *= len(stems)
        if len(glosses) != len(stems) or len(gramms) != len(stems):
            self.raise_error('The number of glosses and grammatical tags sets ' +
                             'should equal either 1 or the number of stems ' +
                             'in the derivation (stem=' + '|'.join(stems) +
                             ', gloss=' + '|'.join(glosses) +
                             ', gramm=' + '|'.join(gramms) + ')')
            return
        iStem = 0
        for stem, gloss, gramm in zip(stems, glosses, gramms):
            for stemVar in stem.split('//'):
                stemVar = re.sub('\\.(?!\\])', '<.>', stemVar)
                stemVar = stemVar.replace('[.]', '.')
                bReplaceGrammar = True
                arrContent = copy.deepcopy(newData)
                if len(gloss) > 0:
                    arrContent.append({'name': 'gloss', 'value': gloss})
                if gramm.startswith('+') or len(gramm) <= 0:
                    bReplaceGrammar = False
                    gramm = gramm[1:]
                arrContent.append({'name': 'gramm', 'value': gramm})
                dictDescr = {'name': 'flex', 'value': stemVar,
                             'content': arrContent}
                flex = Inflexion(dictDescr, self.errorHandler)
                flex.passStemNum = False
                if len(stems) > 1:
                    flex.stemNumOut = {iStem}
                flex.position = POS_NONFINAL
                flex.replaceGrammar = bReplaceGrammar
                flex.keepOtherData = False
                flex.startWithSelf = True
                if len(flex.flexParts[0]) > 0:
                    flex.flexParts[0].insert(0, InflexionPart('', '',
                                                              GLOSS_STARTWITHSELF))
                self.flex.append(flex)
            iStem += 1
        
    def init_paradigm(self, data):
        for obj in self.separate_variants(data):
            if obj['name'] == 'flex':
                newInflexion = Inflexion(obj, self.errorHandler)
                if len(newInflexion.reduplications) > 0:
                    self.containsReduplication = True
                self.flex.append(newInflexion)
            elif obj['name'] == 'paradigm':
                self.subsequent.append(obj)
            elif obj['name'] == 'position':
                self.position = obj['value']
            elif obj['name'] == 'deriv-link':
                self.add_deriv_link(obj)
            elif obj['name'] == 'conversion-link':
                self.conversion_links.append(obj['value'])
            else:
                self.raise_error('Unrecognized field in a paradigm: ' +
                                 obj['name'])

    def add_deriv_link(self, obj):
        self.derivLinks.append(obj)
    
    def separate_variants(self, arrDescr):
        for obj in arrDescr:
            if obj['name'] != 'flex' or '/' not in obj['value']:
                yield obj
            else:
                values = obj['value'].split('//')
                for value in values:
                    objVar = copy.deepcopy(obj)
                    objVar['value'] = value
                    yield objVar
        
    def redistribute_paradigms(self):
        """Copy paradigm-level links to subsequent paradigms to each
        of the individual inflexions."""
        if self.position != POS_UNSPECIFIED:
            for flex in self.flex:
                if flex.position == POS_UNSPECIFIED:
                    flex.position = self.position
        for obj in self.subsequent:
            for flex in self.flex:
                flex.add_paradigm_link(obj, True)
        self.subsequent = []
        self.position = POS_UNSPECIFIED

    def build_regex_tests(self):
        """
        Build a dictionary which contains all regex tests from
        the inflexions.
        Must be performed after the paradigm has been compiled.
        """
        self.regexTests = {}
        for iFlex in range(len(self.flex)):
            flex = self.flex[iFlex]
            for rt in flex.regexTests:
                sField, sRx = rt.field, rt.sTest
                if sField == 'prev':
                    sField = 'stem'
                try:
                    self.regexTests[(sField, sRx)][1].add(iFlex)
                except KeyError:
                    self.regexTests[(sField, sRx)] = [rt, {iFlex}]

    def continue_compilation(self, depth, startTime):
        """
        Check if the paradigm compilation loop should be continued,
        taking all possible constraints into consideration.
        """
        g = grammar.Grammar
        timePassed = time.time() - startTime
        if g.PARTIAL_COMPILE and timePassed > g.MAX_COMPILE_TIME:
            return False
        if depth > g.TOTAL_DERIV_LIMIT:
            return False
        for f in self.flex:
            flen = f.get_length()
            if ((f.position != POS_FINAL and
                 f.join_depth < g.DERIV_LIMIT and
                 flen < g.FLEX_LENGTH_LIMIT) and
                 (not g.PARTIAL_COMPILE or flen < g.MIN_FLEX_LENGTH)):
                return True
        return False

    def compile_paradigm(self):
        """
        Recursively join all the inflexions with the subsequent ones.
        Calling this function may result in huge memory usage. One way
        of dealing with this is to put upper bounds on the length of
        the resulting inflexions or total number of links the compilation
        will follow.
        Specifically, each inflexion can join non-empty subsequent inflexions
        at most grammar.Grammar.DERIV_LIMIT times.
        """
        depth = 0
        g = grammar.Grammar
        startTime = time.time()
        for f in self.flex:
            f.join_depth = 1
        while self.continue_compilation(depth, startTime):
            newFlex = []
            newFlexExtensions = []
            for f in self.flex:
                if depth == 0:
                    shortName = re.sub('#paradigm#[^#]+$', '',
                                       self.name)
                    f.dictRecurs = {shortName: 1}
                    # dictRecurs is a temporary dictionary which shows
                    # how many times certain paradigms were used in the
                    # course of this inflexion's generation
                if len(f.subsequent) <= 0 or f.position == POS_FINAL or\
                   f.position == POS_BOTH:
                    fNew = copy.deepcopy(f)
                    fNew.make_final()
                    fNew.__dict__.pop('dictRecurs', None)
                    newFlex.append(fNew)
                    if len(f.subsequent) <= 0 or f.position == POS_FINAL:
                        continue
                fLen = f.get_length()
                if (g.PARTIAL_COMPILE and
                        (fLen >= g.MIN_FLEX_LENGTH or
                         f.join_depth >= g.DERIV_LIMIT or
                         time.time() - startTime > g.MAX_COMPILE_TIME)):
                    newFlex.append(copy.deepcopy(f))
                else:
                    if f.join_depth >= grammar.Grammar.DERIV_LIMIT or\
                       f.get_length() > grammar.Grammar.FLEX_LENGTH_LIMIT:
                        # just dismiss it and hope it does not occur frequently in the texts
                        print('DISMISS', f)
                        continue
                    curFlexExtensions = self.extend_one(f)
                    print('EXTEND:\n', f, '\n' + '\nand\n'.join(str(fe) for fe in curFlexExtensions))
                    newFlexExtensions += curFlexExtensions
            self.flex = newFlex + newFlexExtensions
            if len(newFlexExtensions) <= 0:
                break
            depth += 1
        self.remove_redundant()

    def remove_redundant(self):
        """
        Remove 'hanging', i. e. strictly non-final, inflexions
        from the list of inflexions after the compilation of the paradigm.
        """
        for iFlex in range(len(self.flex))[::-1]:
            f = self.flex[iFlex]
            if (not grammar.Grammar.PARTIAL_COMPILE and
                    (len(f.subsequent) > 0 and f.position != POS_FINAL and
                     f.position != POS_BOTH)):
                print('REMOVE', f)
                self.flex.pop(iFlex)
            else:
                f.__dict__.pop('dictRecurs', None)

    def extend_one(self, flexL):
        """
        Follow all links to other paradigms in the description
        of the inflexion flexL. Return a list of resulting
        inflexions.
        """
        if grammar.Grammar.PARTIAL_COMPILE\
                and flexL.get_length() >= grammar.Grammar.MIN_FLEX_LENGTH:
            return [flexL]
        extensions = []
        for paradigmLink in flexL.subsequent:
            shortName = re.sub('#paradigm#[^#]+$', '',
                               paradigmLink.name)
            dictRecurs = flexL.dictRecurs.copy()
            try:
                dictRecurs[shortName] += 1
            except KeyError:
                dictRecurs[shortName] = 1
            if dictRecurs[shortName] > grammar.Grammar.RECURS_LIMIT:
                continue
            for flexR in grammar.Grammar.paradigms[paradigmLink.name].flex:
                flexExt = self.join_inflexions(copy.deepcopy(flexL),
                                               copy.deepcopy(flexR),
                                               copy.deepcopy(paradigmLink))
                if flexExt is not None:
                    flexExt.dictRecurs = dictRecurs
                    # the same dictRecurs is used for all resulting inflexions
                    # of this step
                    extensions.append(flexExt)
                    if grammar.Grammar.paradigms[paradigmLink.name].containsReduplications:
                        self.containsReduplications = True
        return extensions

    @classmethod
    def join_inflexions(cls, flexL, flexR, paradigmLink):
        # print(flexL.flex, flexR.flex)
        if not cls.stem_numbers_agree(flexL, flexR):
            return None
        if not cls.join_regexes(flexL, flexR):
            return None

        # Manage links to the subsequent paradigms:
        if paradigmLink.position != POS_UNSPECIFIED:
            flexL.position = paradigmLink.position
        else:
            flexL.position = flexR.position
        if paradigmLink.position == POS_FINAL:
            flexL.make_final()
        elif len(paradigmLink.subsequent) > 0:
            flexL.subsequent = paradigmLink.subsequent
        else:
            flexL.subsequent = flexR.subsequent

        # Join all other fields:
        if not flexR.replaceGrammar:
            if len(flexL.gramm) > 0 and len(flexR.gramm) > 0:
                flexL.gramm += ','
            flexL.gramm += flexR.gramm
        else:
            flexL.gramm = flexR.gramm
            flexL.replaceGrammar = True
        if not flexR.keepOtherData:
            flexL.keepOtherData = False
        cls.join_reduplications(flexL, flexR)
        flexL.flexParts = cls.join_inflexion_parts(flexL.flexParts,
                                                   flexR.flexParts)
        flexL.ensure_infixes()
        flexL.rebuild_value()
        # print('Result:', flexL.flex)
        return flexL

    @staticmethod
    def stem_numbers_agree(flexL, flexR):
        """
        Check if the inflexions' stem number fields agree.
        Make both stem numbers equal.
        Return True if the numbers agree, and False if they don't.
        """
        if flexL.stemNumOut is not None and flexR.stemNum is not None:
            if len(flexL.stemNumOut & flexR.stemNum) <= 0:
                return False
            else:
                flexL.stemNumOut, flexR.stemNum = flexL.stemNumOut & flexR.stemNum, flexL.stemNumOut & flexR.stemNum
                if flexR.passStemNum:
                    flexR.stemNumOut = copy.deepcopy(flexR.stemNum)
        # print(flexL.stemNum, flexL.stemNumOut, flexR.stemNum, flexR.stemNumOut)
        if flexL.stemNumOut is None or flexL.passStemNum:
            flexL.stemNumOut = flexR.stemNumOut
            if flexL.stemNum is None or flexL.passStemNum:
                if flexR.stemNum is not None:
                    flexL.stemNum = copy.deepcopy(flexR.stemNum)
                else:
                    flexR.stemNum = copy.deepcopy(flexL.stemNum)
            flexL.passStemNum = flexL.passStemNum or flexR.passStemNum
            if flexL.passStemNum and flexL.stemNum is not None and flexL.stemNumOut is None:
                flexL.stemNumOut = copy.deepcopy(flexL.stemNum)
        elif flexR.stemNumOut is not None and not flexR.passStemNum:
            flexL.stemNumOut = copy.deepcopy(flexR.stemNumOut)
        # print('-->', flexL.stemNum, flexL.stemNumOut, flexR.stemNum, flexR.stemNumOut)
        return True

    @classmethod
    def flex_is_empty(cls, flexValue):
        """Check if the inflexion does not contain any non-empty segments."""
        if type(flexValue) is not str:
            flexValue.rebuild_value()
            flexValue = flexValue.flex
        if cls.rxEmptyFlex.search(flexValue):
            return True
        return False

    @classmethod
    def join_regexes(cls, flexL, flexR):
        """
        Check if the inflexions' regexes agree.
        If they agree, add flexR's regexes to flexL and return True,
        if they don't, return False.
        """
        bAgree = True
        flexL.rebuild_value()
        valueL = flexL.flex
        if len(flexL.flexParts) > 1:
            valueL = re.sub('^.* + ', '', valueL)
        flexR.rebuild_value()
        valueR = flexR.flex
        if len(flexR.flexParts) > 1:
            valueR = re.sub(' + .*', '', valueR)

        bEmptyL = cls.flex_is_empty(valueL)
        bEmptyR = cls.flex_is_empty(valueR)

        for rxNext in flexL.regexTests:
            if rxNext.field == 'next' and not bEmptyR and not rxNext.perform(valueR):
                return False
            elif rxNext.field.startswith('next-'):
                field2test = rxNext.field[5:]
                if field2test == 'gramm' and not rxNext.perform(flexR.gramm):
                    return False
                elif field2test == 'gloss' and not rxNext.perform(flexR.gloss):
                    return False

        if not bEmptyR:
            flexL.regexTests = [rxTest for rxTest in flexL.regexTests
                                if not rxTest.field.startswith('next')]

        if not (bEmptyL or bEmptyR):
            try:
                flexL.join_depth += 1
            except AttributeError:
                pass
        # If the left inflexion is empty, regex-prev of the right inflexion
        # become regex-stem of the joined inflexion.
        tests2add = []
        for rxPrev in flexR.regexTests:
            if rxPrev.field == 'prev':
                if bEmptyL:
                    if grammar.Grammar.PARTIAL_COMPILE:
                        tests2add.append(copy.deepcopy(rxPrev))
                    elif all(rt.field != 'stem' or rt.sTest != rxPrev.sTest
                             for rt in flexL.regexTests):
                        tests2add.append(copy.deepcopy(rxPrev))
                        tests2add[-1].field = 'stem'
                else:
                    if not rxPrev.perform(valueL):
                        return False
            elif rxPrev.field.startswith('prev-'):
                field2test = rxPrev.field[5:]
                if field2test == 'gramm' and not rxPrev.perform(flexL.gramm):
                    return False
                elif field2test == 'gloss' and not rxPrev.perform(flexL.gloss):
                    return False
            elif all(rt.field != rxPrev.field or rt.sTest != rxPrev.sTest
                     for rt in flexL.regexTests):
                tests2add.append(copy.deepcopy(rxPrev))
        for rxTest in tests2add:
            flexL.regexTests.append(rxTest)
        return True

    @classmethod
    def join_inflexion_parts(cls, flexPartsL, flexPartsR):
        if any((fp.glossType == GLOSS_REDUPL_L and fp.flex.startswith('[~')) or
               (fp.glossType == GLOSS_REDUPL_R and fp.flex.startswith('[~'))
               for fp in flexPartsL[-1]):
            return flexPartsL + flexPartsR
        
        if len(flexPartsL[-1]) <= 0:
            return flexPartsL[:-1] + flexPartsR
        elif len(flexPartsR[0]) <= 0:
            return flexPartsL + flexPartsR[1:]

        if flexPartsR[0][0].glossType == GLOSS_STARTWITHSELF:
            fpOldR = flexPartsR[0][1:]
            if flexPartsL[-1][0].glossType == GLOSS_STARTWITHSELF:
                fpOldL = flexPartsL[-1][1:]
            else:
                fpOldL = flexPartsL[-1]
            if fpOldL[0].flex != '<.>':
                fpOldL.insert(0, InflexionPart('<.>', '<.>', GLOSS_NEXT_FLEX))
            fpNew = [InflexionPart('', '', GLOSS_STARTWITHSELF)]
        else:
            fpOldR = flexPartsR[0]
            if flexPartsL[-1][0].glossType == GLOSS_STARTWITHSELF:
                fpOldL = flexPartsL[-1][1:]
            else:
                fpOldL = flexPartsL[-1]
            # fpNew = [InflexionPart('', '', GLOSS_STARTWITHSELF)]
            fpNew = []

        fpOld = [fpOldL, fpOldR]
        pos = [0, 0]
        iSide = 0
        bStemStarted = False
        bStemForcedRepeat = False
        while any(pos[i] < len(fpOld[i]) for i in [0, 1]):
            if iSide == 0 and pos[iSide] == len(fpOld[iSide]):
                iSide = 1
            elif iSide == 1 and pos[iSide] == len(fpOld[iSide]):
                iSide = 0
            if iSide == 0 and\
               fpOld[iSide][pos[iSide]].glossType == GLOSS_NEXT_FLEX:
                pos[iSide] += 1
                iSide = 1
                continue
            elif iSide == 1 and fpOld[iSide][pos[iSide]].flex == '.':
                if fpOld[iSide][pos[iSide]].glossType == GLOSS_STEM_FORCED:
                    bStemForcedRepeat = True
                if pos[1] == 0:  # and not pos[0] == 1:
                    pos[iSide] += 1
                    continue
                pos[iSide] += 1
                iSide = 0
                continue
            elif fpOld[iSide][pos[iSide]].glossType == GLOSS_STARTWITHSELF:
                pos[iSide] += 1
                continue
            fp = InflexionPart(fpOld[iSide][pos[iSide]].flex,
                               fpOld[iSide][pos[iSide]].gloss,
                               fpOld[iSide][pos[iSide]].glossType)
            if not bStemStarted and fp.glossType == GLOSS_IFX:
                fp.glossType = GLOSS_AFX
            elif fp.glossType in [GLOSS_STEM, GLOSS_STEM_FORCED, GLOSS_EMPTY]:
                if bStemForcedRepeat or fp.glossType == GLOSS_STEM_FORCED:
                    fp.glossType = GLOSS_STEM_FORCED
                    bStemForcedRepeat = False
                elif not bStemStarted:
                    fp.glossType = GLOSS_STEM
                else:
                    fp.glossType = GLOSS_EMPTY
                bStemStarted = True
            elif fp.glossType in [GLOSS_REDUPL_L, GLOSS_REDUPL_R]:
                bStemStarted = True
            elif bStemStarted and fp.glossType == GLOSS_AFX:
                fp.glossType = GLOSS_IFX
            pos[iSide] += 1
            fpNew.append(fp)
        return flexPartsL[:-1] + [fpNew] + flexPartsR[1:]

    @classmethod
    def join_reduplications(cls, flexL, flexR):
        """Add the reduplications of flexR to those of flexL."""
        if len(flexR.reduplications) == 0:
            return
        cls.renumber_reduplications(flexL, flexR)
        flexL.reduplications.update(flexR.reduplications)

    @classmethod
    def renumber_reduplications(cls, flexL, flexR):
        """Renumber the reduplications in flexR."""
        if len(flexL.reduplications) <= 0 or\
           len(flexR.reduplications) <= 0:
            return
        maxReduplNumL = max(flexL.reduplications.keys())
        dictNewReduplR = {}
        for (k, v) in flexR.reduplications.items():
            dictNewReduplR[k + 1 + maxReduplNumL] = v
        flexR.reduplications = dictNewReduplR
        for fps in flexR.flexParts:
            for fp in fps:
                if fp.glossType in [GLOSS_REDUPL_R, GLOSS_REDUPL_L]:
                    try:
                        m = re.search('^\\[~([^\\[\\]]*)\\]$',
                                      fp.flex)
                        reduplNum = int(m.group(1)) + 1 + maxReduplNumL
                        fp.flex = '[~' + str(reduplNum) + ']'
                    except:
                        cls.raise_error('Wrong reduplication: ', fp.flex)

    def fork_redupl(self, sublex):
        """
        Write a reduplication-free version of self to the grammar
        if needed. Return the name of the paradigm.
        """
        if not self.containsReduplications:
            if self.name not in grammar.Grammar.paradigms:
                grammar.Grammar.paradigms[self.name] = copy.deepcopy(self)
            return self.name
        newPara = copy.deepcopy(self)
        reduplParts = []
        for flex in newPara.flex:
            reduplParts += flex.simplify_redupl(sublex)
        if len(reduplParts) > 0:
            newPara.name += '~' + '~'.join(reduplParts)
        newPara.containsReduplications = False
        if newPara.name not in grammar.Grammar.paradigms:
            grammar.Grammar.paradigms[newPara.name] = newPara
        return newPara.name

    def fork_regex(self, sublex):
        """
        Write a regex-free version of self to the grammar if needed.
        Return the name of the paradigm.
        """
        if self.regexTests is None:
            self.build_regex_tests()
        if len(self.regexTests) == 0:
            if self.name not in grammar.Grammar.paradigms:
                grammar.Grammar.paradigms[self.name] = copy.deepcopy(self)
            return self.name

        testResult = self.perform_regex_tests(sublex)
        newParaName = self.name + '=' + str(testResult)
        if newParaName in grammar.Grammar.paradigms:
            return newParaName
        
        # If there is no such paradigm, make it:
        newPara = copy.deepcopy(self)
        testResult = 0
        flex2remove = set()
        for rtKey in sorted(newPara.regexTests):
            result = lexeme.check_for_regex(sublex,
                                            newPara.regexTests[rtKey][0],
                                            self.errorHandler)
            if not result:
                flex2remove |= newPara.regexTests[rtKey][1]
            testResult = testResult * 2 + int(result)
        for iFlex in sorted(flex2remove, reverse=True):
            newPara.flex.pop(iFlex)
        newPara.name = newParaName
        newPara.regexTests = {}
        for flex in newPara.flex:
            flex.regexTests = []
        grammar.Grammar.paradigms[newParaName] = newPara
        return newParaName

    def perform_regex_tests(self, sublex):
        testResult = 0
        for rtKey in sorted(self.regexTests):
            result = lexeme.check_for_regex(sublex,
                                            self.regexTests[rtKey][0],
                                            self.errorHandler)
            testResult = testResult * 2 + int(result)
        return testResult
