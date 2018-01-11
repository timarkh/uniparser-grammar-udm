import re
import grammar
import reduplication


class PeriphrasticPart:
    """
    One part of a periphrastic construction.
    """
    MAX_SCOPE = 16   # max number of tokens parser will check with * or + quantifiers

    def __init__(self, text, quantifier='', errorHandler=None):
        if errorHandler is None:
            if self.errorHandler is None:
                self.errorHandler = grammar.Grammar.errorHandler
        else:
            self.errorHandler = errorHandler

        self.regexTests = []
        self.minQty = self.maxQty = 1
        if '=' not in text:
            self.wf = text.strip()
            return
        fields = re.findall('([^= \t]+) *= *"([.*?])(?<!\\\\)"',
                            text.strip())
        if len(fields) <= 0:
            self.raise_error('Wrong periphrastic construction: ' + text)
            return
        for field, test in fields:
            self.regexTests.append(reduplication.RegexTest(field, test,
                                                           self.errorHandler))
        if quantifier == '*':
            self.minQty = 0
            self.maxQty = PeriphrasticPart.MAX_SCOPE
        elif quantifier == '+':
            self.minQty = 1
            self.maxQty = PeriphrasticPart.MAX_SCOPE
        elif quantifier.startswith('{') and quantifier.endswith('}'):
            m = re.search('^\\{([0-9]*)(,?)([0-9]*)\\}$', quantifier)
            if m is None:
                self.raise_error('Wrong quantifier ' + quantifier + ' in ' + text)
            else:
                if len(m.group(1)) > 0:
                    self.minQty = int(m.group(1))
                else:
                    self.minQty = 0
                if len(m.group(3)) > 0:
                    self.maxQty = int(m.group(3))
                else:
                    if len(m.group(2)) > 0:
                        self.maxQty = PeriphrasticPart.MAX_SCOPE
                    else:
                        self.maxQty = self.minQty
        elif len(quantifier) > 0:
            self.raise_error('Wrong quantifier ' + quantifier + ' in ' + text)

    def raise_error(self, message, data=None):
        if self.errorHandler is not None:
            self.errorHandler.raise_error(message, data)


class Periphrastic:
    """
    A periphrastic construction.
    """
    def __init__(self, text, errorHandler=None):
        if errorHandler is None:
            if self.errorHandler is None:
                self.errorHandler = grammar.Grammar.errorHandler
        else:
            self.errorHandler = errorHandler

        parts = re.findall('\\[([^\\[\\]]+)\\]([^\\s\\[\\]]*)', text)
        if len(parts) <= 0:
            self.raise_error('Wrong periphrastic construction: ' + text)
            return
        self.periParts = [PeriphrasticPart(part, qty) for part, qty in parts]

    def raise_error(self, message, data=None):
        if self.errorHandler is not None:
            self.errorHandler.raise_error(message, data)
