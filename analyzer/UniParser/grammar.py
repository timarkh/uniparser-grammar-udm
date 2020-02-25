import copy
import json
import re
from ErrorHandler import ErrorHandler
import lexeme
import lex_rule
import clitic
from stem_conversion import StemConversion
import paradigm
import derivations
import periphrastic
import yamlReader


class Grammar:
    """The main class of the project."""

    RECURS_LIMIT = 2            # max number of times every given paradigm
                                # may appear in a wordform
    # paradigm compilation options
    PARTIAL_COMPILE = True      # compile until the following restrictions are met:
    MIN_FLEX_LENGTH = 1         # when PARTIAL_COMPILE is set
    MAX_COMPILE_TIME = 60       # when PARTIAL_COMPILE is set

    DERIV_LIMIT = 5             # counts only non-empty derivands
    FLEX_LENGTH_LIMIT = 20      # max inflexion length (without metacharacters)
    TOTAL_DERIV_LIMIT = 10      # counts everything
    MAX_DERIVATIONS = 2         # how many derivation models can appear in a word

    lexemes = []
    lexRulesByStem = {}
    lexRulesByLemma = {}
    clitics = []
    paradigms = {}         # name -> Paradigm object
    lexByParadigm = {}     # paradigm name -> links to sublexemes which
                           # have that paradigm in the form (lex, subLex)
    stemConversions = {}
    derivations = {}
    badAnalyses = []
    errorHandler = None
    
    def __init__(self, errorHandlerFileName=None, errorHandler=None, verbose=False):
        self.verbose = verbose
        if errorHandler is None:
            if errorHandlerFileName is not None and len(errorHandlerFileName) > 0:
                Grammar.errorHandler = ErrorHandler(filename=errorHandlerFileName)
            else:
                Grammar.errorHandler = ErrorHandler()
        else:
            Grammar.errorHandler = errorHandler
        Grammar.lexemes = []
        Grammar.lexRulesByStem = {}
        Grammar.lexRulesByLemma = {}
        Grammar.clitics = []
        Grammar.paradigms = {}
        Grammar.lexByParadigm = {}
        Grammar.stemConversions = {}
        Grammar.derivations = {}
        Grammar.badAnalyses = []

    @staticmethod
    def raise_error(message, data=None):
        if data is not None:
            data = ': ' + json.dumps(data, ensure_ascii=False)
            if len(data) > 200:
                data = data[:200] + '...'
        else:
            data = ''
        print(message + data)

    def log_message(self, message):
        if self.verbose:
            print(message)

    def load_yaml_descrs(self, fnames):
        """
        Load raw descriptions of lexemes, paradigms or derivations
        from the file or files specified by fnames.
        Return a list of descriptions.
        """
        if type(fnames) == str:
            fnames = [fnames]
        descrs = []
        for fname in fnames:
            descrs += yamlReader.read_file(fname, self.errorHandler)
        return descrs

    def load_stem_conversions(self, fnames):
        """
        Load stem conversion rules from the file or files specified.
        by fnames. Return the number of rules loaded.
        """
        if len(self.lexemes) > 0:
            self.raise_error('Loading stem conversions should occur before '
                             'loading stems.')
            return 0
        conversionDescrs = self.load_yaml_descrs(fnames)
        # self.stemConversions = {}   # {conversion name -> StemConversion}
        for dictSC in conversionDescrs:
            sc = StemConversion(dictSC, self.errorHandler)
            self.stemConversions[sc.name] = sc
        return len(self.stemConversions)

    def load_paradigms(self, fnames, compileParadigms=True):
        """
        Load paradigms from the file or files specified by fnames.
        Return the number of paradigms loaded.
        """
        if len(self.lexemes) > 0:
            self.raise_error('Loading paradigms should occur before '
                             'loading stems.')
            return 0
        paraDescrs = self.load_yaml_descrs(fnames)
        for dictDescr in paraDescrs:
            try:
                Grammar.paradigms[dictDescr['value']] =\
                                  paradigm.Paradigm(dictDescr, self.errorHandler)
            except MemoryError:
                self.raise_error('Not enough memory for the paradigms.')
                return
        if compileParadigms:
            newParadigms = {}
            for pName, p in self.paradigms.items():
                self.log_message('paradigm: ' + pName)
                p = copy.deepcopy(p)
                p.compile_paradigm()
                self.log_message('paradigm ' + pName + ' compiled: ' +
                                 str(len(p.flex)) + ' inflections')
                newParadigms[pName] = p
            Grammar.paradigms = newParadigms
        return len(Grammar.paradigms)

    def load_lexemes(self, fnames):
        """
        Load lexemes from the file or files specified by fnames.
        Return the number of lexemes loaded.
        """
        lexDescrs = self.load_yaml_descrs(fnames)
        for dictDescr in lexDescrs:
            if dictDescr is None or len(dictDescr) <= 0:
                continue
            try:
                self.lexemes.append(lexeme.Lexeme(dictDescr, self.errorHandler))
                if self.verbose:
                    self.log_message('New lexeme: ' + self.lexemes[-1].lemma)
            except MemoryError:
                self.raise_error('Not enough memory for the lexemes.')
                return
        return len(self.lexemes)

    def load_lex_rules(self, fnames):
        """
        Load lexical rules from the file or files specified by fnames.
        Return the number of rules loaded.
        """
        ruleDescrs = self.load_yaml_descrs(fnames)
        for dictDescr in ruleDescrs:
            if dictDescr is None or len(dictDescr) <= 0:
                continue
            try:
                lr = lex_rule.LexRule(dictDescr, self.errorHandler)
                if lr.stem is not None:
                    try:
                        Grammar.lexRulesByStem[lr.stem].append(lr)
                    except KeyError:
                        Grammar.lexRulesByStem[lr.stem] = [lr]
                    if self.verbose:
                        self.log_message('New lexical rule for stem ' + lr.stem)
                elif lr.lemma is not None:
                    try:
                        Grammar.lexRulesByLemma[lr.lemma].append(lr)
                    except KeyError:
                        Grammar.lexRulesByLemma[lr.lemma] = [lr]
                    if self.verbose:
                        self.log_message('New lexical rule for lemma ' + lr.lemma)
                else:
                    self.raise_error('A lexical rule contains neither a lemma nor a stem: ',
                                     dictDescr)
            except MemoryError:
                self.raise_error('Not enough memory for the lexical rules.')
                return
        return len(Grammar.lexRulesByLemma) + len(Grammar.lexRulesByStem)

    def load_clitics(self, fnames):
        """Load clitics from the file or files specified by fnames.
        Return the number of lexemes loaded."""
        clDescrs = self.load_yaml_descrs(fnames)
        for dictDescr in clDescrs:
            if dictDescr is None or len(dictDescr) <= 0:
                continue
            try:
                self.clitics.append(clitic.Clitic(dictDescr, self.errorHandler))
            except MemoryError:
                self.raise_error('Not enough memory for the clitics.')
                return
        return len(self.clitics)

    def load_derivations(self, fnames, compileDerivs=False):
        """Load derivations from the file or files specified by fnames.
        Return the number of derivations loaded."""
        derivDescrs = self.load_yaml_descrs(fnames)
        for dictDescr in derivDescrs:
            dictDescr['value'] = '#deriv#' + dictDescr['value']
            try:
                self.derivations[dictDescr['value']] =\
                                  derivations.Derivation(dictDescr, self.errorHandler)
            except MemoryError:
                self.raise_error('Not enough memory for the derivations.')
                return
        if len(derivDescrs) <= 0:
            return 0
        for paradigm in self.paradigms.values():
            derivations.deriv_for_paradigm(paradigm)
        for derivName, deriv in self.derivations.items():
            if derivName.startswith('#deriv#paradigm#'):
                deriv.build_links()
                self.log_message(derivName + ': build complete')
                # print(str(self.derivations['#deriv#paradigm#Nctt']))
                deriv.extend_leaves()
                self.log_message(derivName + ': leaves extended')
                # print(str(deriv))
        # print(str(self.derivations['#deriv#N-fӕ#paradigm#Nct']))
        self.log_message('Derivations: Leaves extended')
        # print(str(self.derivations['#deriv#paradigm#Nct']))
        
        for derivName, deriv in self.derivations.items():
            p = deriv.to_paradigm()
            self.paradigms[derivName] = p
        if compileDerivs:
            for derivName in self.derivations:
                self.log_message('Compiling ' + derivName + '... ')
                self.paradigms[derivName].compile_paradigm()
                self.log_message(derivName + ' compiled')
                # if derivName == '#deriv#paradigm#Nctt':
                #     fPara = open('test-ossetic/deriv-Nctt-test.txt', 'w', encoding='utf-8-sig')
                #     for f in self.paradigms[derivName].flex:
                #         fPara.write(str(f))
                #     fPara.close()
            self.log_message('Derivations compiled')
        for lex in self.lexemes:
            lex.add_derivations()
        return len(self.derivations)

    def load_bad_analyses(self, fnames):
        """
        Load json descriptions of wrong analyses that should be
        deleted after parsing.
        """
        tmpBadAnalyses = []
        if type(fnames) == str:
            fnames = [fnames]
        for fname in fnames:
            try:
                f = open(fname, 'r', encoding='utf-8-sig')
                tmpBadAnalyses += json.loads(f.read())
                f.close()
            except IOError:
                self.raise_error('Error when opening a bad analyses file: ' + fname)
            except json.JSONDecodeError:
                self.raise_error('JSON error when reading a bad analyses file: ' + fname)
        Grammar.badAnalyses = []
        for ana in tmpBadAnalyses:
            if type(ana) != dict:
                continue
            bAnaOk = True
            for k in ana:
                if type(ana[k]) != str:
                    continue
                try:
                    ana[k] = re.compile('^' + ana[k].strip('^$') + '$')
                except:
                    self.raise_error('Wrong regular expression in bad analyses list: ' + ana[k])
                    bAnaOk = False
                    break
            if bAnaOk:
                self.badAnalyses.append(ana)
        return len(Grammar.badAnalyses)

    def add_deriv_links_to_paradigms(self):
        """
        Add to all paradigms all inflexions from the corresponding derivations.
        """
        for paraName in self.paradigms:
            try:
                deriv = self.paradigms['#deriv#paradigm#' + paraName]
            except KeyError:
                continue
            self.paradigms[paraName].flex += deriv.flex  # No need to copy inflexions as they are not used elsewhere
            self.log_message(str(len(deriv.flex)) + ' derivations added to the paradigm ' +
                             paraName)

    def compile_all(self):
        self.log_message('Starting paradigm compilation...')
        self.add_deriv_links_to_paradigms()
        self.log_message('Derivations added to the paradigms')
        curPercent = 1
        for iLex in range(len(self.lexemes)):
            if iLex * 100 // len(self.lexemes) > curPercent:
                self.log_message(str(curPercent) + '% done')
                curPercent = iLex * 100 / len(self.lexemes)
            lex = self.lexemes[iLex]
            try:
                lex.generate_redupl_paradigm()
                lex.generate_regex_paradigm()
            except MemoryError:
                self.raise_error('Not enough memory for compiling the paradigms.')
                return
            for sl in lex.subLexemes:
                try:
                    self.lexByParadigm[sl.paradigm].append((lex, sl))
                except KeyError:
                    self.lexByParadigm[sl.paradigm] = [(lex, sl)]
        self.log_message('Starting paradigm compilation...')


if __name__ == '__main__':
    g = Grammar()
