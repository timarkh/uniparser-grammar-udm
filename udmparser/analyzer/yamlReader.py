import re


def read_file(fname, errorHandler=None):
    try:
        f = open(fname, 'r', encoding='utf-8-sig')
        lines = [re.sub(' *#.*', '', line.strip('\r\n'))
                 for line in f.readlines()]
        f.close()
    except IOError:
        if errorHandler is not None:
            errorHandler.raise_error('IOError: ' + fname +
                                     ' couldn\'t be opened.')
        return []
    arr, numLine = process_lines(lines, errorHandler)
    return arr


def process_lines(lines, errorHandler=None, startFrom=0, prevOffset=0):
    if startFrom == len(lines):
        return [], 0
    arr = []
    i = startFrom
    badObject = False
    while i < len(lines):
        line = lines[i]
        if re.search('^\\s*$', lines[i]) is not None:
            i += 1
            continue
        m = re.search('^( *)(-?)([^ :]+)((?::.*)?)$', line, flags=re.U)
        if m is None:
            if errorHandler is not None:
                errorHandler.raise_error('Line #' + str(i) + ' is wrong: ' +
                                         line)
            badObject = True
            i += 1
            continue
        if len(m.group(1)) < prevOffset:
            return arr, i
        elif len(m.group(1)) > prevOffset:
            if errorHandler is not None:
                errorHandler.raise_error('Wrong offset in line #' + str(i) +
                                         ': ' + line)
            badObject = True
            i += 1
            continue
        obj = {'name': m.group(3)}
        
        # "-lexeme" vs. "-paradigm: N1"
        if m.group(4) is not None:
            obj['value'] = re.sub('^: *| *$', '', m.group(4))
        else:
            obj['value'] = ''

        # "-paradigm: N1" vs. "gramm: N"
        if len(m.group(2)) == 0:
            obj['content'] = None
            i += 1
        else:
            obj['content'], i = process_lines(lines, errorHandler,
                                              i + 1, prevOffset + 1)
        if not badObject:
            arr.append(obj)
        badObject = False
    return arr, len(lines)
