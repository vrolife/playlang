from typing import Dict, List
from playlang.api import *
from playlang.objects import Symbol, Terminal
from playlang.syntex import Syntax, State


class TokenReader:
    def __init__(self, scanner, start, eof):
        self._scanner = scanner
        self._start = start
        self._eof = eof
        self._stack = []
        self._next_token = None

    def __repr__(self):
        return f'{self._stack}'

    def _read(self):
        try:
            return self._scanner.__next__()
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
        branch = current_state.get_branch(lookahead.token)

        if branch is not None:
            # shift
            if isinstance(lookahead.token, Terminal):
                token_reader.read()
            state_stack.push(branch)
            lookahead = token_reader.peek()
        else:
            if isinstance(lookahead.token, Terminal) and lookahead.token.ignorable:
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


class ParserDict(dict):
    def __init__(self):
        super().__init__()
        self['__syntax__'] = Syntax()
        self['__scan_info__'] = ScanInfo()

    def __setitem__(self, key, value):
        if isinstance(value, SymbolInfo):
            si = value
            symbol = self['__syntax__'].symbol(key)
            for ruleinfo in si.rules:
                symbol.add_rule(ruleinfo.symbols,
                           action=si.action,
                           precedence=ruleinfo.precedence,
                           extra_info=si.extra_info)

            dict.__setitem__(self, key, symbol)
            return

        elif isinstance(value, TokenInfo):
            si = self['__scan_info__']
            token_info = si.tokens.get(key)
            if token_info is not None:
                token_info.update(value)
            else:
                token_info = value
                si.tokens[key] = value

            if not token_info.get('discard', False):
                token = self['__syntax__'].token(
                    key, ignorable=token_info.get('ignorable', False))
                token_info['token'] = token
            else:
                token = key

            dict.__setitem__(self, key, token)
            return

        elif value is Precedence.Right:
            self['__syntax__'].right()

        elif value is Precedence.Left:
            self['__syntax__'].left()

        elif value is Precedence.Increase:
            self['__syntax__'].precedence()

        elif isinstance(value, Start):
            symbol = value.symbol
            if not isinstance(symbol, Symbol):
                raise TypeError(
                    'expected a non-terminal symbol as start symbol. but got %s' % symbol)
            self['__start_symbol__'] = symbol

        elif isinstance(value, Scan):
            self['__scan_info__'].contexts[value.name] = value.tokens

        dict.__setitem__(self, key, value)


class Parser(type):
    __state_tree__: State
    __state_list__: List[State]
    __symbol_list__: List[str]
    __scan_info__: ScanInfo
    __start_symbol__: Symbol
    __eof_symbol__: Symbol
    __syntax__: Symbol

    def __new__(cls, name, bases, dic: ParserDict):
        syntax = dic['__syntax__']

        start_symbol = dic.get('__start_symbol__')

        if start_symbol is None:
            raise TypeError('missing start symbol')

        if not isinstance(start_symbol, Symbol):
            raise TypeError(
                f'invalid type of start symbol "{start_symbol}"')

        state_tree, start_wrapper, eof = syntax.generate(start_symbol)

        dic['__state_tree__'] = state_tree
        dic['__state_list__'] = syntax._merged_states
        dic['__symbol_list__'] = syntax._defined_symbols
        dic['__start_symbol__'] = start_wrapper
        dic['__eof_symbol__'] = eof
        
        clazz = type.__new__(cls, name, bases, dic)

        for k, v in dic.items():
            if isinstance(v, StaticField):
                setattr(clazz, k, v.create(clazz))

        return clazz

    def parse(cls, scanner, context=None):
        token_reader = TokenReader(scanner, cls.__start_symbol__, cls.__eof_symbol__)
        state_stack = StateStack(cls.__state_tree__)
        _parse(token_reader, state_stack, context=context)
        return token_reader.pop().value

    @classmethod
    def __prepare__(metacls, name, bases):
        return ParserDict()
