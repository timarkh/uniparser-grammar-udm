import re
import os
import shutil

rxDiacritics = re.compile('[ӥӧӵӟӝё]')
rxDiaPartsStem = re.compile('( stem:)( *[^\r\n]+)')
rxDiaPartsFlex = re.compile('(-flex:)( *[^\r\n]+)')
rxStemVariants = re.compile('[^ |/]+')
rxFlexVariants = re.compile('[^ /]+')
rxYer = re.compile('ъ')
rxYo = re.compile('ё')
rxIVowel = re.compile('и(?=[аеёиӥоӧуыэюя])')
rxEYe = re.compile('(?<=[бвгжӟӝйкмпрфхцчӵшщ])е')
rxYerYerj = re.compile('(?<=[бвгжӟӝйкмпрфхцчӵшщ])ъ(?=[яеёюи])')
dictDiacritics = {
    'ӥ': 'и',
    'ӧ': 'о',
    'ӝ': 'ж',
    'ӟ': 'з',
    'ӵ': 'ч',
    'ё': 'е'
}
rxParadigmChange = re.compile('( stem: *[^\r\n]+ӟ\\.\n(?: [^\r\n]*\n)*)'
                              '( paradigm: (?:Noun|connect_verbs)[^\r\n]+?[^C])((?:-consonant)?)\n',
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


def russify_diacritics_stem(line):
    """
    Remove diacritics from one line that contains stems.
    """
    morphCorrected = rxStemVariants.sub(add_diacriticless, line.group(2))
    return line.group(1) + morphCorrected


def russify_diacritics_flex(line):
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
    text = rxDiaPartsStem.sub(russify_diacritics_stem, text)
    text = rxDiaPartsFlex.sub(russify_diacritics_flex, text)
    return text


def add_oldorth(morph):
    """
    Add pre-standardized spelling variants to a stem or an inflection
    """
    morph = morph.group(0)
    alternatives = {morph}
    alternatives.add(rxEYe.sub("э", rxYer.sub("'", rxYerYerj.sub('ь', morph))))
    alternatives.add(rxEYe.sub("э", rxYer.sub("'", rxYerYerj.sub('ь', morph))))
    alternatives.add(rxEYe.sub("э", rxYer.sub("’", rxYerYerj.sub('ь', morph))))
    alternatives.add(rxEYe.sub("э", rxYer.sub("'", morph)))
    alternatives.add(rxEYe.sub("э", rxYer.sub("'", morph)))
    alternatives.add(rxEYe.sub("э", rxYer.sub("’", morph)))
    alternatives.add(rxEYe.sub("э", rxYerYerj.sub('ь', morph)))
    alternatives.add(rxEYe.sub("э", morph))
    alternatives.add(rxYer.sub("'", rxYerYerj.sub('ь', morph)))
    alternatives.add(rxYer.sub("‘", rxYerYerj.sub('ь', morph)))
    alternatives.add(rxYer.sub("’", rxYerYerj.sub('ь', morph)))
    alternatives.add(rxYer.sub("'", morph))
    alternatives.add(rxYer.sub("‘", morph))
    alternatives.add(rxYer.sub("’", morph))
    alternatives.add(rxYo.sub('е', rxYer.sub("'", morph)))
    alternatives.add(rxYo.sub('е', rxYer.sub("‘", morph)))
    alternatives.add(rxYo.sub('е', rxYer.sub("’", morph)))
    alternatives.add(rxYo.sub('е', rxYer.sub("'", rxYerYerj.sub('ь', morph))))
    alternatives.add(rxYo.sub('е', rxYer.sub("‘", rxYerYerj.sub('ь', morph))))
    alternatives.add(rxYo.sub('е', rxYer.sub("’", rxYerYerj.sub('ь', morph))))
    alternatives.add(rxIVowel.sub("і", morph))
    alternatives.add(rxIVowel.sub("i", morph))
    alternatives.add(rxYo.sub('е', rxIVowel.sub("і", morph)))
    alternatives.add(rxYo.sub('е', rxIVowel.sub("i", morph)))
    return '//'.join(m for m in sorted(alternatives))


def oldorth_stem(line):
    """
    Add pre-standardized spelling variants in one line that contains stems.
    """
    morphCorrected = rxStemVariants.sub(add_oldorth, line.group(2))
    return line.group(1) + morphCorrected


def oldorth_flex(line):
    """
    Add pre-standardized spelling variants in one line that contains inflexions.
    """
    morphCorrected = rxFlexVariants.sub(add_oldorth, line.group(2))
    return line.group(1) + morphCorrected


def oldorth(text):
    """
    Add pre-standardized spelling variants for stems and inflections.
    """
    text = rxDiaPartsStem.sub(oldorth_stem, text)
    text = rxDiaPartsFlex.sub(oldorth_flex, text)
    return text


def prepare_files():
    """
    Put all the lemmata to lexemes.txt. Put all the lexical
    rules to lexical_rules.txt. Create separate versions of
    relevant files for diacriticless texts.
    Put all grammar files to ../uniparser_udmurt/data_strict/
    (original version), ../uniparser_udmurt/data_nodiacritics/
    (diacriticless version) and ../uniparser_udmurt/data_oldorth/
    (version for pre-standardized orthographies).
    """
    lemmata, lexrules = collect_lemmata('.')
    with open('uniparser_udmurt/data_strict/lexemes.txt', 'w', encoding='utf-8') as fOutLemmata:
        fOutLemmata.write(lemmata)
    with open('uniparser_udmurt/data_nodiacritics/lexemes.txt', 'w', encoding='utf-8') as fOutLemmataRus:
        fOutLemmataRus.write(russify(lemmata))
    with open('uniparser_udmurt/data_oldorth/lexemes.txt', 'w', encoding='utf-8') as fOutLemmataOld:
        fOutLemmataOld.write(oldorth(lemmata))

    with open('paradigms.txt', 'r', encoding='utf-8-sig') as fInParadigms:
        paradigms = fInParadigms.read()
    with open('uniparser_udmurt/data_strict/paradigms.txt', 'w', encoding='utf-8') as fOutParadigms:
        fOutParadigms.write(paradigms)
    with open('uniparser_udmurt/data_nodiacritics/paradigms.txt', 'w', encoding='utf-8') as fOutParadigmsRus:
        fOutParadigmsRus.write(russify(paradigms))
    with open('uniparser_udmurt/data_oldorth/paradigms.txt', 'w', encoding='utf-8') as fOutParadigmsOld:
        fOutParadigmsOld.write(oldorth(paradigms))

    with open('uniparser_udmurt/data_strict/lex_rules.txt', 'w', encoding='utf-8') as fOutLexrules:
        fOutLexrules.write(lexrules)
    with open('uniparser_udmurt/data_nodiacritics/lex_rules.txt', 'w', encoding='utf-8') as fOutLexrules:
        fOutLexrules.write(lexrules)
    with open('uniparser_udmurt/data_oldorth/lex_rules.txt', 'w', encoding='utf-8') as fOutLexrules:
        fOutLexrules.write(lexrules)

    shutil.copy2('bad_analyses.txt', 'uniparser_udmurt/data_strict/')
    shutil.copy2('bad_analyses.txt', 'uniparser_udmurt/data_nodiacritics/')
    shutil.copy2('bad_analyses.txt', 'uniparser_udmurt/data_oldorth/')
    shutil.copy2('udmurt_disambiguation.cg3', 'uniparser_udmurt/data_strict/')
    shutil.copy2('udmurt_disambiguation.cg3', 'uniparser_udmurt/data_nodiacritics/')
    shutil.copy2('udmurt_disambiguation.cg3', 'uniparser_udmurt/data_oldorth/')


def process_unanalyzed(a, replacementsAllowed=0):
    """
    Try analyzing the unanalyzed words with another, lax model.
    Add the results to the list of analyzed words.
    This function is first called with a diacritic-insensitive model,
    then with a strict model that allows for replacements.
    """
    unanalyzedDia = []
    freqDict = {}
    with open('wordlists/wordlist_unanalyzed.txt', 'r', encoding='utf-8') as fIn:
        for word in fIn:
            word = word.strip()
            unanalyzedDia.append(word)
    with open('wordlists/wordlist.csv', 'r', encoding='utf-8') as fIn:
        for line in fIn:
            word, freq = line.strip().split('\t')
            freqDict[word] = freq
    with open('wordlists/wordlist_nodia.csv', 'w', encoding='utf-8') as fOut:
        for word in unanalyzedDia:
            fOut.write(word + '\t' + freqDict[word] + '\n')
    a.analyze_wordlist(freqListFile='wordlists/wordlist_nodia.csv',
                       parsedFile='wordlists/wordlist_analyzed_nodia.txt',
                       unparsedFile='wordlists/wordlist_unanalyzed_nodia.txt',
                       verbose=True,
                       replacementsAllowed=replacementsAllowed)
    analyzedDia = set()
    with open('wordlists/wordlist_analyzed_nodia.txt', 'r', encoding='utf-8') as fIn:
        lines = '\n'
        for line in fIn:
            m = re.search('^(.*>)([^<>\r\n]+)</w>', line)
            if m is None:
                continue
            word = m.group(2)
            analyzedDia.add(word)
            lines += m.group(1) + word + '</w>\n'
    with open('wordlists/wordlist_analyzed.txt', 'a', encoding='utf-8') as fOut:
        fOut.write(lines)
    lines = []
    with open('wordlists/wordlist_unanalyzed.txt', 'r', encoding='utf-8') as fIn:
        for line in fIn:
            line = line.strip()
            if line not in analyzedDia:
                lines.append(line)
    with open('wordlists/wordlist_unanalyzed.txt', 'w', encoding='utf-8') as fOut:
        fOut.write('\n'.join(lines))


def parse_wordlists():
    """
    Analyze wordlists/wordlist.csv.
    """
    from uniparser_udmurt import UdmurtAnalyzer
    a = UdmurtAnalyzer(mode='strict')
    aNodia = UdmurtAnalyzer(mode='nodiacritics')
    a.analyze_wordlist(freqListFile='wordlists/wordlist.csv',
                       parsedFile='wordlists/wordlist_analyzed.txt',
                       unparsedFile='wordlists/wordlist_unanalyzed.txt',
                       verbose=True,
                       replacementsAllowed=0)
    print('Processing words that potentially have no diacritics...')
    process_unanalyzed(aNodia)
    print('Processing words with one replacement allowed...')
    process_unanalyzed(a, replacementsAllowed=1)


if __name__ == '__main__':
    prepare_files()
    parse_wordlists()
    # from uniparser_udmurt import UdmurtAnalyzer
    # a = UdmurtAnalyzer(mode='oldorth')
    # for wf in a.analyze_words(['шэр', 'пинал’ёс', 'пинал’ес'], format='json'):
    #     print(wf)
