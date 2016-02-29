import re

fIn = open('udm_lexemes_N_unsure.txt', 'r', encoding='utf-8-sig')
fOutN = open('NEW_N_unsure.txt', 'w', encoding='utf-8-sig')
fOutADV = open('NEW_ADV_unsure.txt', 'w', encoding='utf-8-sig')
fOutADJ = open('NEW_ADJ_unsure.txt', 'w', encoding='utf-8-sig')
fOutV = open('NEW_V_unsure.txt', 'w', encoding='utf-8-sig')
fOutIMIT = open('NEW_IMIT_unsure.txt', 'w', encoding='utf-8-sig')
fOutPART = open('NEW_PART_unsure.txt', 'w', encoding='utf-8-sig')
text = fIn.read()
fIn.close()
lexemes = re.findall('-lexeme\n(?: [^\r\n]*\n)+', text, flags=re.DOTALL)
print(len(lexemes))
for l in lexemes:
    l += '\n'
    if 'gramm: N' in l:
        fOutN.write(l)
    elif 'gramm: ADV' in l:
        fOutADV.write(l)
    elif 'gramm: ADJ' in l:
        fOutADJ.write(l)
    elif 'gramm: V' in l:
        fOutV.write(l)
    elif 'gramm: IMIT' in l:
        fOutIMIT.write(l)
    else:
        fOutPART.write(l)
fOutN.close()
fOutADV.close()
fOutADJ.close()
fOutV.close()
fOutIMIT.close()
fOutPART.close()
