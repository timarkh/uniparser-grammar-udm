import re
import os

rxLexeme = re.compile('(-lexeme\n lex: ([^\r\n]+)\n(?: [^\r\n]*\n)*?'
                      ' gramm: ([^\r\n,]+)[^\r\n]*\n(?: [^\r\n]*\n)*)', flags=re.DOTALL)


def split_fields(lex):
    lemma = ''
    pos = ''
    grdic = ''
    stem = ''
    paradigm = ''
    trans_ru = ''
    trans_en = ''
    lemma = ' / '.join(re.findall(' lex: *([^\r\n]*?) *\n', lex, flags=re.DOTALL))
    m = re.search(' gramm: *([^\r\n, ]*)', lex, flags=re.DOTALL)
    if m is not None:
        pos = m.group(1)
    m = re.search(' gramm: *[^\r\n, ]*,([^\r\n]*?) *\n', lex, flags=re.DOTALL)
    if m is not None:
        grdic = m.group(1)
    m = re.search(' stem: *([^\r\n]*)', lex, flags=re.DOTALL)
    if m is not None:
        stem = m.group(1).strip()
    paradigm = ' / '.join(re.findall(' paradigm: *([^\r\n]*?) *\n', lex, flags=re.DOTALL))
    trans_ru = ' / '.join(re.findall(' trans_ru: *([^\r\n]*?) *\n', lex, flags=re.DOTALL))
    trans_en = ' / '.join(re.findall(' trans_en: *([^\r\n]*?) *\n', lex, flags=re.DOTALL))
    return lemma, pos, grdic, stem, paradigm, trans_ru, trans_en


def load_tabulate_lexemes(fnameDict):
    curDict = {}
    table = []
    usedLexemes = set()
    with open(fnameDict, 'r', encoding='utf-8') as fIn:
        text = fIn.read()
        lexemesFound = rxLexeme.findall(text)
        print(len(lexemesFound), 'lexemes found.')
        for lexeme, lemma, pos in lexemesFound:
            lexeme = re.sub('(gramm: *[A-Z]+)\\?', '\\1', lexeme)
            if lexeme in usedLexemes:
                print('Duplicate', lexeme)
                continue    # remove complete duplicates
            if (lemma, pos) not in curDict:
                curDict[(lemma, pos)] = []
            curDict[(lemma, pos)].append(lexeme)
    lexNew = set()
    for lemma, pos in curDict:
        for lexeme in curDict[(lemma, pos)]:
            lemma, pos, grdic, stem, paradigm, trans_ru, trans_en = split_fields(lexeme)
            if lexeme in lexNew:
                print('Duplicate', lexeme)
            else:
                table.append([lemma, pos, grdic, stem, paradigm, trans_ru, trans_en, ''])
                lexNew.add(lexeme)
    return lexNew, table


def yaml2csv(fnameYaml, fnameCsv):
    lex, table = load_tabulate_lexemes(fnameYaml)
    wfFreqs = {}
    lemmaFreqs = {}
    rxLemma = re.compile('\\blex="([^\r\n"<>]+)"')
    rxWf = re.compile('>([^\r\n<>]+)</w>')
    with open('wordlists/wordlist.csv', 'r', encoding='utf-8-sig') as fWordlist:
        for line in fWordlist:
            if '\t' not in line:
                continue
            wf, freq = line.strip('\r\n').split('\t')
            wfFreqs[wf] = int(freq)
    with open('wordlists/wordlist_analyzed.txt', 'r', encoding='utf-8-sig') as fAnalyzed:
        for line in fAnalyzed:
            mWf = rxWf.search(line)
            if mWf is None:
                continue
            wf = mWf.group(1)
            if wf not in wfFreqs:
                print(wf, 'not in frequency list')
                continue
            freq = wfFreqs[wf]
            for lemma in rxLemma.findall(line):
                if lemma not in lemmaFreqs:
                    lemmaFreqs[lemma] = freq
                else:
                    lemmaFreqs[lemma] += freq
    for i in range(len(table)):
        lemma = table[i][0]
        if lemma not in lemmaFreqs:
            table[i].append(0)
        else:
            table[i].append(lemmaFreqs[lemma])
    with open('add_lex/cur-lexemes.txt', 'w', encoding='utf-8') as fOut:
        fOut.write('\n'.join(l for l in sorted(lex)))
    # Sort by POS, then by frequency, then by lemma
    with open(fnameCsv, 'w', encoding='utf-8') as fOut:
        fOut.write('\n'.join('\t'.join(str(field) for field in line)
                             for line in sorted(table, key=lambda l: (l[1], -l[-1], l[0]))))


def csv2yaml(fnameCsv, fnameYaml):
    """
    Load manually edited data from a CSV.
    """
    lexemesOut = []
    with open(fnameCsv, 'r', encoding='utf-8') as fIn:
        lexemes = fIn.readlines()
    for lex in sorted(l.strip('\r\n') for l in lexemes if len(l) > 5 and '\t' in l):
        lemma, pos, grdic, stem, para, trans_en, trans_fr, remove, rest = lex.split('\t', 8)
        if len(remove.strip()) > 0 or len(lemma) <= 0:
            continue
        if 'PN' not in grdic and re.search('\\b(topn|famn|persn|patrn)\\b', grdic) is not None:
            grdic = 'PN,' + grdic
        if 'anim' not in grdic and re.search('\\b(hum)\\b', grdic) is not None:
            grdic = 'anim,' + grdic
        gramm = pos.replace(' ', '') + ',' + grdic.replace(' ', '')
        gramm = gramm.strip('.,')
        if re.search(',(persn|topn|famn|patrn|PN)\\b', gramm) is not None:
            lemma = lemma[0].upper() + lemma[1:]
        if len(para) <= 0:
            para = 'unchangeable'
        para = para.replace(' ', '').split('/')
        lexOut = ('\n-lexeme\n lex: ' + lemma + '\n stem: ' + stem.strip().replace(' /', '/').replace(' |', '|')
                  + '\n gramm: ' + gramm + ''.join('\n paradigm: ' + p for p in sorted(para))
                  + '\n trans_ru: ' + trans_en.strip() + '\n trans_en: ' + trans_fr.strip() + '\n')
        lexemesOut.append(lexOut)
    lexemesOutStr = ''.join(l for l in sorted(lexemesOut))
    with open(fnameYaml, 'w', encoding='utf-8') as fOut:
        fOut.write(lexemesOutStr.strip())


if __name__ == '__main__':
    # yaml2csv_filter()
    yaml2csv('udm_lexemes_N.txt', 'add_lex/udm_lexemes_N.csv')
    # csv2yaml('add_lex/udm_lexemes_N.csv', 'udm_lexemes_N-2026.02.txt')
