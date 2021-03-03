try:
    from importlib_resources import files, as_file
except ImportError:
    from importlib_resources import files, as_file
from uniparser_morph import Analyzer


class UdmurtAnalyzer(Analyzer):
    def __init__(self, mode='strict', verbose_grammar=False):
        """
        Initialize the analyzer by reading the grammar files.
        If mode=='strict' (default), load the data as is.
        If mode=='nodiacritics', load the data for (possibly) diacriticless texts.
        """
        super().__init__(verbose_grammar=verbose_grammar)
        if mode not in ('strict', 'nodiacritics'):
            return
        dirName = 'uniparser_udmurt.data_' + mode
        with as_file(files(dirName) / 'paradigms.txt') as self.paradigmFile,\
             as_file(files(dirName) / 'lexemes.txt') as self.lexFile,\
             as_file(files(dirName) / 'lex_rules.txt') as self.lexRulesFile,\
             as_file(files(dirName) / 'derivations.txt') as self.derivFile,\
             as_file(files(dirName) / 'stem_conversions.txt') as self.conversionFile,\
             as_file(files(dirName) / 'clitics.txt') as self.cliticFile,\
             as_file(files(dirName) / 'bad_analyses.txt') as self.delAnaFile:
            self.load_grammar()


if __name__ == '__main__':
    pass

