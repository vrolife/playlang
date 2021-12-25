import io


class Location:
    def __init__(self, line_num=0, column=0, filename=None):
        self._filename = filename
        self._line_num = line_num
        self._column = column

    @property
    def filename(self):
        return self._filename

    @property
    def line(self):
        return self._line_num

    @property
    def column(self):
        return self._column

    def lines(self, n):
        self._line_num += n
        self._column = 0
        return None

    def step(self, n):
        self._column += n
        return None

    def copy(self):
        return Location(self._line_num, self._column, self._filename)

    def __repr__(self):
        return f'{self._filename}:{self._line_num}+{self._column}'


class TokenValue:
    def __init__(self, token, value, location=None):
        self.token = token
        self.value = value
        self.location = location

    def __repr__(self):
        buf = io.StringIO()
        buf.write(self.token.__repr__())

        if self.location is not None:
            buf.write(':')
            buf.write(self.location.__repr__())

        buf.write('=')
        buf.write(str(self.value))

        return buf.getvalue()


class Precedence:
    class Left:
        pass

    class Right:
        pass

    class Increase:
        pass


class Start:
    def __init__(self, symbol):
        self.symbol = symbol


class ScanInfo:
    def __init__(self):
        self.tokens = {}
        self.contexts = {}


class Scan:
    def __init__(self, *tokens, name='__default__'):
        self.tokens = tokens
        self.name = name


class StaticField:
    def create(self, parser):
        raise NotImplementedError()


class TokenInfo(dict):
    pass


def Action(action):
    ti = TokenInfo()
    ti['action'] = action
    return ti


def Token(pattern,
          action=None,
          discard=False,
          ignorable=False,
          context=None,
          capture=False,
          token=None,
          eof=False,
          show_name=None,
          **extra_info):
    ti = TokenInfo()
    if capture:
        ti['capture'] = pattern
    else:
        ti['pattern'] = pattern
    ti['action'] = action
    ti['token'] = token
    ti['discard'] = discard
    ti['ignorable'] = ignorable
    ti['context'] = context
    ti['eof'] = eof
    ti['show_name'] = show_name
    ti.update(extra_info)
    return ti


class RuleInfo:
    def __init__(self, symbols, precedence):
        self.symbols = symbols
        self.precedence = precedence


class SymbolInfo:
    def __init__(self):
        self.rules = []
        self.action = None
        self.extra_info = {}
        self.show_name = None


class Rule:
    def __init__(self, *symbols, precedence=None):
        self._symbols = list(symbols)
        self._precedence = precedence

    def __call__(self, action):
        if isinstance(action, SymbolInfo):
            action.rules.append(RuleInfo(self._symbols, self._precedence))
            return action
        else:
            si = SymbolInfo()
            si.rules.append(RuleInfo(self._symbols, self._precedence))
            if isinstance(action, staticmethod):
                si.action = action.__func__
            else:
                si.action = action
            return si


class ShowName:
    def __init__(self, name):
        self._name = name

    def __call__(self, si):
        if isinstance(si, SymbolInfo):
            si.show_name = self._name
            return si
        raise TypeError('unsupported target: %s' % si)
