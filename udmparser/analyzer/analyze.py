# This is the script you should start with.

import sys
import os
import grammar
import morph_parser
import time


def collect_filenames(s):
    """
    Check if the string s contains a name of a file or a directory.
    If the latter is true, return the list of .txt and .yaml files
    in the subtree. Otherwise, return [s].
    """
    filenames = []
    if os.path.isdir(s):
        for root, dirs, files in os.walk(s):
            for fname in files:
                if not fname.lower().endswith(('.txt', '.yaml')):
                    continue
                filenames.append(os.path.join(root, fname))
    else:
        if os.path.exists(s):
            filenames = [s]
    return filenames


def analyze(freqListFile, paradigmFile, lexFile, lexRulesFile,
            derivFile, conversionFile, cliticFile, delAnaFile,
            parsedFile, unparsedFile, errorFile,
            xmlOutput=True, verboseGrammar=False, parserVerbosity=0,
            freqListSeparator='\t', glossing=True,
            parsingMethod='fst', partialCompile=True,
            minFlexLen=4, maxCompileTime=60):
    t1 = time.time()
    g = grammar.Grammar(verbose=verboseGrammar)
    grammar.Grammar.PARTIAL_COMPILE = partialCompile
    grammar.Grammar.MIN_FLEX_LENGTH = minFlexLen
    grammar.Grammar.MAX_COMPILE_TIME = maxCompileTime
    paradigmFiles = collect_filenames(paradigmFile)
    lexFiles = collect_filenames(lexFile)
    lexRulesFiles = collect_filenames(lexRulesFile)
    derivFiles = collect_filenames(derivFile)
    conversionFiles = collect_filenames(conversionFile)
    cliticFiles = collect_filenames(cliticFile)
    delAnaFiles = collect_filenames(delAnaFile)

    if parsedFile is None or len(parsedFile) <= 0:
        parsedFile = freqListFile + '-parsed.txt'
    if unparsedFile is None or len(unparsedFile) <= 0:
        unparsedFile = freqListFile + '-unparsed.txt'

    print(g.load_stem_conversions(conversionFiles), 'stem conversions loaded.')
    print(g.load_paradigms(paradigmFiles, compileParadigms=False), 'paradigms loaded.')
    print(g.load_lexemes(lexFiles), 'lexemes loaded.')
    print(g.load_lex_rules(lexRulesFiles), 'lexical rules loaded.')
    print(g.load_derivations(derivFiles), 'derivations loaded.')
    print(g.load_clitics(cliticFiles), 'clitics loaded.')
    print(g.load_bad_analyses(delAnaFiles), 'bad analyses loaded.')
    g.compile_all()
    print('Paradigms and lexemes loaded and compiled in', time.time() - t1, 'seconds.')
    print('\n\n**** Starting parser... ****\n')
    t1 = time.time()
    m = morph_parser.Parser(verbose=parserVerbosity, parsingMethod=parsingMethod)
    m.fill_stems()
    if parsingMethod == 'fst':
        m.fill_affixes()
    print('Parser initialized in', time.time() - t1, 'seconds.')
    t1 = time.time()

    m.verbose = 0

    nTokens, parsedRate = m.parse_freq_list(freqListFile,
                                            sep=freqListSeparator,
                                            fnameParsed=parsedFile,
                                            fnameUnparsed=unparsedFile,
                                            glossing=glossing,
                                            maxLines=10000000000)
    print('Frequency list processed,', parsedRate * 100, '% tokens parsed.')
    print('Average speed:', nTokens / (time.time() - t1), 'tokens per second.')


if __name__ == '__main__':
    paradigmFile = 'paradigms.txt'
    lexFile = 'lexemes.txt'
    lexRulesFile = 'lex_rules.txt'
    derivFile = 'derivations.txt'
    conversionFile = 'stem_conversions.txt'
    cliticFile = 'clitics.txt'
    delAnaFile = 'bad_analyses.txt'
    freqListFile = '../wordlist.csv'
    freqListSeparator = '\t'
    parserVerbosity = 0
    parsingMethod = 'fst'
    errorFile = None
    parsedFile = None
    unparsedFile = None
    xmlOutput = True
    for iArg in range(1, len(sys.argv)):
        if iArg == 1 and not sys.argv[iArg].startswith('-'):
            freqListFile = sys.argv[iArg]
        elif sys.argv[iArg].startswith('-'):
            command = sys.argv[iArg]['-']
            if iArg == len(sys.argv) - 1 and command not in ['xml']:
                print('No value specified for the parameter', command)
                continue
            if command in ['p', 'paradigms']:
                paradigmFile = sys.argv[iArg + 1]
            elif command in ['l', 'lexemes']:
                lexFile = sys.argv[iArg + 1]
            elif command in ['lr', 'lex_rules']:
                lexRulesFile = sys.argv[iArg + 1]
            elif command in ['conv', 'conversions']:
                conversionFile = sys.argv[iArg + 1]
            elif command in ['d', 'derivations']:
                derivFile = sys.argv[iArg + 1]
            elif command in ['cl', 'clitics']:
                cliticFile = sys.argv[iArg + 1]
            elif command in ['ba', 'bad_analyses']:
                delAnaFile = sys.argv[iArg + 1]
            elif command in ['pf', 'parsed']:
                parsedFile = sys.argv[iArg + 1]
            elif command in ['uf', 'unparsed']:
                unparsedFile = sys.argv[iArg + 1]
            elif command in ['el', 'error_log']:
                errorFile = sys.argv[iArg + 1]
            elif command in ['v', 'verbosity']:
                try:
                    parserVerbosity = int(sys.argv[iArg + 1])
                except ValueError:
                    pass
                if parserVerbosity not in [0, 1, 2]:
                    if parserVerbosity > 2:
                        parserVerbosity = 2
                    else:
                        parserVerbosity = 0
            elif command in ['pm', 'parsing_method']:
                parsingMethod = sys.argv[iArg + 1]
                if parsingMethod not in ['fst', 'hash']:
                    print('Unrecognized parsing method, assuming fst.')
                    parsingMethod = 'fst'
            elif command == 'sep_colon':
                freqListSeparator = ':'
            elif command == 'sep_tab':
                freqListSeparator = '\t'
            elif command == 'sep_comma':
                freqListSeparator = ','
            elif command == 'sep_semicolon':
                freqListSeparator = ';'
            elif command == 'sep_space':
                freqListSeparator = ' '
            elif command == 'xml':
                xmlOutput = True
            elif command == 'noxml':
                xmlOutput = False
    analyze(freqListFile, paradigmFile, lexFile, lexRulesFile, derivFile, conversionFile,
            cliticFile, delAnaFile, parsedFile, unparsedFile, errorFile, xmlOutput,
            False, parserVerbosity, freqListSeparator, parsingMethod=parsingMethod)
