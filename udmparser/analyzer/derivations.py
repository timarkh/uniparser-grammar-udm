import grammar
import copy
import json
import re
from paradigm import Paradigm


def deriv_for_paradigm(paradigm):
    """
    Generate a Derivation object for the given paradigm.
    """
    derivLinks = {}     # recurs_class -> set of Derivation names
    maxRecursClass = 0
    for derivLink in paradigm.derivLinks:
        recursClass, derivLink = get_recurs_class(derivLink)
        # print(recursClass, derivLink['value'])
        if maxRecursClass < recursClass:
            maxRecursClass = recursClass
        pName = fork_deriv(derivLink, paradigm.name)
        if len(pName) > 0:
            try:
                derivLinks[recursClass].add(pName)
            except KeyError:
                derivLinks[recursClass] = {pName}
    handle_recurs_classes(derivLinks, maxRecursClass)
    unifiedDerivContent = []
    for derivNamesSet in derivLinks.values():
        for derivName in derivNamesSet:
            unifiedDerivContent.append({'name': 'paradigm',
                                        'value': derivName,
                                        'content': []})
    if len(unifiedDerivContent) <= 0:
        return
    unifiedName = '#deriv#paradigm#' + paradigm.name
    unifiedDeriv = Derivation({'name': 'deriv-type', 'value': unifiedName,
                               'content': unifiedDerivContent})
    grammar.Grammar.derivations[unifiedName] = unifiedDeriv


def fork_deriv(derivLink, paradigmName):
    """
    Create a new derivation with customized properties on the basis
    of an existing one.
    Return the name of the resulting derivation.
    """
    derivName = derivLink['value']
    try:
        newDeriv = copy.deepcopy(grammar.Grammar.derivations['#deriv#' +
                                                             derivName])
    except KeyError:
        grammar.Grammar.raise_error('No derivation named ' + derivName)
        return ''
    existingParadigms = newDeriv.find_property('paradigm')
    if len(existingParadigms) <= 0:
        newDeriv.add_property('paradigm', paradigmName)
    if derivLink['content'] is not None:
        for propName in {obj['name'] for obj in derivLink['content']}:
            newDeriv.del_property(propName)
        for obj in derivLink['content']:
            newDeriv.add_property(obj['name'], obj['value'])
    newDerivName = newDeriv.dictDescr['value'] + '#paradigm#' + paradigmName
    newDeriv.dictDescr['value'] = newDerivName
    grammar.Grammar.derivations[newDerivName] = newDeriv
    return newDerivName


def get_recurs_class(derivLink):
    """Find the recurs_class property in the contents.
    Return its value and the dictionary with recurs_value removed."""
    recursClass = 0
    if derivLink['content'] is None or len(derivLink['content']) <= 0:
        return 0, derivLink
    newDerivLink = copy.deepcopy(derivLink)
    for iObj in range(len(newDerivLink['content']))[::-1]:
        obj = newDerivLink['content'][iObj]
        if obj['name'] == 'recurs_class':
            try:
                recursClass = int(obj['value'])
            except ValueError:
                grammar.Grammar.raise_error('Incorrect recurs_class value: ' +
                                            obj['value'])
            newDerivLink['content'].pop(iObj)
    return recursClass, newDerivLink


def handle_recurs_classes(derivLinks, maxRecursClass):
    """
    For every derivation in the dictionary, add links to the derivations
    with recurs_class less than recurs_class of that derivation.
    """
    links = []
    restrictedDerivs = set([re.sub('#paradigm#[^#]+$', '', dv)
                            for s in derivLinks.values() for dv in s])
    prevDerivLinks = set()
    for recursClass in range(maxRecursClass + 1):
        try:
            curDerivLinks = derivLinks[recursClass]
            restrictedDerivs -= set([re.sub('#paradigm#[^#]+$', '', dv)
                                     for dv in prevDerivLinks])
            curRestrictedDerivs = copy.deepcopy(restrictedDerivs)
            prevDerivLinks = curDerivLinks
        except KeyError:
            # print('No recurs_class ' + str(recursClass))
            continue
        linksExtension = []
        for derivName in curDerivLinks:
            try:
                deriv = grammar.Grammar.derivations[derivName]
            except KeyError:
                grammar.Grammar.raise_error('No derivation named ' + derivName)
                continue
            for link in links:
                deriv.add_dict_property(link)
            deriv.restrictedDerivs = curRestrictedDerivs
            if recursClass < maxRecursClass:
                newLink = {'name': 'paradigm', 'value': derivName,
                           'content': [copy.deepcopy(p)
                                       for p in deriv.find_property('paradigm')]}
                for link in links:
                    newLink['content'].append(copy.deepcopy(link))
                linksExtension.append(newLink)
        links += linksExtension


def add_restricted(recursCtr, restrictedDerivs):
    recursCtr = recursCtr.copy()
    for rd in restrictedDerivs:
        recursCtr[rd] = grammar.Grammar.RECURS_LIMIT + 1
    return recursCtr


def extend_leaves(data, sourceParadigm, recursCtr=None,
                  removeLong=False, depth=0):
    # recursCtr: derivation name -> number of times it has been used
    if recursCtr is None:
        recursCtr = {}
    depth += 1
    data2add = []
    # print(json.dumps(recursCtr, indent=1))
    # print(len(recursCtr), max([0] + recursCtr.values()))
    for iObj in range(len(data))[::-1]:
        obj = data[iObj]
        if obj['name'] != 'paradigm':
            continue
        elif obj['value'].startswith('#deriv#'):
            shortName = re.sub('#paradigm#[^#]+$', '',
                               obj['value'], flags=re.U)
            try:
                recursCtr[shortName] += 1
            except KeyError:
                recursCtr[shortName] = 1
            if recursCtr[shortName] > grammar.Grammar.RECURS_LIMIT or \
                    depth > grammar.Grammar.DERIV_LIMIT:
                if removeLong:
                    data.pop(iObj)
                continue
            try:
                deriv = grammar.Grammar.derivations[obj['value']]
            except KeyError:
                continue
            recursCtrNext = add_restricted(recursCtr, deriv.restrictedDerivs)
            extend_leaves(obj['content'], sourceParadigm,
                          recursCtrNext, removeLong, depth)
        else:
            # print obj['value']
            if depth > grammar.Grammar.DERIV_LIMIT or obj['value'] == sourceParadigm:
                continue
            try:
                deriv = grammar.Grammar.derivations['#deriv#paradigm#' +
                                                    obj['value']]
            except KeyError:
                continue
            subsequentDerivs = copy.deepcopy(deriv.find_property('paradigm'))
            # print(json.dumps(subsequentDerivs, indent=1))
            recursCtrNext = add_restricted(recursCtr, deriv.restrictedDerivs)
            extend_leaves(subsequentDerivs, sourceParadigm,
                          recursCtrNext, True, depth)
            data2add += subsequentDerivs
    data += data2add


class Derivation:
    """
    An auxiliary class where derivations are represented by dictionaries.
    After priorities are handled, all derivations should be transformed into
    paradigms.
    """

    def __init__(self, dictDescr, errorHandler=None):
        self.dictDescr = copy.deepcopy(dictDescr)
        if self.dictDescr['content'] is None:
            self.dictDescr['content'] = []
        if errorHandler is None:
            self.errorHandler = grammar.Grammar.errorHandler
        else:
            self.errorHandler = errorHandler
        self.restrictedDerivs = set()

    def raise_error(self, message, data=None):
        if self.errorHandler is not None:
            self.errorHandler.raise_error(message, data)

    def content(self):
        return self.dictDescr['content']

    def find_property(self, propName):
        return [el for el in self.content() if el['name'] == propName]

    def add_property(self, name, value):
        self.dictDescr['content'].append({'name': name, 'value': value,
                                          'content': []})

    def add_dict_property(self, dictProperty):
        self.dictDescr['content'].append(copy.deepcopy(dictProperty))

    def del_property(self, propName):
        for iObj in range(len(self.dictDescr['content']))[::-1]:
            obj = self.dictDescr['content'][iObj]
            if obj['name'] == propName:
                self.dictDescr['content'].pop(iObj)

    def __str__(self):
        return json.dumps(self.dictDescr, ensure_ascii=False, indent=2)

    def build_links(self):
        """Add the links from all subsequent derivations to self."""
        newDerivLinks = []
        for derivLink in self.find_property('paradigm'):
            if (not derivLink['value'].startswith('#deriv#')) or\
                (derivLink['content'] is not None and
                 len(derivLink['content']) > 0):
                newDerivLinks.append(derivLink)
                continue
            newDerivLink = copy.deepcopy(derivLink)
            try:
                targetDeriv = grammar.Grammar.derivations[newDerivLink['value']]
            except KeyError:
                self.raise_error('No derivation named ' + newDerivLink['value'])
                continue
            newDerivLink['content'] = \
                copy.deepcopy(targetDeriv.find_property('paradigm'))
            newDerivLinks.append(newDerivLink)
        self.del_property('paradigm')
        for newDerivLink in newDerivLinks:
            self.add_dict_property(newDerivLink)

    def extend_leaves(self):
        """
        For the leaves in the subsequent derivation tree, which are
        real paradigms, add their subsequent derivations, if needed.
        """
        m = re.search('#deriv#paradigm#([^#]+$)', self.dictDescr['value'],
                      flags=re.U)
        if m is None:
            return
        paradigmName = m.group(1)
        recursCtr = {}
        for derivName in self.restrictedDerivs:
            recursCtr[derivName] = grammar.Grammar.RECURS_LIMIT + 1
        extend_leaves(self.dictDescr['content'], paradigmName, recursCtr)

    def to_paradigm(self):
        """
        Create a paradigm from self.dictDescr and return it.
        """
        return Paradigm(self.dictDescr, self.errorHandler)
