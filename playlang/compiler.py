from playlang.objects import *
from playlang.parser import parse, Syntax
from playlang.tokenizer import Tokenizer


class CompilerAnnotations(dict):
    def __init__(self, dic, syntax, patterns):
        super().__init__()
        self._dic = dic
        self._syntax = syntax
        self._patterns = patterns

    def __setitem__(self, key, value):
        if isinstance(value, (MetaToken, TokenType)):
            pattern = self._dic.get(key)
            token = self._syntax.token(key)

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
        if 'START' not in dic:
            raise TypeError('missing "START" symbol')

        dic['__states__'] = dic['__syntax__'].generate(dic['START'])

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
