from playlang.errors import *
from playlang.objects import *


# Support modify during iteration
class StateIter:
    def __init__(self, state):
        self._state = state
        self._index = -1

    def __next__(self):
        self._index += 1
        if self._index >= len(self._state._tokens):
            raise StopIteration()
        t = self._state._tokens[self._index]
        return t, self._state._next_states[t]


class State:
    def __init__(self):
        # the rule generate this state
        self.bind_rule = None

        self.bind_index = None

        # reduce in this rule. possible different to bind_rule after merged
        self.reduce_rule = None

        self._next_states = {}

        # see StateIter
        self._tokens = []

    def __contains__(self, token):
        return token in self._next_states

    @property
    def next_states(self):
        return self._next_states

    @property
    def tokens(self):
        return list(self._next_states.keys())

    def set_next_state(self, token, state):
        self._tokens.append(token)
        self._next_states[token] = state

    def get_next_state(self, token):
        return self._next_states.get(token)

    def __iter__(self):
        return StateIter(self)


class Syntax:
    def __init__(self, auto_shift=True):
        self._auto_shift = auto_shift
        self._defined_symbols = {}
        self._defined_tokens = set()
        self._generated_states = {}
        self._pending_rules = {}
        self._merged_states = set()
        self._current_precedence = Precedence(0)
        self.__EOF__ = Token('__EOF__', self._current_precedence)

    def __call__(self, *rule, precedence=None, name=None):
        def dec(action):
            nonlocal name
            if isinstance(action, Symbol):
                symbol = action
                action.add(
                    rule, action=symbol.rules[-1].action, precedence=precedence)
                return action
            else:
                if name is None:
                    name = getattr(action, '__name__', None)
                    if name is None:
                        raise TypeError(f'unable to get the name of {action}')

                symbol = self.symbol(name)
                symbol.add(rule, action=action, precedence=precedence)
            return symbol

        return dec

    def symbol(self, name) -> Symbol:
        if name is None:
            raise TypeError('symbol name must be not none')

        symbol = self._defined_symbols.get(name)
        if symbol is None:
            symbol = Symbol(name)
            self._defined_symbols[name] = symbol

        return symbol

    def precedence(self):
        self._current_precedence = Precedence(self._current_precedence.precedence + 1)

    def left(self):
        self._current_precedence = Precedence(self._current_precedence.precedence + 1, Precedence.ASSOC_LEFT)

    def right(self):
        self._current_precedence = Precedence(self._current_precedence.precedence + 1, Precedence.ASSOC_RIGHT)

    def nonassoc(self):
        self._current_precedence = Precedence(self._current_precedence.precedence + 1, Precedence.ASSOC_NONE)

    def token(self, name, **kwargs) -> Token:
        if name in self._defined_tokens:
            raise TypeError(f'duplicate token {name}')

        self._defined_tokens.add(name)
        return Token(name, precedence=self._current_precedence, **kwargs)

    def generate(self, symbol):
        def reduce(v, _):
            return v

        start = Symbol(name='__START__')
        start.add([symbol, self.__EOF__], action=reduce)

        root_state = self._generate_from(start)

        self._merge(root_state)

        setattr(root_state, '__EOF__', self.__EOF__)
        setattr(root_state, '__START__', start)
        return root_state

    def _generate_from(self, start):
        state = self._generated_states.get(start)
        if state is None:
            state = State()
            self._generated_states[start] = state

        rules = self._pending_rules.get(start)
        if rules is None:
            rules = start.rules[:]
            self._pending_rules[start] = rules

        while len(rules) > 0:
            rule = rules.pop()
            iter = enumerate(rule)
            self._generate_for_symbol(start, state, rule, iter)

        return state

    def _generate_for_symbol(self, symbol, state, rule, iter):
        try:
            index, element = iter.__next__()

            if element not in state:
                next_state = State()
                next_state.bind_rule = rule
                next_state.bind_index = index
                state.set_next_state(element, next_state)
            else:
                next_state = state.get_next_state(element)

                # rebind
                if rule.precedence > next_state.bind_rule.precedence:
                    next_state.bind_rule = rule

            # try next
            self._generate_for_symbol(symbol, next_state, rule, iter)

            if isinstance(element, Symbol):
                self._generate_from(element)
        except StopIteration:
            state.reduce_rule = rule

    def _should_reduce(self, reduce, shift):
        if reduce._precedence > shift._precedence:
            return True
        if reduce._precedence < shift._precedence:
            return False
        else:  # ==
            if reduce._associative != shift._associative:
                raise ConflictShiftReduceError('shift/reduce conflict')

            if reduce._associative == Precedence.ASSOC_LEFT:
                return True

            if not self._auto_shift:
                raise ConflictShiftReduceError('shift/reduce conflict')

            # shift default
            return False

    def _should_override(self, to, _from):
        if to._precedence > _from._precedence:
            return True
        if to._precedence < _from._precedence:
            return False
        else:  # ==
            raise ConflictReduceReduceError('reduce/reduce conflict')

    def _merge_state(self, state, element_state):
        if state is element_state:
            return

        if element_state.reduce_rule is not None:
            if state.reduce_rule is None:
                # precedence ?
                state.reduce_rule = element_state.reduce_rule
            elif state.reduce_rule is not element_state.reduce_rule:
                if self._should_override(state.reduce_rule.precedence, element_state.reduce_rule.precedence):
                    state.reduce_rule = element_state.reduce_rule

        for next_element, next_state in element_state:
            if next_element in state:
                exist_state = state.get_next_state(next_element)

                if exist_state.reduce_rule is not None:
                    # see self.gen: #rebind
                    if self._should_reduce(exist_state.bind_rule.precedence,
                                           next_state.bind_rule.precedence):
                        # discard, we don't merge a low precedence state to high precedence state
                        continue

                self._merge_state(exist_state, next_state)

            else:
                if state.reduce_rule is not None:
                    if self._should_reduce(state.reduce_rule.precedence,
                                           next_state.bind_rule.precedence):
                        # percent extend state chain with low precedence state
                        continue
                state.set_next_state(next_element, next_state)

    def _merge(self, state):
        for element, _ in state:
            if isinstance(element, Symbol):
                element_state = self._generated_states[element]
                self._merge_state(state, element_state)

        self._merged_states.add(state)
        for element, next_state in state:
            if next_state not in self._merged_states:
                self._merge(next_state)


class TokenReader:
    def __init__(self, tokenizer, start, eof):
        self._tokenizer = tokenizer
        self._start = start
        self._eof = eof
        self._stack = []
        self._next_token = None

    def __repr__(self):
        return f'{self._stack}'

    def _read(self):
        try:
            return self._tokenizer.__next__()
        except StopIteration:
            return TokenValue(self._eof, None)
        except EOFError as e:
            location = None
            if isinstance(e.args[0], Location):
                location = e.args[0]
            return TokenValue(self._eof, None, location=location)

    def done(self):
        return len(self._stack) == 1 and self._stack[-1].token is self._start

    def top(self):
        return self._stack[-1]

    def peek(self):
        if self._next_token is None:
            self._next_token = self._read()
        return self._next_token

    def discard(self):
        self._next_token = None

    def read(self):
        t = self._next_token
        if t is None:
            t = self._read()
        else:
            self._next_token = None
        self._stack.append(t)

    def consume(self, n):
        if n == 0:
            return []
        a = self._stack[-n:]
        self._stack = self._stack[:-n]
        return a

    def commit(self, *a):
        self._stack.extend(a)

    def pop(self):
        return self._stack.pop()

    def push(self, tv):
        self._stack.append(tv)


class StateStack:
    def __init__(self, initial):
        self._stack = [initial]

    def __repr__(self):
        return f'{self._stack}'

    def top(self):
        return self._stack[-1]

    def pop(self, count=1):
        for _ in range(count):
            self._stack.pop()

    def push(self, state):
        self._stack.append(state)


def _parse(token_reader, state_stack, context):
    lookahead = token_reader.peek()
    while not token_reader.done():
        current_state = state_stack.top()
        next_state = current_state.get_next_state(lookahead.token)

        if next_state is not None:
            # shift
            if isinstance(lookahead.token, Token):
                token_reader.read()
            state_stack.push(next_state)
            lookahead = token_reader.peek()
        else:
            if isinstance(lookahead.token, Token) and lookahead.token.ignorable:
                token_reader.discard()
                lookahead = token_reader.peek()
                continue

            if current_state.reduce_rule is not None:
                # reduce
                n = current_state.reduce_rule(token_reader, context=context)
                state_stack.pop(n)
                lookahead = token_reader.top()
            else:
                raise SyntaxError(
                    f'unexpected token {lookahead}')


def parse(states, tokenizer, context=None):
    token_reader = TokenReader(tokenizer, states.__START__, states.__EOF__)
    state_stack = StateStack(states)
    _parse(token_reader, state_stack, context=context)
    return token_reader.pop().value
