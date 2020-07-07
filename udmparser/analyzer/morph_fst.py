import re
import grammar


class MorphFSTState:
    lastID = 0  # each instance has its own unique id

    def __init__(self, loopState=False, obj=None):
        """
        Initialize a state. If it can be final, obj should
        equal the list of objects (stem or affix) which the transducer
        should write as its output.
        loopState is True if it has a loop with a star over it.
        """
        self.obj = None
        if obj is not None:
            self.obj = [obj]
        self.loopState = loopState
        self.id = MorphFSTState.lastID + 1
        MorphFSTState.lastID += 1

    def add_obj(self, obj):
        try:
            if obj not in self.obj:
                self.obj.append(obj)
        except TypeError:
            self.obj = [obj]

    def __repr__(self):
        sLoop = ''
        if self.loopState:
            sLoop = '∞'
        if self.obj is None:
            return '(' + str(self.id) + sLoop + ')'
        return '{{' + str(self.id) + sLoop + '}}'

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return self.id == other.id

    def __ne__(self, other):
        return self.id != other.id

    def __lt__(self, other):
        return self.id < other.id

    def __gt__(self, other):
        return self.id > other.id

    def __le__(self, other):
        return self.id <= other.id

    def __ge__(self, other):
        return self.id >= other.id


class MorphFST:
    """
    Finite state transducer to be used for stem lookup and
    possible affixes lookup within one paradigm.
    It is non-deterministic in that it can contain empty
    transitions.
    """
    emptyStemCharacters = {'|', '[', ']'}
    rxEmptyStemChars = re.compile('[\\[\\]|¦]')
    rxEmptyIncorpStemChars = re.compile('[\\[\\]|¦.]')
    rxEmptyAffixChars = re.compile('^<[0-9,]+>|[\\[\\]|¦<>0]')
    rxMultipleDots = re.compile('(?:\\[\\.\\]|\\.){2,}')
    rxAfxLeadingDot = re.compile('^(?:<[0-9,]*>)?\\.(?![0.\\[|¦])')

    def __init__(self, verbose=0, det=False):
        self.transitions = {}
        self.startState = MorphFSTState()
        self.verbose = verbose
        self.det = det

    @staticmethod
    def prepare_stem(stem):
        """
        Remove all unnecessary information from the stem
        before adding it to the FST.
        """
        stem = MorphFST.rxEmptyStemChars.sub('', stem)
        stem = MorphFST.rxMultipleDots.sub('.', stem)
        if len(grammar.Grammar.derivations) > 0:
            if not stem.startswith('.'):
                stem = '.' + stem
            if not stem.endswith('.'):
                stem += '.'
        return stem

    @staticmethod
    def prepare_incorp_stem(stem):
        """
        Remove all unnecessary information from the incorporated stem
        before adding it to the FST.
        """
        # we do not need any further slots in incorporated stems
        stem = MorphFST.rxEmptyIncorpStemChars.sub('', stem) + '.'
        return stem

    @staticmethod
    def prepare_affix(afx):
        """
        Remove all unnecessary information from the affix
        before adding it to the FST.
        """
        afx = MorphFST.rxAfxLeadingDot.sub('', afx)
        afx = MorphFST.rxEmptyAffixChars.sub('', afx)
        afx += '.'
        afx = MorphFST.rxMultipleDots.sub('.', afx)
        # print(afx)
        return afx

    def get_next_states_strict(self, curState, curChar):
        try:
            return self.transitions[(curState, curChar)]
        except KeyError:
            return []

    def get_next_states(self, curState, curChar):
        try:
            resultStrict = self.transitions[(curState, curChar)]
        except KeyError:
            resultStrict = []
        resultNonstrict = []
        resultLoop = []
        if curState.loopState:
            if not self.det or len(resultStrict) <= 0:
                resultLoop.append(curState)
        if not self.det and (curState, '') in self.transitions:
            resultNonstrict += self.transitions[(curState, '')]
        return resultStrict, resultNonstrict, resultLoop

    def add_transition(self, curState, curChar, nextState):
        try:
            self.transitions[(curState, curChar)].append(nextState)
        except KeyError:
            self.transitions[(curState, curChar)] = [nextState]

    def add_string(self, s, obj):
        """
        Add a string s (representing either a stem or an affix)
        to the transducer. obj is the transducer's output given
        that string.
        Return number of states added during the operation.
        """
        curState = self.startState
        statesAdded = 0     # just for the record
        if self.verbose > 1:
            print('Starting', s, '...')
        for i in range(len(s)):
            c = s[i]
            if self.verbose > 1:
                print('Current character:', c, ', current state:', curState)
            if c == '.':
                if i == len(s) - 1:
                    curState.add_obj(obj)
                nextStates = self.get_next_states_strict(curState, '')
                if len(nextStates) != 1\
                        or not nextStates[0].loopState:
                    nextState = MorphFSTState(loopState=True)
                    self.add_transition(curState, '', nextState)
                    curState = nextState
                    statesAdded += 1
                else:
                    curState = nextStates[0]
            else:
                nextStates = self.get_next_states_strict(curState, c)
                if len(nextStates) != 1 or nextStates[0].loopState:
                    nextState = MorphFSTState()
                    self.add_transition(curState, c, nextState)
                    curState = nextState
                    statesAdded += 1
                else:
                    curState = nextStates[0]
        curState.add_obj(obj)
        return statesAdded

    def add_stem(self, sl):
        """
        Add a SubLexeme object to the transducer.
        """
        stem = self.prepare_stem(sl.stem)
        statesAdded = self.add_string(stem, sl)
        if self.verbose > 0:
            print('stem:', sl.stem, ';', statesAdded, 'states added.')

    def add_incorp_stem(self, sl):
        """
        Add a SubLexeme object representing an incorporation stem
        to the transducer.
        """
        stem = self.prepare_incorp_stem(sl.stem)
        statesAdded = self.add_string(stem, sl)
        if self.verbose > 0:
            print('incorporation stem:', sl.stem, ';', statesAdded, 'states added.')

    def add_affix(self, infl):
        """
        Add an Inflection object to the transducer.
        """
        infl.rebuild_value()
        afx = self.prepare_affix(infl.flex)
        statesAdded = self.add_string(afx, infl)
        if self.verbose > 0:
            print('inflexion:', infl.flex, ';', statesAdded, 'states added.')

    def get_reachable_states(self, states, usedStates=None):
        """
        Find all states reachable from the given state by empty arcs.
        """
        if usedStates is None:
            usedStates = set(st for st in states)
        reachableStates = set()
        for st, c in self.transitions:
            if c == '' and st in states:
                for stTo in self.transitions[(st, c)]:
                    if stTo not in usedStates:
                        reachableStates.add(stTo)
        if len(reachableStates) <= 0:
            return states
        result = states | reachableStates
        result |= self.get_reachable_states(reachableStates,
                                            usedStates | reachableStates)
        return result

    def det_follow_transitions(self, detFst, curStates, curStateDet, usedIds):
        """
        Add new states and transitions to the determinized FST,
        starting from the states corresponding to curStateDet.
        Return the number of states added to the determinized FST.
        """
        if curStateDet.id in usedIds:
            return 0
        usedIds.add(curStateDet.id)
        statesAdded = 0
        dictReachableStates = {}    # character -> {old states}
        for st, c in self.transitions:
            if c != '' and st.id in curStateDet.id:
                try:
                    dictReachableStates[c] |= set(self.transitions[(st, c)])
                except KeyError:
                    dictReachableStates[c] = set(self.transitions[(st, c)])
        for c in dictReachableStates:
            newStateDet = MorphFSTState()
            statesAdded += 1
            if curStateDet.loopState:
                dictReachableStates[c] |= curStates
            dictReachableStates[c] = self.get_reachable_states(dictReachableStates[c])
            if any(st.loopState for st in dictReachableStates[c]):
                newStateDet.loopState = True
            ids = [st.id for st in dictReachableStates[c]]
            # if curStateDet.loopState:
            #     ids += list(curStateDet.id)
            newStateDet.id = tuple(i for i in sorted(set(ids)))
            for st in dictReachableStates[c]:
                if st.obj is not None:
                    for o in st.obj:
                        newStateDet.add_obj(o)
            detFst.transitions[(curStateDet, c)] = [newStateDet]
            statesAdded += self.det_follow_transitions(detFst, dictReachableStates[c],
                                                       newStateDet, usedIds)
        return statesAdded

    def determinize(self):
        """
        Return a determinized version of self. Note that the
        number of states may grow exponentially and there is
        no minimization.
        """
        if self.verbose > 0:
            print('Determinizing the FST...')
        detFst = MorphFST(verbose=self.verbose, det=True)
        seedState = {self.startState}
        startStates = self.get_reachable_states(seedState)
        detFst.startState.id = tuple(st.id for st in sorted(set(startStates)))
        if any(st.loopState for st in startStates):
            detFst.startState.loopState = True
        for st in startStates:
            if st.obj is not None:
                for o in st.obj:
                    detFst.startState.add_obj(o)
        statesAdded = 1 + self.det_follow_transitions(detFst, startStates,
                                                      detFst.startState, set())
        if self.verbose > 0:
            print('Finished determinizing:', statesAdded, 'states in the new FST.')
        return detFst

    def transduce(self, token, startChar=0, startState=None,
                  objStart=0, objEnd=-1):
        """
        Return all objects the transducer can write as its output
        when given token as its input.
        """
        result = []
        if objEnd == -1:
            objEnd = len(token) - 1
        curState = startState
        if curState is None:
            curState = self.startState
        i = startChar
        if i <= len(token) - 1:
            nextStStrict, nextStNonstrict, nextStLoop = self.get_next_states(curState, token[i])
            if len(nextStStrict) <= 0 and len(nextStNonstrict) <= 0\
                    and len(nextStLoop) <= 0:
                return []
            for st in nextStStrict:
                curObjEnd = objEnd
                if curObjEnd >= i:
                    curObjEnd = i + 1
                result += self.transduce(token, i + 1, st, objStart, curObjEnd)
            for st in nextStNonstrict:
                curObjEnd = objEnd
                if curObjEnd >= i:
                    curObjEnd = i - 1
                result += self.transduce(token, i, st, objStart, curObjEnd)
            for st in nextStLoop:
                curObjStart = objStart
                curObjEnd = objEnd
                if curObjStart < i < curObjEnd:
                    curObjEnd = i
                elif curObjStart == i:
                    curObjStart = i + 1
                    curObjEnd = i + 1
                elif curObjEnd == i:
                    curObjEnd -= 1
                result += self.transduce(token, i + 1, st, curObjStart, curObjEnd)
        elif curState.obj is not None:
            result += [(objStart, objEnd, obj) for obj in curState.obj]
        return result

    def __repr__(self):
        result = '****  FST  ****\n'
        result += ' --> ' + str(self.startState) + '\n'
        for rule in sorted(self.transitions):
            result += str(rule[0]) + ' --[' + rule[1] + ']--> ' +\
                str(self.transitions[rule]) + '\n'
        return result
