import re

REDUPL_SIDE_RIGHT = True
REDUPL_SIDE_LEFT = False


class RegexTest:
    """
    A class that represents a regex-based test used to decide
    whether an inflexion should be able to attach to a certain
    stem or a certain other inflection.
    """
    def __init__(self, field, sTest, errorHandler=None):
        self.errorHandler = errorHandler
        self.field = field
        self.sTest = sTest
        try:
            self.rxTest = re.compile(self.sTest, flags=re.U)
        except:
            self.raise_error('Wrong regex in the test for field ' +
                             self.field + ': ' + self.sTest)
            self.rxTest = re.compile('', flags=re.U)

    def raise_error(self, message, data=None):
        if self.errorHandler is not None:
            self.errorHandler.RaiseError(message, data)

    def __deepcopy__(self, memo):
        newObj = RegexTest(self.field, self.sTest, self.errorHandler)
        return newObj

    def perform(self, s):
        # print('regex: ' + s)
        return self.rxTest.search(s) is not None

    def __repr__(self):
        return '<' + self.field + ': \'' + self.sTest + '\'>'


class Replacement:
    def __init__(self, dictRepl, errorHandler=None):
        self.errorHandler = errorHandler
        self.rxWhat = None
        self.sWhat = ''
        self.sWith = ''
        if len(dictRepl['value']) > 0:
            self.sWhat, self.sWith = self.short_repl(dictRepl['value'])
        else:
            self.sWhat = ''
            self.sWith = ''
            for obj in dictRepl['content']:
                if obj['name'] == 'what':
                    self.sWhat = obj['value']
                elif obj['name'] == 'with':
                    self.sWith = obj['value']
                    # print self.sWith
                else:
                    self.raise_error('Unrecognized field in a replacement description: ',
                                     obj)
        self.compile_replacement()

    def short_repl(self, s):
        m = re.search('^(.*?) *-> *(.*)$', s, flags=re.U)
        if m is None:
            self.raise_error('Wrong replacement description: ' + s)
            return '^$', ''
        return m.group(1), m.group(2)

    def compile_replacement(self):
        try:
            self.rxWhat = re.compile(self.sWhat, flags=re.U|re.DOTALL)
        except:
            self.raise_error('Wrong regex in a replacement description: ' +
                             self.sWhat)

    def convert(self, s):
        # print 'Conversion: ' + s
        # print 'Regexp: ' + self.sWith
        try:
            s = self.rxWhat.sub(self.sWith, s)
            # print 'Result: ' + s
        except:
            self.raise_error('Incorrect regex in a replacement description: ',
                             self.rxWhat)
        return s

    def raise_error(self, message, data=None):
        if self.errorHandler is not None:
            self.errorHandler.RaiseError(message, data)

    def __deepcopy__(self, memo):
        dictDescr = {'name': 'replace', 'value': '',
                     'content': [{'name': 'what', 'value': self.sWhat},
                                  {'name': 'with', 'value': self.sWith}]}
        newObj = Replacement(dictDescr, self.errorHandler)
        return newObj


class Reduplication:
    def __init__(self, arrDescr, errorHandler=None):
        self.errorHandler = errorHandler
        self.replacements = []
        self.side = REDUPL_SIDE_RIGHT
        for obj in arrDescr:
            if obj['name'] == 'side':
                self.change_side(obj)
            elif obj['name'] == 'replace':
                self.replacements.append(Replacement(obj, self.errorHandler))
            else:
                self.raise_error('Unrecognized field in a reduplication description: ',
                                 obj)

    def raise_error(self, message, data=None):
        if self.errorHandler is not None:
            self.errorHandler.RaiseError(message, data)

    def change_side(self, side):
        if side['value'] == 'right':
            self.side = REDUPL_SIDE_RIGHT
        elif side['value'] == 'left':
            self.side = REDUPL_SIDE_LEFT
        else:
            self.raise_error('Unrecognized value in a reduplication description: ',
                             side)

    def perform(self, s):
        """Perform the reduplication on a string."""
        for repl in self.replacements:
            s = repl.convert(s)
        return s
