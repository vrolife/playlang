import os
import io
import inspect
import logging
import collections
from typing import Union


class TerminalPrecedence:
    ASSOC_SHIFT = 0
    ASSOC_LEFT = 1
    ASSOC_RIGHT = 2
    ASSOC_NONE = 3

    def __init__(self, precedence, assoc=ASSOC_SHIFT):
        self.precedence = precedence
        self.associative = assoc

    def __repr__(self):
        assoc = ['Shift', 'Left', 'Right', 'None'][self.associative]
        return f'Precedence({self.precedence}, {assoc})'

    def __gt__(self, other):
        return self.precedence.__gt__(other.precedence)

    def __ge__(self, other):
        return self.precedence.__ge__(other.precedence)

    def __lt__(self, other):
        return self.precedence.__lt__(other.precedence)

    def __le__(self, other):
        return self.precedence.__le__(other.precedence)


class Terminal(collections.UserDict):
    def __init__(self, name: str, fullname: str, precedence: TerminalPrecedence):
        super().__init__(self)
        self.precedence = precedence
        self.data['name'] = name
        self.data['fullname'] = fullname
        self.data['show_name'] = name

    def __hash__(self):
        return self.fullname.__hash__()

    @property
    def pattern(self):
        return self.data.get('pattern', None)

    @property
    def ignorable(self):
        return self.data.get('ignorable', False)

    @property
    def discard(self):
        return self.data.get('discard', False)

    @property
    def capture(self):
        return self.data.get('capture', False)

    @property
    def show_name(self):
        return self.data['show_name']

    @property
    def fullname(self):
        return self.data['fullname']

    @property
    def name(self):
        return self.data['name']

    @property
    def is_eof(self):
        return self.data.get('is_eof', False)

    def __repr__(self):
        return self.name


class RuleInfo:
    def __init__(self, components, precedence: Union[TerminalPrecedence, Terminal]):
        self.components = components
        self.precedence = precedence


class SymbolInfo(collections.UserDict):
    def __init__(self):
        super().__init__(self)
        self.rules = []
        self.action = None


class Rule:
    def __init__(self, *components, precedence: Union[TerminalPrecedence, Terminal] = None):
        self._components = components
        self._precedence = precedence

    def __call__(self, arg):
        if isinstance(arg, SymbolInfo):
            arg.rules.append(RuleInfo(self._components, self._precedence))
            return arg
        else:
            si = SymbolInfo()
            si.rules.append(RuleInfo(self._components, self._precedence))
            if isinstance(arg, staticmethod):
                si.action = arg.__func__
            else:
                si.action = arg
            return si


class Symbol(collections.UserDict):
    def __init__(self, name, fullname):
        super().__init__(self)
        self._rules = []
        self.data['name'] = name
        self.data['fullname'] = fullname
        self.data['show_name'] = name

    def __hash__(self):
        return self.fullname.__hash__()

    def __repr__(self):
        return self.name

    @property
    def show_name(self):
        return self.data['show_name']

    @property
    def fullname(self):
        return self.data['fullname']

    @property
    def name(self):
        return self.data['name']

    @property
    def rules(self):
        return self._rules


class SymbolRule:
    def __init__(self,
                 symbol: Symbol,
                 components: Union[list, tuple],
                 action: callable = None,
                 precedence=None,
                 extra_info=None):
        if not isinstance(components, (list, tuple)):
            print(components)
            raise TypeError('expect tuple or list')

        if isinstance(precedence, Terminal):
            precedence = precedence.precedence
        elif precedence is None:
            precedence = TerminalPrecedence(0)
            for c in components:
                if isinstance(c, Terminal):
                    if precedence > c.precedence and logging.getLogger().isEnabledFor(logging.DEBUG):
                        logging.debug(
                            'rule bind to lower precedence. %s', {components})
                    precedence = c.precedence

        assert isinstance(precedence, TerminalPrecedence)

        self.symbol = symbol
        self._action = action
        self._components = components
        self.precedence = precedence
        self._component_count = len(components)

        if extra_info is None:
            self.extra_info = {}
        else:
            self.extra_info = extra_info

    @property
    def action(self):
        return self._action

    def __len__(self):
        return self._component_count

    def __repr__(self):
        detail = ''
        if self._action is not None:
            line_number = inspect.getsourcelines(self._action)[1]
            file = os.path.basename(inspect.getsourcefile(self._action))
            detail = f'{file}:{line_number}'
        return f'{{ {self.symbol} -> {self._components} <{detail}> }}'

    def __iter__(self):
        return self._components.__iter__()


class State:
    def __init__(self):
        # the rule generate this state
        self.bind_rule = None

        # for sort
        self.bind_index = None

        # reduce in this rule. possible different to bind_rule after merged
        self.reduce_rule = None

        self._branchs = {}

        # see StateIter
        self._tokens = []
        self._immediate_tokens = None

    def __repr__(self):
        return self._tokens.__repr__()

    def __contains__(self, token):
        return token in self._branchs

    @property
    def tokens(self):
        return self._tokens

    @property
    def immediate_tokens(self):
        return self._immediate_tokens

    @property
    def branchs(self):
        return self._branchs

    def _copy_tokens(self):
        self._immediate_tokens = tuple(self._tokens)

    def set_branch(self, token, state):
        self._tokens.append(token)
        self._branchs[token] = state

    def get_branch(self, token):
        return self._branchs.get(token)

    def __iter__(self):
        # Support append while iterating
        class StateIter:
            def __init__(self, state):
                self._state = state
                self._index = -1

            def __next__(self):
                self._index += 1
                if self._index >= len(self._state.tokens):
                    raise StopIteration()
                t = self._state.tokens[self._index]
                return t, self._state.branchs[t]

        return StateIter(self)


class Location:
    def __init__(self, line_num=1, column=1, filename=None):
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
        self._column = 1
        return None

    def step(self, n):
        self._column += n
        return None

    def copy(self):
        return Location(self._line_num, self._column, self._filename)

    def __repr__(self):
        return f'{self._filename}:{self._line_num}+{self._column}'


class TokenValue:
    def __init__(self, token: Union[Symbol, Terminal], value, location: Location = None):
        self.token = token
        self.value = value
        self.location = location

    def __repr__(self):
        buf = io.StringIO()
        buf.write(self.token.__repr__())

        if self.location is not None:
            buf.write(':')
            buf.write(self.location.__repr__())

        buf.write('="')
        buf.write(str(self.value))
        buf.write('"')

        return buf.getvalue()


class TokenInfo(collections.UserDict):
    pass


def Action(action):
    ti = TokenInfo()
    ti.data['action'] = action
    return ti


def Token(pattern=None,
          discard=False,
          ignorable=False,
          is_eof=False,
          **kwargs) -> TokenInfo:
    """Define a token

    Args:
        pattern ([type], optional): regexp for this token. Defaults to None.
        discard (bool, optional): read and discard by scanner. Defaults to False.
        ignorable (bool, optional): ignore this token if it cause a syntax error. Defaults to False.
        eof (bool, optional): this token is a End-Of-File token.
                              arguemnt `pattern will be ignore`. Defaults to False.
        action (callable, optional) scanner action. Defaults to None.
        show_name (callable, optional) human readable name. Defaults to None.
    Returns:
        TokenInfo: this value will be replace by meta class Parser
    """

    ti = TokenInfo()
    ti.data['pattern'] = pattern
    ti.data['discard'] = discard
    ti.data['ignorable'] = ignorable
    ti.data['is_eof'] = is_eof
    ti.data.update(kwargs)
    return ti


class Precedence:
    class Left:
        pass

    class Right:
        pass

    class Increase:
        pass


class Start:
    def __init__(self, symbol: Symbol):
        self.symbol = symbol

# start condition
class Scanner:
    def __init__(self, *tokens, name='__default__', capture: Terminal = None):
        self.tokens = tokens
        self.name = name
        self.eof_token = None
        for tok in tokens:
            if tok.is_eof:
                self.eof_token = tok
        if capture is not None:
            capture.data['capture'] = True
            self.tokens = list(tokens)
            self.tokens.append(capture)


class StaticField:
    def create(self, parser):
        raise NotImplementedError()


class ShowName:
    def __init__(self, name):
        self._name = name

    def __call__(self, si):
        if isinstance(si, SymbolInfo):
            si.data['show_name'] = self._name
            return si
        elif isinstance(si, TokenInfo):
            si.data['show_name'] = self._name
            return si
        raise TypeError(f'unsupported target: {si}')
