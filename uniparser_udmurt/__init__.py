try:
    from importlib.resources import files, as_file
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
        self.mode = mode
        if mode not in ('strict', 'nodiacritics'):
            return
        self.dirName = 'uniparser_udmurt.data_' + mode
        with as_file(files(self.dirName) / 'paradigms.txt') as self.paradigmFile,\
             as_file(files(self.dirName) / 'lexemes.txt') as self.lexFile,\
             as_file(files(self.dirName) / 'lex_rules.txt') as self.lexRulesFile,\
             as_file(files(self.dirName) / 'derivations.txt') as self.derivFile,\
             as_file(files(self.dirName) / 'stem_conversions.txt') as self.conversionFile,\
             as_file(files(self.dirName) / 'clitics.txt') as self.cliticFile,\
             as_file(files(self.dirName) / 'bad_analyses.txt') as self.delAnaFile:
            self.load_grammar()

    def analyze_words(self, words, format=None, disambiguate=False):
        """
        Analyze a single word or a (possibly nested) list of words. Return either a list of
        analyses (all possible analyses of the word) or a nested list of lists
        of analyses with the same depth as the original list.
        If format is None, the analyses are Wordform objects.
        If format == 'xml', the analyses for each word are united into an XML string.
        If format == 'json', the analyses are JSON objects (dictionaries).
        Perform CG3 disambiguation if disambiguate == True and CG3 is installed.
        """
        if disambiguate:
            with as_file(files(self.dirName) / 'udmurt_disambiguation.cg3') as cgFile:
                cgFilePath = str(cgFile)
                return super().analyze_words(words, format=format, disambiguate=True,
                                             cgFile=cgFilePath)
        return super().analyze_words(words, format=format, disambiguate=False)


if __name__ == '__main__':
    pass

