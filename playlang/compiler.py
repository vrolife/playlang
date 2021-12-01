from playlang.objects import *
from playlang.parser import parse, Syntax


class CompilerAnnotations(dict):
    def __init__(self, dic, syntax, patterns):
        super().__init__()
        self._dic = dic
        self._syntax = syntax
        self._patterns = patterns

    def __setitem__(self, key, value):
        if isinstance(value, (MetaToken, TokenType)):
            pattern = self._dic.get(key)
            token = self._syntax.token(key, ignorable=value is TokenIgnorable)

            self._dic[key] = token

            token_type = None

            if isinstance(value, TokenType):
                token_type = value.type

            self._patterns.append((token, pattern, token_type))
        elif value is Precedence:
            key = key.upper()
            if key.endswith('RIGHT'):
                self._syntax.right()
            elif key.endswith('LEFT'):
                self._syntax.left()
            elif key.endswith('INCREASE'):
                self._syntax.precedence()
            else:
                raise TypeError('unknown associativity')
            dict.__setitem__(self, key, self._syntax._current_precedence)
        elif value is Start:
            dict.__setitem__(self, '__start__', key)
            dict.__setitem__(self, key, value)
        elif value is TokenList:
            dict.__setitem__(self, '__token_list__', key)
            dict.__setitem__(self, key, value)
        else:
            dict.__setitem__(self, key, value)


class CompilerDict(dict):
    def __init__(self):
        super().__init__()
        self._syntax = Syntax()
        patterns = []
        self['__syntax__'] = self._syntax
        self['__patterns__'] = patterns
        self['__annotations__'] = CompilerAnnotations(self, self._syntax, patterns)

    def __setitem__(self, key, value):
        if isinstance(value, Symbol) and key != 'START':
            symbol = self._syntax.symbol(key)
            symbol.merge(value)
            dict.__setitem__(self, key, symbol)
            return
        dict.__setitem__(self, key, value)


class Compiler(type):
    def __new__(cls, name, bases, dic):
        annotations = dic['__annotations__']
        syntax = dic['__syntax__']
        start_symbol_name = annotations.get('__start__')

        if start_symbol_name is None:
            raise TypeError('missing start symbol')

        if start_symbol_name not in dic:
            raise TypeError(f'start symbol "{start_symbol_name}" annotated but unassigned')

        start_symbol = dic[start_symbol_name]

        if not isinstance(start_symbol, Symbol):
            raise TypeError(f'invalid type of start symbol "{start_symbol_name}"')

        dic['__states__'] = syntax.generate(start_symbol)

        token_list_name = annotations.get('__token_list__')
        if token_list_name is not None:
            token_list = dic[token_list_name]
            if not isinstance(token_list, (tuple, list)):
                raise TypeError('a class member annotated as TokenList must be a tuple or list')

            # sort __patterns__
            order = {}
            for idx, token in enumerate(token_list):
                order[token] = idx

            dic['__patterns__'].sort(key=lambda v: order.get(v[0], 0xffff))

        return type.__new__(cls, name, bases, dic)

    @classmethod
    def __prepare__(metacls, name, bases):
        return CompilerDict()

    @staticmethod
    def build(compiler, build_tokenizer):
        states = getattr(compiler, '__states__')
        patterns = getattr(compiler, '__patterns__')
        tokenizer = build_tokenizer(patterns)

        def compile(string, context=None):
            return parse(states, tokenizer(string), context=context)

        return compile


class TokenList:
    pass


class Start:
    pass
