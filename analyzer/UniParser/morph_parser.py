import re
import copy
import grammar
import paradigm
import wordform
import clitic
import morph_fst
import time


class ParseState:
    def __init__(self, wf, sl, wfCorrStart, stemCorrStart, corrLength,
                 inflLevels=None, curLevel=-1, curStemPos=0, curPos=0,
                 derivsUsed=None, nextInfl=None, paraLink=None):
        self.wf = wf
        self.sl = sl
        self.wfCorrStart = wfCorrStart
        self.stemCorrStart = stemCorrStart
        self.corrLength = corrLength
        self.curStemPos = curStemPos
        self.curPos = curPos
        if inflLevels is None:
            self.inflLevels = []
        else:
            self.inflLevels = [copy.copy(il) for il in inflLevels]
        self.curLevel = curLevel
        if nextInfl is not None:
            self.inflLevels.append({'curInfl': nextInfl, 'paraLink': paraLink,
                                    'curPart': 0, 'curPos': 0})
        if derivsUsed is None:
            self.derivsUsed = []
        else:
            self.derivsUsed = copy.copy(derivsUsed)

    def __repr__(self):
        if self.curLevel == -1:
            offset = '> '
        else:
            offset = '  '
        offset += ' ' * (self.wfCorrStart - len(re.search('^[.<>]*', self.sl.stem).group(0)))
        res = self.wf + '\n'
        res += ' ' * self.curPos + '^\n'
        res += offset + self.sl.stem + '\n'
        res += offset + ' ' * self.curStemPos + '^\n'
        for iLevel in range(len(self.inflLevels)):
            inflLevel = self.inflLevels[iLevel]
            res += '-----------------\n'
            if iLevel == self.curLevel:
                offset = '> '
            else:
                offset = '  '
            res += offset
            for fp in inflLevel['curInfl'].flexParts[0]:
                res += fp.flex + ' '
            res += '\n' + offset
            for i in range(len(inflLevel['curInfl'].flexParts[0])):
                if i >= inflLevel['curPart']:
                    break
                res += ' ' * len(inflLevel['curInfl'].flexParts[0][i].flex) + ' '
            res += ' ' * inflLevel['curPos'] + '^'
            res += '\n'
        return res


class Parser:
    MAX_STEM_START_LEN = 6
    MAX_EMPTY_INFLEXIONS = 2
    MAX_TOKEN_LENGTH = 512   # to avoid stack overflow in FST recursion
    REMEMBER_PARSES = False  # useless if parsing a frequency list

    rxFirstNonEmptyPart = re.compile('^(.*?)([^ .()\\[\\]<>|~]{1,' + str(MAX_STEM_START_LEN) +
                                     '})')
    inflStarts = ('<', '[')
    rxCleanToken = re.compile('^[-=<>\\[\\]/():;.,_!?*]+|[-=<>\\[\\]/():;.,_!?*]+$')
    rxTokenSearch = re.compile('^([^\\w]*)' +
                               '([0-9,.\\-%]+|'
                               '[\\w\\-\'`´‘’‛/@.,]+?)'
                               '([^\\w]*)$')

    def __init__(self, verbose=0, parsingMethod='fst', errorHandler=None):
        if errorHandler is None:
            errorHandler = grammar.Grammar.errorHandler
        self.errorHandler = errorHandler
        self.verbose = verbose
        self.parsingMethod = parsingMethod  # 'hash' or 'fst'
        wordform.Wordform.verbosity = self.verbose
        self.wfs = {}    # list of wordforms stored in memory
                         # wordform -> [possible Wordform objects]
        self.stemStarters = {}   # letter -> [subLexemes whose firt non-empty
                                 # part starts with that letter]
                                 # (used with 'hash' parsing method)
        self.stemFst = morph_fst.MorphFST(self.verbose)  # (used with 'fst' parsing method)
        self.incorpFst = morph_fst.MorphFST(self.verbose)
        self.paradigmFsts = {}   # paradigm_name -> FST for its affixes
                                 # (used with 'fst' parsing method)
        self.dictParses = {}        # token -> [possible Wordform objects]

    def raise_error(self, message, data=None):
        if self.errorHandler is None:
            self.errorHandler = grammar.Grammar.errorHandler
        self.errorHandler.raise_error(message, data)

    def print_stem_starters(self):
        if self.verbose > 0:
            print('Filling stem starters dictionary complete.')
        if self.verbose > 1:
            for start in self.stemStarters:
                print('\n*** ' + start + ' ***')
                for sl in self.stemStarters[start]:
                    print(sl)
            print('***************\n')

    def add_all_wordforms(self, lexeme):
        """
        Add all the wordforms of a given lexeme to the
        list of pre-generated wordforms.
        """
        for wf in lexeme.generate_wordforms():
            try:
                self.wfs[wf.wf].append(wf)
            except KeyError:
                self.wfs[wf.wf] = [wf]

    def fill_stem_dicts(self):
        """
        Prepare hash table with the stems ('hash' parsing method)
        """
        for l in grammar.Grammar.lexemes:
            curStemStarters = {}
            for sl in l.subLexemes:
                m = self.rxFirstNonEmptyPart.search(sl.stem)
                if m is None:
                    # if there are no letters in the stem,
                    # generate all possible wordforms
                    self.add_all_wordforms(l)
                    curStemStarters = {}
                    break
                try:
                    curStemStarters[m.group(2)].append(sl)
                except KeyError:
                    curStemStarters[m.group(2)] = [sl]
            for (start, sl) in curStemStarters.items():
                try:
                    self.stemStarters[start] += sl
                except KeyError:
                    self.stemStarters[start] = sl
        self.print_stem_starters()

    def fill_stem_fst(self):
        """
        Prepare FST with the stems ('fst' parsing method)
        """
        for l in grammar.Grammar.lexemes:
            for sl in l.subLexemes:
                m = self.rxFirstNonEmptyPart.search(sl.stem)
                if m is None:
                    # if there are no letters in the stem,
                    # generate all possible wordforms
                    self.add_all_wordforms(l)
                    break
                self.stemFst.add_stem(sl)

    def fill_incorporated_stem_fst(self):
        """
        Prepare FST with the incorporation versions of the stems.
        """
        for l in grammar.Grammar.lexemes:
            for sl in l.subLexemes:
                if not sl.noIncorporation:
                    m = self.rxFirstNonEmptyPart.search(sl.stem)
                    if m is not None:
                        self.incorpFst.add_incorp_stem(sl)

    def fill_stems(self):
        """
        Add stems from all the sublexemes in the Grammar to the
        FST or the hash tables, depending on the current parsing
        method.
        This is a necessary preliminary step before the analysis
        begins. Usually it takes up to 10 seconds to complete.
        """
        if self.parsingMethod == 'fst':
            self.fill_stem_fst()
        elif self.parsingMethod == 'hash':
            self.fill_stem_dicts()
        else:
            self.raise_error('Unable to fill stems because the parsing method ' +
                             self.parsingMethod + ' is not supported.')
        self.fill_incorporated_stem_fst()

    def make_paradigm_fst(self, para):
        """
        Return an FST made from all affixes of the paradigm.
        """
        fst = morph_fst.MorphFST(verbose=self.verbose)
        for infl in para.flex:
            fst.add_affix(infl)
        # fst = fst.determinize()
        return fst

    def fill_affixes(self):
        """
        Add affixes from all paradigms to the FSTs. This step is
        necessary only when parsing method is set to 'fst'.
        """
        for p in grammar.Grammar.paradigms:
            if self.verbose > 1:
                print('Making an FST for', p, '...')
            para = grammar.Grammar.paradigms[p]
            self.paradigmFsts[p] = self.make_paradigm_fst(para)
        if self.verbose > 0:
            print('Created FSTs for', len(self.paradigmFsts), 'paradigms.')

    @staticmethod
    def is_bad_analysis(wf):
        """
        Check if the given analysis is not in the list of bad analyses
        in the Grammar.
        """
        for badAna in grammar.Grammar.badAnalyses:
            bAnalysisConforms = True
            for k, v in badAna.items():
                try:
                    realValue = wf.__dict__[k]
                    if v.search(realValue) is None:
                        bAnalysisConforms = False
                        break
                    # print(v.pattern, k)
                except KeyError:
                    bAnalysisConforms = False
                    break
            if bAnalysisConforms:
                return True
        return False

    def inflexion_may_conform(self, state, infl):
        for fp in infl.flexParts[0]:
            if fp.glossType in [paradigm.GLOSS_EMPTY,
                                paradigm.GLOSS_STEM,
                                paradigm.GLOSS_STEM_FORCED,
                                paradigm.GLOSS_STARTWITHSELF]:
                continue
            if fp.flex == '<.>':
                continue
            if fp.flex not in state.wf[state.curPos:]:
                return False
            return True
        return True

    def inflexion_is_good(self, state, infl, findDerivations=False):
        """
        Check if the inflexion infl could be part of the word,
        given the current state. If findDerivations is True, search
        only for inflexions starting with GLOSS_STARTWITHSELF.
        """
        if len(infl.flexParts) <= 0 or len(infl.flexParts[0]) <= 0:
            return False
        if findDerivations and infl.flexParts[0][0].glossType != paradigm.GLOSS_STARTWITHSELF:
            return False
        if self.infl_count(state, infl) >= grammar.Grammar.RECURS_LIMIT:
            return False
        for fp in infl.flexParts[0]:
            if fp.glossType == paradigm.GLOSS_EMPTY or len(fp.flex) <= 0:
                continue
            else:
                if fp.flex == '<.>' or fp.glossType in [paradigm.GLOSS_STEM,
                                                        paradigm.GLOSS_STEM_FORCED]:
                    if self.inflexion_may_conform(state, infl):
                        return True
                    else:
                        return False
                if state.curPos >= len(state.wf):
                    return False
                # if not fp.flex.startswith(state.wf[state.curPos]):
                if not fp.flex == state.wf[state.curPos:state.curPos + len(fp.flex)]:
                    return False
                return True
        return True

    def empty_depth(self, state):
        """
        Calculate how many empty inflexions are used in the state.
        """
        emptyDepth = 0
        for level in range(len(state.inflLevels)):
            infl = state.inflLevels[level]['curInfl']
            if (len(infl.flexParts) <= 0 or len(infl.flexParts[0]) <= 0 or
                    (len(infl.flexParts[0]) == 1 and len(infl.flexParts[0][0].flex) <= 0)) and\
                     len(infl.subsequent) > 0:
                emptyDepth += 1
        return emptyDepth

    def infl_count(self, state, infl):
        """
        Count how many times given inflexion has been used in the state.
        """
        inflCount = 0
        for level in range(len(state.inflLevels)):
            curInfl = state.inflLevels[level]['curInfl']
            if curInfl == infl:
                inflCount += 1
        return inflCount

    def find_inflexions_fst(self, state, paraName, findDerivations=False, emptyDepth=0):
        try:
            paraFst = self.paradigmFsts[paraName]
        except KeyError:
            self.raise_error('No FST for the paradigm ' + paraName)
            para = grammar.Grammar.paradigms[paraName]
            return self.find_inflexions_simple(state, para,
                                               findDerivations, emptyDepth)
        # print(state.wf, state.curPos)
        # print(paraFst)
        startChar = objStart = state.curPos
        if state.curPos == state.wfCorrStart:
            startChar = objStart = state.wfCorrStart + state.corrLength
        suitableInfl = paraFst.transduce(state.wf, startChar=startChar,
                                         objStart=objStart)
        result = []
        # print('Looking for:', state.wf, state.curPos, startChar)
        # print('paradigm:', paraName, '\n***\n',
        #       u'\n----\n'.join(f.flex for f in grammar.Grammar.paradigms[paraName].flex))
        # print(paraFst)
        for inflStart, inflEnd, infl in suitableInfl:
            # print(inflStart, inflEnd, infl)
            if findDerivations and len(infl.flexParts) > 0 and\
                            len(infl.flexParts[0]) > 0 and\
                            infl.flexParts[0][0].glossType != paradigm.GLOSS_STARTWITHSELF:
                continue
            elif self.infl_count(state, infl) >= grammar.Grammar.RECURS_LIMIT:
                continue
            elif (len(infl.flexParts) <= 0 or len(infl.flexParts[0]) <= 0 or
                  (len(infl.flexParts[0]) == 1 and len(infl.flexParts[0][0].flex) <= 0)) and\
                  len(infl.subsequent) > 0:
                for sp in infl.subsequent:
                    result += self.find_inflexions(state, sp.name,
                                                   emptyDepth=emptyDepth + 1,
                                                   findDerivations=findDerivations)
            else:
                result.append((infl, paraName))
        # print('found:', [str(f[0]) for f in result])
        return result

    def find_inflexions_simple(self, state, para, findDerivations=False, emptyDepth=0):
        result = []
        for infl in para.flex:
            if self.inflexion_is_good(state, infl, findDerivations=findDerivations):
                result.append((infl, para.name))
            if (len(infl.flexParts) <= 0 or len(infl.flexParts[0]) <= 0 or
                (len(infl.flexParts[0]) == 1 and len(infl.flexParts[0][0].flex) <= 0)) and\
                 len(infl.subsequent) > 0:
                for sp in infl.subsequent:
                    result += self.find_inflexions(state, sp.name,
                                                   emptyDepth=emptyDepth + 1,
                                                   findDerivations=findDerivations)
        return result

    def find_inflexions(self, state, paraName, findDerivations=False, emptyDepth=0):
        if emptyDepth <= 0:
            emptyDepth = self.empty_depth(state)
        if emptyDepth > self.MAX_EMPTY_INFLEXIONS:
            return []
        if (len(state.derivsUsed) >= grammar.Grammar.MAX_DERIVATIONS and
            '#deriv' in paraName):
            return []
        try:
            para = grammar.Grammar.paradigms[paraName]
        except KeyError:
            self.raise_error('Wrong paradigm name: ' + paraName)
            return []
        if self.parsingMethod == 'hash':
            return self.find_inflexions_simple(state, para, findDerivations, emptyDepth)
        elif self.parsingMethod == 'fst':
            return self.find_inflexions_fst(state, paraName, findDerivations, emptyDepth)
        return []

    def get_wordforms(self, state):
        """
        Look at the state after the loop has been finished. Check if
        the combination of stem and affixes found during the loop can
        indeed result into the wordform. Return a list of Wordform objects
        representing all possible analyses.
        """
        # check if some part of the word was not used or no inflexions were used
        if state.curPos < len(state.wf) or len(state.inflLevels) <= 0:
            return None
        # check if not the whole stem was used
        if state.curStemPos < len(state.sl.stem):
            for i in range(state.curStemPos, len(state.sl.stem)):
                if state.sl.stem[i] != '.':
                    return None
        # check if the lowest level contains an inflexion that requires continuation
        lastInfl = state.inflLevels[-1]['curInfl']
        if (lastInfl.position != paradigm.POS_NONFINAL and
                any(fp.flex == '<.>' for fp in lastInfl.flexParts[0])):
            return None
        # check if inflexions at all levels have been finished
        for inflLevel in state.inflLevels:
            if inflLevel['curPart'] < len(inflLevel['curInfl'].flexParts[0]):
                for iPos in range(inflLevel['curPos'] + 1,
                                  len(inflLevel['curInfl'].flexParts[0][inflLevel['curPart']].flex)):
                    if inflLevel['curInfl'].flexParts[0][inflLevel['curPart']].flex[iPos] not in '.<>[]~|':
                        # print('NONE')
                        return None
                for iPart in range(inflLevel['curPart'] + 1, len(inflLevel['curInfl'].flexParts[0])):
                    if inflLevel['curInfl'].flexParts[0][inflLevel['curPart']].glossType not in\
                        [paradigm.GLOSS_STEM, paradigm.GLOSS_STEM_FORCED,
                         paradigm.GLOSS_STARTWITHSELF] and\
                            len(inflLevel['curInfl'].flexParts[0][inflLevel['curPart']].flex) > 0:
                        # print(inflLevel['curInfl'].flexParts[0][inflLevel['curPart']].flex)
                        return None
        infl = copy.deepcopy(state.inflLevels[0]['curInfl'])
        for iLevel in range(1, len(state.inflLevels)):
            curLevel = state.inflLevels[iLevel]
            paradigm.Paradigm.join_inflexions(infl, copy.deepcopy(curLevel['curInfl']),
                                              curLevel['paraLink'])
        if infl is None:
            return None
        wf = wordform.Wordform(state.sl, infl)
        if wf is None or wf.wf != state.wf:
            return None
        if self.verbose > 0:
            print(state)
        return [wf]

    def continue_loop(self, state):
        """
        Determine if, given the current state, the investigation loop
        has to be continued.
        """
        if state.curPos < len(state.wf):
            return True
        if len(state.inflLevels) <= 0 and (state.curStemPos >= len(state.sl.stem) or
                                           state.sl.stem[state.curStemPos] == '.'):
            return True
        if len(state.inflLevels) <= 0:
            return False
        curPart = state.inflLevels[-1]['curPart']
        curInflPos = state.inflLevels[-1]['curPos']
        curInfl = state.inflLevels[-1]['curInfl']
        if curPart < len(curInfl.flexParts[0]) and\
           (curInflPos >= len(curInfl.flexParts[0][curPart].flex) or
            ((state.curStemPos < len(state.sl.stem) or state.sl.stem.endswith('.')) and
             curInfl.flexParts[0][curPart].glossType in [paradigm.GLOSS_STEM,
                                                         paradigm.GLOSS_STEM_FORCED,
                                                         paradigm.GLOSS_STARTWITHSELF]) or
            curInfl.flexParts[0][curPart].flex == '<.>'):
            return True
        return False

    def swicth_to_upper_level(self, state):
        """
        Determine if, given the current state, the investigation loop
        should go one level up, switching to the stem or the previous
        inflexion in the stack. Should be called when current part of
        the inflexion is "." or "[.]".
        """
        curPart = state.inflLevels[state.curLevel]['curPart']
        curInfl = state.inflLevels[state.curLevel]['curInfl']
        if curPart >= len(curInfl.flexParts[0]) or\
           curInfl.flexParts[0][curPart].flex not in ['.', '[.]']:
            return False
        if curInfl.flexParts[0][0].glossType == paradigm.GLOSS_STARTWITHSELF:
            if curPart > 1 or (state.curStemPos < 2 and state.sl.stem.startswith('.')):
                return True
            return False
        if curPart == 0 and state.curLevel > 0 and\
                state.inflLevels[state.curLevel - 1]['curPart'] == 1 and\
                state.inflLevels[state.curLevel - 1]['curInfl'].flexParts[0][1].flex == '<.>':
            return False
        if curPart != 0 or (state.curLevel == 0
                            and state.curStemPos < 2 and state.sl.stem.startswith('.')):
            return True
        return False

    def investigate_state(self, state):
        while self.continue_loop(state):
            if self.verbose > 1:
                print(state)
                time.sleep(0.2)
            if state.curLevel == -1:    # level of the stem
                if state.curStemPos >= len(state.sl.stem):
                    if self.verbose > 1:
                        print('Stem ended unexpectedly.')
                    return []
                if state.sl.stem[state.curStemPos] == '.':
                    curLevel = 0
                    state.curStemPos += 1
                    if len(state.inflLevels) > 0:
                        state.curLevel = 0
                        continue
                    else:
                        resultingStates = []
                        for infl, para in self.find_inflexions(state, state.sl.paradigm):
                            # print(infl)
                            newDerivsUsed = []
                            if '#deriv' in para:
                                newDerivsUsed = [para]
                            newState = ParseState(state.wf, state.sl, state.wfCorrStart,
                                                  state.stemCorrStart, state.corrLength,
                                                  state.inflLevels, curLevel, state.curStemPos,
                                                  state.curPos, state.derivsUsed + newDerivsUsed,
                                                  infl)
                            resultingStates += self.investigate_state(newState)
                        return resultingStates
                elif state.curStemPos == 0 and len(state.inflLevels) <= 0:
                    # find derivational inflexions
                    resultingStates = []
                    if self.verbose > 1:
                        print('Looking for derivational inflexions...')
                    for infl, para in self.find_inflexions(state, state.sl.paradigm, findDerivations=True):
                        newDerivsUsed = []
                        if '#deriv' in para:
                            newDerivsUsed = [para]
                        newState = ParseState(state.wf, state.sl, state.wfCorrStart,
                                              state.stemCorrStart, state.corrLength,
                                              state.inflLevels, 0, state.curStemPos,
                                              state.curPos, state.derivsUsed + newDerivsUsed,
                                              infl)
                        resultingStates += self.investigate_state(newState)
                    if len(resultingStates) > 0:
                        if self.verbose > 1:
                            print(len(resultingStates), 'derivational inflexions found.')
                        if state.wf[state.curPos] == state.sl.stem[state.curStemPos]:
                            newState = ParseState(state.wf, state.sl, state.wfCorrStart,
                                                  state.stemCorrStart, state.corrLength,
                                                  state.inflLevels, -1, state.curStemPos,
                                                  state.curPos, state.derivsUsed)
                            newState.curPos += 1
                            newState.curStemPos += 1
                            resultingStates += self.investigate_state(newState)
                        return resultingStates
                if state.stemCorrStart <= state.curStemPos <\
                                state.stemCorrStart + state.corrLength:
                    if state.curPos != state.wfCorrStart + state.curStemPos -\
                            state.stemCorrStart:
                        return []
                elif state.curPos >= len(state.wf) or\
                     state.curStemPos >= len(state.sl.stem):
                    self.raise_error('Stem or wordform ended unexpectedly: stem=' +
                                     state.sl.stem + ', wf=' + state.wf + '.')
                    return []
                elif state.wf[state.curPos] != state.sl.stem[state.curStemPos]:
                    return []
                state.curPos += 1
                state.curStemPos += 1
            else:
                curPart = state.inflLevels[state.curLevel]['curPart']
                curPos = state.inflLevels[state.curLevel]['curPos']
                curInfl = state.inflLevels[state.curLevel]['curInfl']
                if curPart >= len(curInfl.flexParts[0]):
                    state.curLevel -= 1
                    continue
                fp = curInfl.flexParts[0][curPart]
                # print(fp.flex, curPart, curPos)
                # if curPos > 0 and curPos >= len(fp.flex):
                if fp.flex == '.' or fp.flex == '[.]':
                    bSwicthToUpperLevel = self.swicth_to_upper_level(state)
                    if not (state.curStemPos < 2 and state.sl.stem.startswith('.') and
                            curPart == 0 and state.curPos <= -2):
                        state.inflLevels[state.curLevel]['curPart'] += 1
                        state.inflLevels[state.curLevel]['curPos'] = 0
                    if bSwicthToUpperLevel:
                        state.curLevel -= 1
                    continue
                elif fp.flex == '<.>':
                    curLevel = state.curLevel + 1
                    state.inflLevels[state.curLevel]['curPart'] += 1
                    state.inflLevels[state.curLevel]['curPos'] = 0
                    if len(state.inflLevels) > curLevel:
                        state.curLevel = curLevel
                        continue
                    else:
                        resultingStates = []
                        for pl in curInfl.subsequent:
                            # print(pl.name)
                            for infl, para in self.find_inflexions(state, pl.name):
                                newDerivsUsed = []
                                if '#deriv' in para:
                                    newDerivsUsed = [para]
                                newState = ParseState(state.wf, state.sl, state.wfCorrStart,
                                                      state.stemCorrStart, state.corrLength,
                                                      state.inflLevels, curLevel, state.curStemPos,
                                                      state.curPos, state.derivsUsed + newDerivsUsed, infl, pl)
                                resultingStates += self.investigate_state(newState)
                        return resultingStates
                elif curPos >= len(fp.flex):   # or fp.glossType == paradigm.GLOSS_EMPTY:
                    state.inflLevels[state.curLevel]['curPart'] += 1
                    state.inflLevels[state.curLevel]['curPos'] = 0
                    continue
                else:
                    if curPos >= len(fp.flex) or\
                                    state.curPos >= len(state.wf) or\
                                    fp.flex[curPos] != state.wf[state.curPos]:
                        return []
                    state.curPos += 1
                    state.inflLevels[state.curLevel]['curPos'] += 1
                    continue
        if self.verbose > 1:
            print('End of loop:')
            print(state)
            print('Trying to get a wordform...')
            print('Inflexions:\n' + '---\n'.join(str(l['curInfl']) for l in state.inflLevels))
        wf = self.get_wordforms(state)
        if wf is None:
            return []
        return wf

    def get_hosts(self, word, cliticSide=None):
        """
        Find all possible ways of splitting the word into a host and a clitic.
        Return a list of tuples (Clitic object of None, remaining part of
        the string). If cliticSide is not None, search only for the clitics
        specified by that argument (proclitics or enclitics).
        """
        hostsAndClitics = [(None, word)]
        for cl in grammar.Grammar.clitics:
            if (cl.side == clitic.SIDE_ENCLITIC and
                    cliticSide != clitic.SIDE_PROCLITIC and
                    word.endswith(cl.stem) and
                    len(word) > len(cl.stem)):
                host = word[:-len(cl.stem)]
                if not cl.is_compatible_str(host):
                    continue
                hostsAndClitics.append((cl, host))
            if (cl.side == clitic.SIDE_PROCLITIC and
                    cliticSide != clitic.SIDE_ENCLITIC and
                    word.startswith(cl.stem) and
                    len(word) > len(cl.stem)):
                host = word[len(cl.stem):]
                if not cl.is_compatible_str(host):
                    continue
                hostsAndClitics.append((cl, host))
        return hostsAndClitics

    def find_stems(self, word):
        """
        Find all possible stems in the given token.
        Return a list of corresponding state instances.
        """
        states = []
        if self.parsingMethod == 'hash':
            for l in range(len(word)):
                for r in range(l + 1, min(len(word) + 1, l + self.MAX_STEM_START_LEN + 1)):
                    possibleStem = word[l:r]
                    try:
                        suitableSubLex = self.stemStarters[possibleStem]
                    except KeyError:
                        continue
                    if self.verbose > 0:
                        print('Trying to analyze:', l, r, possibleStem)
                    for sl in suitableSubLex:
                        if self.verbose > 1:
                            print(sl)
                        state = ParseState(word, sl, l, sl.stem.find(possibleStem), r - l)
                        states.append(state)
        elif self.parsingMethod == 'fst':
            suitableSubLex = self.stemFst.transduce(word)
            for l, r, sl in suitableSubLex:
                if self.verbose > 1:
                    print('FST: found a stem, parameters:',
                          l, sl.stem, word[l:r+1], sl.stem.find(word[l:r+1]), r - l + 1)
                state = ParseState(word, sl, l, sl.stem.find(word[l:r+1]), r - l + 1)
                states.append(state)
        return states

    def parse_host(self, word):
        """
        Return a list of Wordform objects, each representing a possible
        analysis of the word string, assuming it has no clitics.
        """
        analyses = []
        if self.verbose > 0:
            print(word, ': start searching for sublexemes...')
        states = self.find_stems(word)
        if self.verbose > 0:
            print('Start investigating states...')
        for state in states:
            analyses += self.investigate_state(state)
        analysesSet = set()
        for ana in analyses:
            if self.is_bad_analysis(ana):
                continue
            enhancedAnas = Parser.apply_lex_rules(ana)
            if len(enhancedAnas) <= 0:
                analysesSet.add(ana)
            else:
                analysesSet |= enhancedAnas
        return analysesSet

    @staticmethod
    def apply_lex_rules(ana):
        possibleEnhancements = set()
        if ana.lemma in grammar.Grammar.lexRulesByLemma:
            for rule in grammar.Grammar.lexRulesByLemma[ana.lemma]:
                newAna = rule.apply(ana)
                if newAna is not None:
                    possibleEnhancements.add(newAna)
        if ana.stem in grammar.Grammar.lexRulesByStem:
            for rule in grammar.Grammar.lexRulesByStem[ana.stem]:
                newAna = rule.apply(ana)
                if newAna is not None:
                    possibleEnhancements.add(newAna)
        return possibleEnhancements

    def parse(self, word, printOut=False):
        """
        Return a list of Wordform objects, each representing a possible
        analysis of the word string.
        """
        analyses = []
        word = Parser.rxCleanToken.sub('', word)
        if self.REMEMBER_PARSES:
            try:
                analyses = self.dictParses[word]
                if self.verbose > 0:
                    print(word, 'was found in the cache.')
                return analyses
            except KeyError:
                pass
        if len(word) <= 0 or len(word) > Parser.MAX_TOKEN_LENGTH:
            return analyses

        if self.verbose > 0:
            print(word, ': start searching for clitics...')
        hostsAndClitics = self.get_hosts(word)
        if self.verbose > 1:
            print(len(hostsAndClitics), 'possible variants of splitting into a host and a clitic.')
        for cl, host in hostsAndClitics:
            hostAnalyses = self.parse_host(host)
            if len(hostAnalyses) <= 0:
                continue
            for wf in hostAnalyses:
                if cl is None:
                    analyses.append(wf)
                elif cl.is_compatible(wf):
                    wf.wf = word
                    wf.lemma += '+' + cl.lemma
                    if len(wf.gramm) > 0 and len(cl.gramm) > 0:
                        wf.gramm += ','
                    wf.gramm += cl.gramm
                    if cl.side == clitic.SIDE_PROCLITIC:
                        wf.gloss = cl.gloss + '=' + wf.gloss
                        wf.wfGlossed = cl.stem + '=' + wf.wfGlossed
                    else:
                        wf.gloss += u'=' + cl.gloss
                        wf.wfGlossed += u'=' + cl.stem
                    analyses.append(wf)
        if printOut:
            if len(analyses) <= 0:
                print(word + ': no possible analyses found.')
            else:
                print(word + ':', len(analyses), 'analyses:\n')
                for ana in analyses:
                    print('****************\n')
                    print(ana)
        if self.REMEMBER_PARSES:
            self.dictParses[word] = analyses
        return analyses

    @staticmethod
    def ana2xml(token, analyses, glossing=False):
        r = '<w>'
        for ana in sorted(set(ana.to_xml(glossing=glossing) for ana in analyses)):
            r += ana
        return r + token + '</w>'

    def parse_freq_list(self, fnameIn, sep=':', fnameParsed='', fnameUnparsed='',
                        maxLines=None, glossing=False):
        """
        Analyze a frequency list of tokens. Write analyses to fnameParsed
        and unanalyzed tokens to fnameUnparsed. Return total number of tokens
        and the rate of the parsed tokens (taking their frequencies into account).
        If maxLines is not None, process only the first maxLines of the
        frequency list.
        """
        if len(fnameParsed) <= 0:
            fnameParsed = fnameIn + '-parsed.txt'
        if len(fnameUnparsed) <= 0:
            fnameUnparsed = fnameIn + '-unparsed.txt'
        try:
            fIn = open(fnameIn, 'r', encoding='utf-8-sig')
            lines = [(x[0].strip(), int(x[1].strip()))
                     for x in [line.split(sep) for line in fIn if len(line) > 2]]
            fIn.close()
        except IOError:
            self.raise_error('The frequency list could not be opened.')
            return 0, 0.0
        except ValueError:
            self.raise_error('Wrong format of the frequency list.')
            return 0, 0.0
        if maxLines is not None:
            lines = lines[:maxLines]
        parsedTokenFreqs = 0
        unparsedTokenFreqs = 0
        fParsed = open(fnameParsed, 'w', encoding='utf-8')
        fUnparsed = open(fnameUnparsed, 'w', encoding='utf-8')
        for (token, freq) in sorted(lines, key=lambda x: (-x[1], x[0])):
            analyses = self.parse(token)
            if len(analyses) <= 0:
                fUnparsed.write(token + '\n')
                unparsedTokenFreqs += freq
            else:
                fParsed.write(Parser.ana2xml(token, analyses, glossing=glossing) + '\n')
                parsedTokenFreqs += freq
        fParsed.close()
        fUnparsed.close()
        return len(lines), parsedTokenFreqs / (parsedTokenFreqs + unparsedTokenFreqs)

    def parse_txt(self, fnameIn, fnameOut='', encoding='utf-8-sig',
                  glossing=False):
        """
        Analyze a text file fnameIn. Write the processed text to fnameOut.
        Return total number of tokens and number of the parsed tokens.
        """
        self.REMEMBER_PARSES = True
        if len(fnameOut) <= 0:
            fnameOut = fnameIn + '-processed.xml'
        try:
            fIn = open(fnameIn, 'r', encoding=encoding)
            text = fIn.read()
            processedText = '<text>\n'
            fIn.close()
        except IOError:
            self.raise_error('The text file ' + fnameIn + ' could not be opened.')
            return 0, 0
        rawTokens = text.split()
        wordsAnalyzed = totalWords = 0
        for token in rawTokens:
            if len(token) <= 0:
                continue
            m = self.rxTokenSearch.search(token)
            processedText += ' '
            if m is None:
                processedText += token
                continue
            puncl = m.group(1)
            wf = m.group(2)
            puncr = m.group(3)
            processedText += puncl
            if len(wf) > 0:
                anas = self.parse(wf.lower())
                if len(anas) > 0:
                    wordsAnalyzed += 1
                processedText += Parser.ana2xml(wf, anas, glossing=glossing)
                totalWords += 1
            processedText += puncr + '\n'
        processedText += '</text>'
        fOut = open(fnameOut, 'w', encoding='utf-8')
        fOut.write(processedText)
        fOut.close()
        return totalWords, wordsAnalyzed
