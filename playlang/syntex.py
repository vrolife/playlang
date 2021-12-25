import enum
from playlang.errors import *
from playlang.objects import _Precedence, Symbol, Terminal, State


class Syntax:
    def __init__(self, auto_shift=True):
        self._auto_shift = auto_shift
        self._defined_symbols = {}
        self._defined_tokens = set()
        self._generated_states = {}
        self._pending_rules = {}
        self._merged_states = set()
        self._current_precedence = _Precedence(0)

    def __call__(self, *rule, precedence=None, name=None):
        def dec(action):
            nonlocal name
            if isinstance(action, Symbol):
                symbol = action
                action.add_rule(
                    rule, action=symbol.rules[-1].action, precedence=precedence)
                return action
            else:
                if name is None:
                    name = getattr(action, '__name__', None)
                    if name is None:
                        raise TypeError(f'unable to get the name of {action}')

                symbol = self.symbol(name)
                symbol.add_rule(rule, action=action, precedence=precedence)
            return symbol

        return dec

    def precedence(self):
        self._current_precedence = _Precedence(
            self._current_precedence.precedence + 1)

    def left(self):
        self._current_precedence = _Precedence(
            self._current_precedence.precedence + 1, _Precedence.ASSOC_LEFT)

    def right(self):
        self._current_precedence = _Precedence(
            self._current_precedence.precedence + 1, _Precedence.ASSOC_RIGHT)

    def nonassoc(self):
        self._current_precedence = _Precedence(
            self._current_precedence.precedence + 1, _Precedence.ASSOC_NONE)

    def symbol(self, name, **kwargs):
        if name is None:
            raise TypeError('symbol name must be not none')

        symbol = self._defined_symbols.get(name)
        if symbol is None:
            symbol = Symbol(name, **kwargs)
            self._defined_symbols[name] = symbol

        return symbol

    def token(self, name, **kwargs):
        if name in self._defined_tokens:
            raise TypeError(f'duplicate token {name}')

        self._defined_tokens.add(name)
        return Terminal(name, precedence=self._current_precedence, **kwargs)

    def generate(self, start_symbol, eof_symbol):
        def reduce(v, _):
            return v

        start_wrapper = Symbol(name='__START__')
        start_wrapper.add_rule([start_symbol, eof_symbol], action=reduce)

        root_state = self._generate_state_tree(start_wrapper)

        self._merge_state_tree(root_state)

        return root_state, start_wrapper

    def _generate_state_tree(self, symbol):
        state = self._generated_states.get(symbol)
        if state is None:
            state = State()
            self._generated_states[symbol] = state

        rules = self._pending_rules.get(symbol)
        if rules is None:
            rules = symbol.rules[:]
            self._pending_rules[symbol] = rules

        while len(rules) > 0:
            rule = rules.pop()
            iter = rule.__iter__()
            self._generate_for_symbol(symbol, state, rule, iter)

        return state

    def _generate_for_symbol(self, symbol, state, rule, iter):
        try:
            element = iter.__next__()

            if element not in state:
                branch = State()
                branch._bind_rule = rule
                state.set_branch(element, branch)
            else:
                branch = state.get_branch(element)

                # rebind
                if rule.precedence > branch._bind_rule.precedence:
                    branch._bind_rule = rule

            # try next
            self._generate_for_symbol(symbol, branch, rule, iter)

            if isinstance(element, Symbol):
                self._generate_state_tree(element)
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

            if reduce._associative == _Precedence.ASSOC_LEFT:
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

        for next_element, branch in element_state:
            if next_element in state:
                exist_state = state.get_branch(next_element)

                if exist_state.reduce_rule is not None:
                    # see self._generate_for_symbol: #rebind
                    if self._should_reduce(exist_state._bind_rule.precedence,
                                           branch._bind_rule.precedence):
                        # discard, we don't merge a low precedence state to high precedence state
                        continue

                self._merge_state(exist_state, branch)

            else:
                if state.reduce_rule is not None:
                    if self._should_reduce(state.reduce_rule.precedence,
                                           branch._bind_rule.precedence):
                        # percent extend state chain with low precedence state
                        continue
                state.set_branch(next_element, branch)

    def _merge_state_tree(self, state):
        state._copy_tokens()
        for element, _ in state:
            if isinstance(element, Symbol):
                element_state = self._generated_states[element]
                self._merge_state(state, element_state)

        self._merged_states.add(state)
        for element, branch in state:
            if branch not in self._merged_states:
                self._merge_state_tree(branch)
