import re
import os


def collect_lemmata():
    lemmata = ''
    lexrules = ''
    for fname in os.listdir('..'):
        if fname.endswith('.txt') and fname.startswith('udm_lexemes_'):
            f = open(os.path.join('..', fname), 'r', encoding='utf-8-sig')
            lemmata += f.read() + '\n'
            f.close()
        elif fname.endswith('.txt') and fname.startswith('udm_lexrules_'):
            f = open(os.path.join('..', fname), 'r', encoding='utf-8-sig')
            lexrules += f.read() + '\n'
            f.close()
    lemmataSet = set(re.findall('-lexeme\n(?: [^\r\n]*\n)+', lemmata, flags=re.DOTALL))
    lemmata = '\n'.join(sorted(list(lemmataSet)))
    return lemmata, lexrules


def main():
    """
    Put all the lemmata to lexemes.txt. Put all the lexical
    rules to lexical_rules.txt.
    """
    lemmata, lexrules = collect_lemmata()
    fOutLemmata = open('lexemes.txt', 'w', encoding='utf-8')
    fOutLemmata.write(lemmata)
    fOutLemmata.close()
    fOutLemmata = open('lex_rules.txt', 'w', encoding='utf-8')
    fOutLemmata.write(lexrules)
    fOutLemmata.close()


if __name__ == '__main__':
    main()
