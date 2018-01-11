uniparser-grammar-udm
=====================

This is a formalized description of literary Udmurt morphology, which also includes a number of dialectal elements. The description is carried out in the UniParser format and involves a description of the inflection (paradigms.txt), a grammatical dictionary (udm_lexemes_XXX.txt files), a list of rules that annotate combinations of lexemes and grammatical values with additional Russian translations (lex_rules.txt), and a short list of analyses that should be avoided (bad_analyses.txt). The dictionary contains descriptions of individual lexemes, each of which is accompanied by information about its stem, its part-of-speech tag and some other grammatical/borrowing information, its inflectional type (paradigm), and Russian translation.

This description can be used for morphological analysis of Udmurt texts in the following ways:

1. The Wordlists directory contains a frequency list of tokens based on the Udmurt corpus (which contains 9 million words of contemporary texts) and the output of the analyzer for this list. The simplest solution is to use this analyzed wordlist for analyzing your texts. The recall of the analyzer on the corpus texts is about 96% and the corpus is sufficiently large, so if you use the wordlist, the recall on your texts will almost definitely exceed 90%.

2. The Analyzer directory contains the UniParser set of scripts together with all necessary language files. You can use it to analyze your own frequency word list. Your have to name your list "wordlist.csv" and put it to that directory. Each line should contain one token and its frequency, tab-delimited. When you run analyzer/UniParser/analyze.py, the analyzer will produce two files, one with analyzed tokens, the other with unanalyzed ones. (You can also use other file names and separators with command line options, see the code of analyze.py.) This way, you will notbe restricted by my word list, but the analyzer works pretty slowly (300-400 tokens per second).

3. Finally, you are free to convert/adapt the description to whatever kind of morphological analysis you prefer to use.

Apart from the analyzer, this repository contains a set of Constraint Grammar rules that can be used to partial disambiguation of analyzed Udmurt texts. They reduce the average number of different analyses per analyzed token from about 1.6 to about 1.3.