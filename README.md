# Udmurt morphological analyzer
This is a rule-based morphological analyzer for Udmurt (``udm``; Uralic > Permic). It is based on a formalized description of literary Udmurt morphology, which also includes a number of dialectal elements, and uses [uniparser-morph](https://github.com/timarkh/uniparser-morph) for parsing. It performs full morphological analysis of Udmurt words (lemmatization, POS tagging, grammatical tagging, glossing).

## How to use
### Python package
The analyzer is available as a Python package. If you want to analyze Udmurt texts in Python, install the module:

```
pip3 install uniparser-udmurt
```

Import the module and create an instance of ``UdmurtAnalyzer`` class. Set ``mode='strict'`` if you are going to process text in the standard orthography (default value). Set ``mode='nodiacritics'`` if you expect some words to lack the diacritics (which often happens in social media), e.g. ``сыче`` instead of the correct ``сыӵе``. Set ``mode='oldorth'`` if you are processing texts written in one of the older, pre-standardized orthographies (earlier than late 1930s). Right now, apostrophes in place of ``ъ`` and some features of the pre-revolution orthography are accounted for, but not all of them.

After that, you can either parse tokens or lists of tokens with ``analyze_words()``, or parse a frequency list with ``analyze_wordlist()``. Here is a simple example:

```python
from uniparser_udmurt import UdmurtAnalyzer
a = UdmurtAnalyzer(mode='strict')

analyses = a.analyze_words('Морфологиез')
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
analyses = a.analyze_words(['Морфологиез', [['А'], ['Мон', 'тонэ', 'яратӥсько', '.']]],
	                       format='json')
```

Refer to the [uniparser-morph documentation](https://uniparser-morph.readthedocs.io/en/latest/) for the full list of options.

### Disambiguation
Apart from the analyzer, this repository contains a set of [Constraint Grammar](https://visl.sdu.dk/constraint_grammar.html) rules that can be used for partial disambiguation of analyzed Udmurt texts. They reduce the average number of different analyses per analyzed token from about 1.6 to about 1.3. If you want to use them, set ``disambiguation=True`` when calling ``analyze_words``:

```python
analyses = a.analyze_words(['Мон', 'тонэ', 'яратӥсько'], disambiguate=True)
```

In order for this to work, you have to install the ``cg3`` executable separately. On Ubuntu/Debian, you can use ``apt-get``:

```
sudo apt-get install cg3
```

On Windows, download the binary and add the path to the ``PATH`` environment variable. See [the documentation](https://visl.sdu.dk/cg3/single/#installation) for other options.

Note that each time you call ``analyze_words()`` with ``disambiguate=True``, the CG grammar is loaded and compiled from scratch, which makes the analysis even slower. If you are analyzing a large text, it would make sense to pass the entire text contents in a single function call rather than do it sentence-by-sentence, for optimal performance.

### Word lists
Alternatively, you can use a preprocessed word list. The ``wordlists`` directory contains a list of words from a 10-million-word [Udmurt corpus](http://udmurt.web-corpora.net/) (``wordlist.csv``), list of analyzed tokens (``wordlist_analyzed.txt``; each line contains all possible analyses for one word in an XML format), and list of tokens the parser could not analyze (``wordlist_unanalyzed.txt``). The recall of the analyzer on the corpus texts is about 96% and the corpus is sufficiently large, so if you just use the analyzed word list, the recall on your texts will almost definitely exceed 90%.

## Description format
The description is carried out in the ``uniparser-morph`` format and involves a description of the inflection (paradigms.txt), a grammatical dictionary (udm_lexemes_XXX.txt files), a list of rules that annotate combinations of lexemes and grammatical values with additional Russian translations (lex_rules.txt), and a short list of analyses that should be avoided (bad_analyses.txt). The dictionary contains descriptions of individual lexemes, each of which is accompanied by information about its stem, its part-of-speech tag and some other grammatical/borrowing information, its inflectional type (paradigm), and Russian translation. See more about the format [in the uniparser-morph documentation](https://uniparser-morph.readthedocs.io/en/latest/format.html).
