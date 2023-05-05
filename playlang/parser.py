# Copyright (C) 2023 pom@vro.life
# SPDX-License-Identifier: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only
from typing import List, Dict
from playlang.classes import TokenValue, Symbol, \
    Terminal, SymbolInfo, Precedence, SymbolRule, \
    StaticField, Scanner, Start, State, TokenInfo
from playlang.syntex import Syntax


class TokenReader:
    def __init__(self, scanner, start):
        self._scanner = scanner
        self._start = start
        self._stack = []
        self._next_token = None

    def __repr__(self):
        return f'{self._stack}'

    def _read(self):
        return self._scanner.__next__()

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
        branch = current_state.get_branch(lookahead.token)

        if branch is not None:
            # shift
            if not isinstance(lookahead.token, Symbol):
                token_reader.read()
            state_stack.push(branch)
            lookahead = token_reader.peek()
        else:
            if current_state.reduce_rule is not None:
                # reduce
                rule = current_state.reduce_rule
                if rule.action is not None:
                    args = [context]
                    for tv in token_reader.consume(len(rule)):
                        args.append(tv.value)
                    value = rule.action(*args)
                else:
                    token_reader.consume(len(rule))
                    value = None
                token_reader.commit(TokenValue(rule.symbol, value))
                state_stack.pop(len(rule))
                lookahead = token_reader.top()
            else:
                # pylint: disable=line-too-long
                if isinstance(lookahead.token, Terminal) and lookahead.token.ignorable:
                    token_reader.discard()
                    lookahead = token_reader.peek()
                    continue

                count = len(current_state.immediate_tokens)
                location = ""
                message = ""

                if lookahead.location is not None:
                    loc = lookahead.location
                    location = f'{loc.filename}{loc.line}:{loc.column} => '

                if count == 1:
                    message = f', expecting {current_state.immediate_tokens[0].show_name}'
                elif count == 2:
                    message = f', expecting {current_state.immediate_tokens[0].show_name} or {current_state.immediate_tokens[1].show_name}'
                else:
                    message = f', expecting one of [{" ".join([t.show_name for t in current_state.immediate_tokens])}]'

                raise SyntaxError(
                    f'{location}unexpected token {lookahead.token.show_name}({lookahead.value}){message}')


class ParserDict(dict):
    def __init__(self, name):
        super().__init__()
        self['__syntax__'] = Syntax(name)
        self['__scanners__'] = {}

    def __setitem__(self, key, value): # pylint: disable=too-many-branches
        if isinstance(value, SymbolInfo):
            syntax = self['__syntax__']  # type: Syntax

            def add_all(symbol: Symbol):
                for rule in symbol.rules:
                    for c in rule:
                        if isinstance(c, Terminal) and c.fullname not in syntax.tokens:
                            syntax.tokens[c.fullname] = c
                        if isinstance(c, Symbol) and c.fullname not in syntax.symbols:
                            syntax.symbols[c.fullname] = c
                            add_all(c)

            symbol = syntax.symbol(key)  # type: Symbol
            for ruleinfo in value.rules:
                for c in ruleinfo.components:
                    if isinstance(c, Terminal) and c.fullname not in syntax.tokens:
                        syntax.tokens[c.fullname] = c
                    if isinstance(c, Symbol) and c.fullname not in syntax.symbols:
                        syntax.symbols[c.fullname] = c
                        add_all(c)

                rule = SymbolRule(symbol,
                                  ruleinfo.components,
                                  value.action,
                                  ruleinfo.precedence,
                                  value.data)
                symbol.rules.append(rule)

            symbol.data.update(value.data)

            dict.__setitem__(self, key, symbol)
            return

        elif isinstance(value, TokenInfo):
            syntax = self['__syntax__']  # type: Syntax
            token = syntax.terminal(key)
            token.data.update(value)

            dict.__setitem__(self, key, token)
            return

        elif value is Precedence.Right:
            self['__syntax__'].right()

        elif value is Precedence.Left:
            self['__syntax__'].left()

        elif value is Precedence.Increase:
            self['__syntax__'].increase()

        elif isinstance(value, Start):
            symbol = value.symbol
            if not isinstance(symbol, Symbol):
                raise TypeError(
                    f'expected a non-terminal symbol as start symbol. but got {symbol}')
            self['__start_symbol__'] = symbol

        elif isinstance(value, Scanner):
            syntax = self['__syntax__']  # type: Syntax

            self['__scanners__'][value.name] = value
            if value.eof_token is None:
                token = syntax.terminal('__EOF__')
                token.update({"is_eof": True})
                value.eof_token = token
                value.tokens = (*value.tokens, value.eof_token)

        dict.__setitem__(self, key, value)


class Parser(type):
    __syntax__: Syntax
    __state_tree__: State
    __state_list__: List[State]
    __scanners__: Dict[str, Scanner]
    __symbols__: List[str]

    def __new__(cls, name, bases, dic: ParserDict):
        syntax = dic['__syntax__']
        
        scan_info: Dict[str, Scanner] = dic.get('__scanners__')
        if scan_info is None:
            raise TypeError('missing scan information')

        eof_token = scan_info['__default__'].eof_token

        start_symbol = dic.get('__start_symbol__')

        if start_symbol is None:
            raise TypeError('missing start symbol')

        if not isinstance(start_symbol, Symbol):
            raise TypeError(
                f'invalid type of start symbol "{start_symbol}"')

        state_tree, start_wrapper = syntax.generate(start_symbol, eof_token)

        state_list = list(syntax._merged_states)
        state_list.sort(key=lambda s: ''.join([str(t) for t in s.tokens]))

        dic['__state_tree__'] = state_tree
        dic['__state_list__'] = state_list
        dic['__symbols__'] = syntax.symbols.values()
        dic['__start_wrapper__'] = start_wrapper

        clazz = type.__new__(cls, name, bases, dic)

        for k, v in dic.items():
            if isinstance(v, StaticField):
                setattr(clazz, k, v.create(clazz))

        return clazz

    def parse(cls, scanner, context):
        token_reader = TokenReader(scanner, cls.__start_wrapper__)
        state_stack = StateStack(cls.__state_tree__)
        _parse(token_reader, state_stack, context)
        return token_reader.pop().value

    @classmethod
    def __prepare__(cls, name, bases):
        return ParserDict(name)
