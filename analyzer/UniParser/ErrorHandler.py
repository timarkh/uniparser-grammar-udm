import json


class ErrorHandler:
    """
    Class for logging the error messages. Normally, a single
    instance of this class should be stored in the Grammar class.
    Currently, all error messages are written to a file.
    """

    def __init__(self, filename='errors.log'):
        self.log = []
        self.logFileName = filename
        self.f = open(self.logFileName, 'w', encoding='utf-8')
        self.f.close()

    def __deepcopy__(self, memo):
        return self

    def raise_error(self, errorMessage, data=None):
        if data is not None:
            try:
                dataStr = json.dumps(data, ensure_ascii=False)
                errorMessage += dataStr
            except:
                pass
        self.log.append(errorMessage)
        f = open(self.logFileName, 'a', encoding='utf-8')
        f.write(errorMessage + '\n')
        f.close()


if __name__ == '__main__':
    eh = ErrorHandler()
