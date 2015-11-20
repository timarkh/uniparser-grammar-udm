# coding=utf-8
import os
import re


def remove_diacritics(s):
    return s.replace('ӧ', 'о').replace('ӥ', 'и').replace('ӟ', 'з').replace('ӵ', 'ч').replace('ӝ', 'ж')


def load_paradigms(dirname, ignoreDiacritics=False):
    dictParadigms = {}
    for fname in os.listdir(dirname):
        if 'stems' in fname or not fname.endswith('.csv'):
            continue
        print('Loading', fname)
        f = open(os.path.join(dirname, fname), 'r', encoding='utf-8-sig')
        dictInfl = {}
        for line in f:
            if ignoreDiacritics:
                line = remove_diacritics(line)

            line = line.strip('\r\n').split('\t')
            if len(line) <= 1:
                print('Empty line:', fname, line)
                continue
            if len(line[1]) > 0:
                gramm = ',' + line[1]
            else:
                gramm = line[1]
            ending = line[0].replace('.', '').replace('|', '')
            try:
                dictInfl[ending].append(gramm)
            except KeyError:
                dictInfl[ending] = [gramm]
        f.close()
        dictParadigms[fname.replace('.csv', '')] = dictInfl
    print(len(dictParadigms), 'paradigms loaded.')
    return dictParadigms


def load_lexemes(fname, ignoreDiacritics=False):
    f = open(fname, 'r', encoding='utf-8-sig')
    text = f.read()
    f.close()

    lexemes = re.findall('-lexeme *\n((?: [^\r\n]*\n)+)', text,
                         re.DOTALL)
    dictStems = {}
    for lex in lexemes:
        mLex = re.search(' lex: *([^\r\n ]+)', lex, flags=re.U)
        if mLex is None:
            continue
        lemma = mLex.group(1)
        mStem = re.search(' stem: *([^\r\n ]+)', lex, flags=re.U)
        if mStem is None:
            continue
        stem = mStem.group(1).strip().replace('.', '')
        if ignoreDiacritics:
            stem = remove_diacritics(stem)
        mGramm = re.search(' gramm: *([^\r\n ]+)', lex, flags=re.U)
        if mGramm is None:
            continue
        gramm = mGramm.group(1)
        mTrans = re.search(' trans_ru: *([^\r\n]+)', lex, flags=re.U)
        if mTrans is None:
            transRu = ''
        else:
            transRu = mTrans.group(1)
        paradigms = re.findall(' paradigm: *([^\r\n ]+)', lex, flags=re.U)
        if len(paradigms) <= 0:
            continue
        lexDescr = ('<ana lex="' + lemma + '" gr="' + gramm,
                    '" trans_ru="' + transRu + '"></ana>',
                    paradigms)
        try:
            dictStems[stem].append(lexDescr)
        except KeyError:
            dictStems[stem] = [lexDescr]
    print(len(dictStems), 'stems loaded.')
    return dictStems


def parse_word(word, dictLexemes, dictParadigms):
    analyses = []
    for i in range(1, len(word) + 1):
        l, r = word[:i], word[i:]
        try:
            possibleLex = dictLexemes[l]
        except KeyError:
            continue
        for lexDescr in possibleLex:
            for p in lexDescr[2]:  # paradigm names
                try:
                    possibleGramm = dictParadigms[p][r]
                except KeyError:
                    continue
                for gr in possibleGramm:
                    analyses.append(lexDescr[0] + gr + lexDescr[1])
    return ''.join(analyses)


def parse_file(fname, dictLexemes, dictParadigms):
    """
    Parse a file with a wordlist. Each line of the input file must
    have a wordform together with its frequency, separated by \t.
    """
    parsed = []
    unparsed = []
    nParsed = 0
    nTotal = 0
    f = open(fname, 'r', encoding='utf-8-sig')
    for line in f:
        if len(line) < 3:
            continue
        word, freq = line.strip().split('\t')
        ana = parse_word(word.strip('- \r\n'), dictLexemes, dictParadigms)
        if len(ana) > 0:
            parsed.append('<w>' + ana + word + '</w>')
            nParsed += int(freq)
        else:
            unparsed.append(word)
        nTotal += int(freq)
    f.close()
    return parsed, unparsed, nParsed / float(nTotal)


def write2file(arr, fname):
    f = open(fname, 'w', encoding='utf-8-sig')
    f.write('\n'.join(arr))
    f.close()


if __name__ == '__main__':
    dictParadigms = load_paradigms('ParadigmsCompiled', ignoreDiacritics=False)
    dictLexemes = load_lexemes('ParadigmsCompiled/stems.csv', ignoreDiacritics=False)
    parsed, unparsed, percent = parse_file('wordlist.csv', dictLexemes, dictParadigms)
    print(percent * 100, '% parsed')
    write2file(parsed, 'parsedConc.csv')
    write2file(unparsed, 'unparsedConc.csv')
##    print(parse_word('мынӥськомы', dictLexemes, dictParadigms))
##    print(parse_word('лыдӟиськем', dictLexemes, dictParadigms))
##    print(parse_word('тыршиськом', dictLexemes, dictParadigms))
