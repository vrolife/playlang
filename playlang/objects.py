import io
import os
import inspect


class Precedence:
    ASSOC_SHIFT = 0
    ASSOC_LEFT = 1
    ASSOC_RIGHT = 2
    ASSOC_NONE = 3

    def __init__(self, precedence, assoc=ASSOC_SHIFT):
        self._precedence = precedence
        self._associative = assoc

    def __repr__(self):
        assoc = ['Shift', 'Left', 'Right', 'None'][self._associative]
        return f'Precedence({self._precedence}, {assoc})'

    def __gt__(self, other):
        return self._precedence.__gt__(other._precedence)

    def __ge__(self, other):
        return self._precedence.__ge__(other._precedence)

    def __lt__(self, other):
        return self._precedence.__lt__(other._precedence)

    def __le__(self, other):
        return self._precedence.__le__(other._precedence)

    @property
    def precedence(self):
        return self._precedence


class MetaToken(type):
    def __getitem__(self, type):
        return TokenType(type)


class TokenIgnorable(metaclass=MetaToken):
    pass


class Token(metaclass=MetaToken):
    def __init__(self, name, precedence, ignorable=False):
        self.name = name
        self.precedence = precedence
        self.ignorable = ignorable

    def __repr__(self):
        return self.name


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


class TokenType:
    def __init__(self, type):
        self.type = type


class Location:
    def __init__(self, line_num=0, column=0, filename=None):
        self._filename = filename
        self._line_num = line_num
        self._column = column

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


class SymbolRule:
    def __init__(self, symbol, action, rule, precedence):
        self.symbol = symbol
        self.action = action
        self._rule = rule
        self.precedence = precedence
        self._rule_count = len(rule)

        if action is not None:
            param_num = len(inspect.signature(action).parameters)
            if param_num == self._rule_count:
                self._pass_context = False
            elif param_num == (self._rule_count + 1):
                self._pass_context = True
            else:
                raise TypeError(
                    f'{self.__repr__()} require {self._rule_count} or {self._rule_count + 1} parameters')

    def __len__(self):
        return self._rule_count

    def __repr__(self):
        detail = ''
        try:
            line_number = inspect.getsourcelines(self.action)[1]
            file = os.path.basename(inspect.getsourcefile(self.action))
            detail = f':{file}:{line_number}'
        except:
            pass
        return f'Rule<{self.symbol}{detail}>[{self._rule}]'

    def __call__(self, stack, context=None):
        if self.action is not None:
            args = []
            if self._pass_context:
                args.append(context)

            for tv in stack.consume(self._rule_count):
                args.append(tv.value)
            value = self.action(*args)
        else:
            stack.consume(self._rule_count)
            value = None

        stack.commit(TokenValue(self.symbol, value))
        return self._rule_count

    def __iter__(self):
        return self._rule.__iter__()


class Symbol:
    def __init__(self, name):
        assert (name)
        self.name = name
        self._rules = []

    def __repr__(self):
        return f'{self.name}|{super().__repr__()}|'

    @property
    def rules(self):
        return self._rules

    def add(self, *rule, action=None, precedence=None):
        if len(rule) > 0 and isinstance(rule[0], (list, tuple)):
            rule = rule[0]

        if isinstance(precedence, Token):
            precedence = precedence.precedence
        elif precedence is None:
            precedence = Precedence(0)
            for t in rule:
                if isinstance(t, Token):
                    precedence = t.precedence

        assert isinstance(precedence, Precedence)

        rule = SymbolRule(self, action, rule, precedence)
        self._rules.append(rule)

    def merge(self, symbol):
        for rule in symbol._rules:
            rule.symbol = self
            self._rules.append(rule)


class Rule:
    def __init__(self, *symbols, precedence=None, name=None):
        self._symbols = list(symbols)
        self._precedence = precedence
        self._name = name

    def __call__(self, action):
        if isinstance(action, Symbol):
            symbol = action
            symbol.add(self._symbols, action=symbol.rules[-1].action, precedence=self._precedence)
        else:
            if self._name is None:
                self._name = getattr(action, '__name__', None)
                if self._name is None:
                    raise TypeError(f'unable to get the name of {action}')
            symbol = Symbol(self._name)
            symbol.add(self._symbols, action=action, precedence=self._precedence)
        return symbol
