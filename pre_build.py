import re
import os
import shutil

rxDiacritics = re.compile('[ӥӧӵӟӝё]')
rxDiaPartsStem = re.compile('( stem:)( *[^\r\n]+)')
rxDiaPartsFlex = re.compile('(-flex:)( *[^\r\n]+)')
rxStemVariants = re.compile('[^ |/]+')
rxFlexVariants = re.compile('[^ /]+')
dictDiacritics = {
    'ӥ': 'и',
    'ӧ': 'о',
    'ӝ': 'ж',
    'ӟ': 'з',
    'ӵ': 'ч',
    'ё': 'е'
}
rxParadigmChange = re.compile('( stem: *[^\r\n]+ӟ\\.\n(?: [^\r\n]*\n)*)'
                              '( paradigm: (?:Noun|connect_verbs)[^\r\n]+?)((?:-consonant)?)\n',
                              flags=re.DOTALL)


def collect_lemmata(dirName):
    lemmata = ''
    lexrules = ''
    for fname in os.listdir(dirName):
        if fname.endswith('.txt') and fname.startswith('udm_lexemes_'):
            f = open(os.path.join(dirName, fname), 'r', encoding='utf-8-sig')
            lemmata += f.read() + '\n'
            f.close()
        elif fname.endswith('.txt') and fname.startswith('udm_lexrules_'):
            f = open(os.path.join(dirName, fname), 'r', encoding='utf-8-sig')
            lexrules += f.read() + '\n'
            f.close()
    lemmataSet = set(re.findall('-lexeme\n(?: [^\r\n]*\n)+', lemmata, flags=re.DOTALL))
    lemmata = '\n'.join(sorted(list(lemmataSet)))
    return lemmata, lexrules


def add_diacriticless(morph):
    """
    Add a diacriticless variant to a stem or an inflection
    """
    morph = morph.group(0)
    if rxDiacritics.search(morph) is None:
        return morph
    return morph + '//' + rxDiacritics.sub(lambda m: dictDiacritics[m.group(0)], morph)


def process_diacritics_stem(line):
    """
    Remove diacritics from one line that contains stems.
    """
    morphCorrected = rxStemVariants.sub(add_diacriticless, line.group(2))
    return line.group(1) + morphCorrected


def process_diacritics_flex(line):
    """
    Remove diacritics from one line that contains inflextions.
    """
    morphCorrected = rxFlexVariants.sub(add_diacriticless, line.group(2))
    return line.group(1) + morphCorrected


def russify(text):
    """
    Add diacriticless variants for stems and inflections.
    """
    text = rxParadigmChange.sub('\\1\\2\\3\n\\2-soft\n', text)
    text = rxDiaPartsStem.sub(process_diacritics_stem, text)
    text = rxDiaPartsFlex.sub(process_diacritics_flex, text)
    return text


def prepare_files():
    """
    Put all the lemmata to lexemes.txt. Put all the lexical
    rules to lexical_rules.txt. Create separate versions of
    relevant files for diacriticless texts.
    Put all grammar files to ../uniparser_udmurt/data_strict/
    (original version) or ../uniparser_udmurt/data_nodiacritics/
    (diacriticless version).
    """
    lemmata, lexrules = collect_lemmata('.')
    fOutLemmata = open('uniparser_udmurt/data_strict/lexemes.txt', 'w', encoding='utf-8')
    fOutLemmata.write(lemmata)
    fOutLemmata.close()
    fOutLemmataRus = open('uniparser_udmurt/data_nodiacritics/lexemes.txt', 'w', encoding='utf-8')
    fOutLemmataRus.write(russify(lemmata))
    fOutLemmataRus.close()
    fInParadigms = open('paradigms.txt', 'r', encoding='utf-8-sig')
    paradigms = fInParadigms.read()
    fInParadigms.close()
    fOutParadigms = open('uniparser_udmurt/data_strict/paradigms.txt', 'w', encoding='utf-8')
    fOutParadigms.write(paradigms)
    fOutParadigms.close()
    fOutParadigmsRus = open('uniparser_udmurt/data_nodiacritics/paradigms.txt', 'w', encoding='utf-8')
    fOutParadigmsRus.write(russify(paradigms))
    fOutParadigmsRus.close()
    fOutLexrules = open('uniparser_udmurt/data_strict/lex_rules.txt', 'w', encoding='utf-8')
    fOutLexrules.write(lexrules)
    fOutLexrules.close()
    fOutLexrules = open('uniparser_udmurt/data_nodiacritics/lex_rules.txt', 'w', encoding='utf-8')
    fOutLexrules.write(lexrules)
    fOutLexrules.close()
    shutil.copy2('bad_analyses.txt', 'uniparser_udmurt/data_strict/')
    shutil.copy2('bad_analyses.txt', 'uniparser_udmurt/data_nodiacritics/')
    shutil.copy2('udmurt_disambiguation.cg3', 'uniparser_udmurt/data_strict/')
    shutil.copy2('udmurt_disambiguation.cg3', 'uniparser_udmurt/data_nodiacritics/')


def parse_wordlists():
    """
    Analyze wordlists/wordlist.csv.
    """
    from uniparser_udmurt import UdmurtAnalyzer
    a = UdmurtAnalyzer(mode='strict')
    a.analyze_wordlist(freqListFile='wordlists/wordlist.csv',
                       parsedFile='wordlists/wordlist_analyzed.txt',
                       unparsedFile='wordlists/wordlist_unanalyzed.txt',
                       verbose=True)


if __name__ == '__main__':
    prepare_files()
    parse_wordlists()
