# Udmurt morphological analyzer
This is a rule-based morphological analyzer for Udmurt (udm; Uralic > Permic). It is based on a formalized description of literary Udmurt morphology, which also includes a number of dialectal elements, and uses [uniparser-morph](https://github.com/timarkh/uniparser-morph) for parsing.

## How to use
### Python package
The analyzer is available as a Python package. If you want to analyze Udmurt texts in Python, install the module:

```
pip3 install uniparser-udmurt
```

Import the module and create an instance of ``UdmurtAnalyzer`` class. Set ``mode='strict'`` if you are going to process text in standard orthography, or ``mode='nodiacritics'`` if you expect some words to lack the diacritics (which often happens in social media). After that, you can either parse tokens or lists of tokens with ``analyze_words()``, or parse a frequency list with ``analyze_wordlist()``. Here is a simple example:

```python
from uniparser_udmurt import UdmurtAnalyzer
a = UdmurtAnalyzer(mode='strict')

analyses = a.analyze_words('Морфологияез')
# The parser is initialized before first use, so expect
# some delay here (usually several seconds)

# You will get a list of Wordform objects
# The analysis attributes are stored in its properties
# as string values, e.g.:
for ana in analyses:
        print(ana.wf, ana.lemma, ana.gramm, ana.gloss)

# You can also pass lists (even nested lists) and specify
# output format ('xml' or 'json')
# If you pass a list, you will get a list of analyses
# with the same structure
analyses = a.analyze_words([['А'], ['Мон', 'тонэ', 'яратӥсько', '.']],
	                       format='xml')
analyses = a.analyze_words(['Морфологияез', [['А'], ['Мон', 'тонэ', 'яратӥсько', '.']]],
	                       format='json')
```

Refer to the [uniparser-morph documentation](https://uniparser-morph.readthedocs.io/en/latest/) for the full list of options.

### Word lists
Alternatively, you can use a preprocessed word list. The ``wordlists`` directory contains a list of words from a 10-million-word [Udmurt corpus](http://udmurt.web-corpora.net/) (``wordlist.csv``), list of analyzed tokens (``wordlist_analyzed.txt``; each line contains all possible analyses for one word in an XML format), and list of tokens the parser could not analyze (``wordlist_unanalyzed.txt``). The recall of the analyzer on the corpus texts is about 96% and the corpus is sufficiently large, so if you just use the analyzed word list, the recall on your texts will almost definitely exceed 90%.

## Description format
The description is carried out in the ``uniparser-morph`` format and involves a description of the inflection (paradigms.txt), a grammatical dictionary (udm_lexemes_XXX.txt files), a list of rules that annotate combinations of lexemes and grammatical values with additional Russian translations (lex_rules.txt), and a short list of analyses that should be avoided (bad_analyses.txt). The dictionary contains descriptions of individual lexemes, each of which is accompanied by information about its stem, its part-of-speech tag and some other grammatical/borrowing information, its inflectional type (paradigm), and Russian translation. See more about the format [in the uniparser-morph documentation](https://uniparser-morph.readthedocs.io/en/latest/format.html).

## Disambiguation rules
Apart from the analyzer, this repository contains a set of [Constraint Grammar](https://visl.sdu.dk/constraint_grammar.html) rules that can be used to partial disambiguation of analyzed Udmurt texts. They reduce the average number of different analyses per analyzed token from about 1.6 to about 1.3. As of now, they are **not** taken into account by the Python module; you will have to apply them yourself to the data analyzed by ``uniparser_udmurt``.