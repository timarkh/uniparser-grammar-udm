import reduplication
import lexeme
import copy


class LexRule:
    """
    A class that represents a regex-based second order lexical
    rule. Rules are applied after the primary morphological
    analysis has been completed and are used to add fields
    to the words which have certain combinations of features
    in their morphological analyses.
    Each rule must indicate either a lemma or a stem to which
    it is applicable.
    """
    def __init__(self, dictRule, errorHandler=None):
        self.errorHandler = errorHandler
        self.rxWhat = None
        self.stem = None
        self.lemma = None
        self.searchFields = []
        self.addFields = []
        for obj in dictRule['content']:
            if obj['name'] == 'search':
                self.process_search(obj['content'])
            elif obj['name'] == 'add':
                self.process_add(obj['content'])
            else:
                self.raise_error('Unrecognized field in a lexical rule description: ',
                                 obj)

    def raise_error(self, message, data=None):
        if self.errorHandler is not None:
            self.errorHandler.RaiseError(message, data)

    def apply(self, wf):
        if wf.stem != self.stem and wf.lemma != self.lemma:
            return None
        for rxTest in self.searchFields:
            if not lexeme.check_for_regex(wf, rxTest, errorHandler=self.errorHandler,
                                          checkWordform=True):
                return None
        wfNew = copy.deepcopy(wf)
        wfNew.otherData += self.addFields
        return wfNew

    def process_search(self, dictRules):
        for rule in dictRules:
            field = rule['name']
            value = rule['value']
            if type(value) != str:
                self.raise_error('Wrong field in a lexical rule.', value)
                continue
            if field == 'lex':
                self.lemma = value
            elif field == 'stem':
                self.stem = value
            else:
                self.searchFields.append(reduplication.RegexTest(field, value,
                                                                 errorHandler=self.errorHandler))

    def process_add(self, dictRules):
        for rule in dictRules:
            field = rule['name']
            value = rule['value']
            self.addFields.append((field, value))
