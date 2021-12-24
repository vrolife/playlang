import logging
import os
import inspect
from playlang.api import *


class _Precedence:
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


class Terminal:
    def __init__(self, name, precedence, ignorable=False):
        self.name = name
        self.precedence = precedence
        self.ignorable = ignorable

    def __repr__(self):
        return self.name


class SymbolRule:
    def __init__(self, symbol, elements, action, precedence, extra_info=None):
        self.symbol = symbol
        self.action = action
        self._elements = elements
        self.precedence = precedence
        self._element_count = len(elements)

        if extra_info is None:
            self.extra_info = {}
        else:
            self.extra_info = extra_info

        if action is not None:
            param_num = len(inspect.signature(action).parameters)
            if param_num == self._element_count:
                self._pass_context = False
            elif param_num == (self._element_count + 1):
                self._pass_context = True
            else:
                raise TypeError(
                    f'{self.__repr__()} require {self._element_count} or {self._element_count + 1} parameters')

    def __len__(self):
        return self._element_count

    def __repr__(self):
        detail = ''
        try:
            line_number = inspect.getsourcelines(self.action)[1]
            file = os.path.basename(inspect.getsourcefile(self.action))
            detail = f':{file}:{line_number}'
        except:
            pass
        return f'Rule<{self.symbol}{detail}>[{self._elements}]'

    def __call__(self, token_reader, context=None):
        if self.action is not None:
            args = []
            if self._pass_context:
                args.append(context)

            for tv in token_reader.consume(self._element_count):
                args.append(tv.value)
            value = self.action(*args)
        else:
            token_reader.consume(self._element_count)
            value = None

        token_reader.commit(TokenValue(self.symbol, value))
        return self._element_count

    def __iter__(self):
        return self._elements.__iter__()


class Symbol:
    def __init__(self, name):
        assert (name)
        self.name = name
        self._rules = []

    def __repr__(self):
        return self.name

    @property
    def rules(self):
        return self._rules

    def add_rule(self, *rule, action=None, precedence=None, extra_info=None):
        if len(rule) > 0 and isinstance(rule[0], (list, tuple)):
            rule = rule[0]

        if isinstance(precedence, Terminal):
            precedence = precedence.precedence
        elif precedence is None:
            precedence = _Precedence(0)
            for t in rule:
                if isinstance(t, Terminal):
                    if precedence > t.precedence:
                        logging.debug(f'rule bind to lower precedence. {rule}')
                    precedence = t.precedence

        assert isinstance(precedence, _Precedence)

        rule = SymbolRule(self, rule, action, precedence,
                          extra_info=extra_info)
        self._rules.append(rule)


# Support append while iterating
class StateIter:
    def __init__(self, state):
        self._state = state
        self._index = -1

    def __next__(self):
        self._index += 1
        if self._index >= len(self._state._tokens):
            raise StopIteration()
        t = self._state._tokens[self._index]
        return t, self._state._branchs[t]


class State:
    def __init__(self):
        # the rule generate this state
        self._bind_rule = None

        # reduce in this rule. possible different to bind_rule after merged
        self.reduce_rule = None

        self._branchs = {}

        # see StateIter
        self._tokens = []

    def __repr__(self):
        return self._tokens.__repr__()

    def __contains__(self, token):
        return token in self._branchs

    @property
    def branchs(self):
        return self._branchs

    def set_branch(self, token, state):
        self._tokens.append(token)
        self._branchs[token] = state

    def get_branch(self, token):
        return self._branchs.get(token)

    def __iter__(self):
        return StateIter(self)
