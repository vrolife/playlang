from playlang.errors import ConflictReduceReduceError, ConflictShiftReduceError
from playlang.classes import TerminalPrecedence, Symbol, SymbolRule, Terminal, State


class Syntax:
    def __init__(self, name, auto_shift=True):
        self.name = name
        self._auto_shift = auto_shift
        self._defined_symbols = {}
        self._defined_tokens = {}
        self._generated_states = {}
        self._pending_rules = {}
        self._merged_states = set()
        self._current_precedence = TerminalPrecedence(0)

        self.__START__ = self.symbol('__START__', '__START__')

    @property
    def tokens(self):
        return self._defined_tokens

    @property
    def symbols(self):
        return self._defined_symbols

    def increase(self):
        self._current_precedence = TerminalPrecedence(
            self._current_precedence.precedence + 1)

    def left(self):
        self._current_precedence = TerminalPrecedence(
            self._current_precedence.precedence + 1, TerminalPrecedence.ASSOC_LEFT)

    def right(self):
        self._current_precedence = TerminalPrecedence(
            self._current_precedence.precedence + 1, TerminalPrecedence.ASSOC_RIGHT)

    def nonassoc(self):
        self._current_precedence = TerminalPrecedence(
            self._current_precedence.precedence + 1, TerminalPrecedence.ASSOC_NONE)

    def symbol(self, name, fullname=None):
        if name is None:
            raise TypeError('symbol name must be not none')

        if fullname is None:
            fullname = f'{self.name}_{name}'.upper()

        symbol = self._defined_symbols.get(fullname)
        if symbol is None:
            symbol = Symbol(name, fullname)
            self._defined_symbols[fullname] = symbol

        return symbol

    def terminal(self, name, fullname=None):
        if name is None:
            raise TypeError('token name must be not none')

        if fullname is None:
            fullname = f'{self.name}_{name}'.upper()

        token = self._defined_tokens.get(fullname)
        if token is None:
            token = Terminal(
                name, fullname, precedence=self._current_precedence)
            self._defined_tokens[fullname] = token

        return token

    def generate(self, start_symbol, eof_token):
        def reduce_start_symbol(ctx, v, _):
            return v

        self.__START__.rules.append(SymbolRule(
            self.__START__, [start_symbol, eof_token], reduce_start_symbol))

        root_state = self._generate_state_tree(self.__START__)

        self._merge_state_tree(root_state)

        return root_state, self.__START__

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
            rule_iter = enumerate(rule.__iter__())
            self._generate_for_symbol(symbol, state, rule, rule_iter)

        return state

    def _generate_for_symbol(self, symbol, state, rule, rule_iter):
        try:
            index, component = rule_iter.__next__()

            if component not in state:
                branch = State()
                branch.bind_rule = rule
                branch.bind_index = index
                state.set_branch(component, branch)
            else:
                branch = state.get_branch(component)

                # rebind
                if rule.precedence > branch.bind_rule.precedence:
                    branch.bind_rule = rule

            # try next
            self._generate_for_symbol(symbol, branch, rule, rule_iter)

            if isinstance(component, Symbol):
                self._generate_state_tree(component)
        except StopIteration:
            state.reduce_rule = rule

    def _should_reduce(self, reduce, shift):
        if reduce.precedence > shift.precedence:
            return True
        if reduce.precedence < shift.precedence:
            return False
        else:  # ==
            if reduce.associative != shift.associative:
                raise ConflictShiftReduceError('shift/reduce conflict. reduce: %s. shift: %s' % (reduce, shift))

            if reduce.associative == TerminalPrecedence.ASSOC_LEFT:
                return True

            if not self._auto_shift:
                raise ConflictShiftReduceError('shift/reduce conflict. reduce: %s. shift: %s' % (reduce, shift))

            # shift default
            return False

    def _should_override(self, dest_rule, source_rule):
        if dest_rule.precedence > source_rule.precedence:
            return True
        if dest_rule.precedence < source_rule.precedence:
            return False
        else:  # ==
            raise ConflictReduceReduceError('reduce/reduce conflict. %s and %s' % (dest_rule, source_rule))

    def _merge_state(self, dest_state, source_state):
        if dest_state is source_state:
            return

        if source_state.reduce_rule is not None:
            if dest_state.reduce_rule is None:
                # precedence ?
                dest_state.reduce_rule = source_state.reduce_rule
            elif dest_state.reduce_rule is not source_state.reduce_rule:
                if self._should_override(dest_state.reduce_rule,
                                         source_state.reduce_rule):
                    dest_state.reduce_rule = source_state.reduce_rule

        for component, branch in source_state:
            if component in dest_state:
                exist_state = dest_state.get_branch(component)

                if exist_state.reduce_rule is not None:
                    # see self._generate_for_symbol: #rebind
                    if self._should_reduce(exist_state.bind_rule.precedence,
                                           branch.bind_rule.precedence):
                        # discard, we don't merge a low precedence state to high precedence state
                        continue

                self._merge_state(exist_state, branch)

            else:
                if dest_state.reduce_rule is not None:
                    if self._should_reduce(dest_state.reduce_rule.precedence,
                                           branch.bind_rule.precedence):
                        # percent extend state chain with low precedence state
                        continue
                dest_state.set_branch(component, branch)

    def _merge_state_tree(self, state):
        state._copy_tokens()
        for component, _ in state:
            if isinstance(component, Symbol):
                self._merge_state(state, self._generated_states[component])

        self._merged_states.add(state)
        for component, branch in state:
            if branch not in self._merged_states:
                self._merge_state_tree(branch)
