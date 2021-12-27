import io
import logging
import unittest
from playlang import *
from playlang import javascript
from playlang.objects import *
from playlang.syntex import Syntax
from playlang.javascript import JavaScript

logging.basicConfig(level='DEBUG')


class MismatchError(Exception):
    @staticmethod
    def throw(*args):
        raise MismatchError(*args)


class ParserCalc(metaclass=Parser):
    NUMBER = Token(r'\d+',
                   action=int,
                   show_name='Number',
                   javascript='return parseInt(ctx.text)')
    NAME = Token(r'[a-zA-Z_]+\w*',
                 action=str,
                 show_name='Name',
                 javascript='return ctx.text')
    NEWLINE = Token(r'\n+',
                    discard=True,
                    action=lambda ctx: ctx.lines(len(ctx.text)))
    WHITE = Token(r'\s+', discard=True)
    MISMATCH = Token(r'.', discard=True)

    QUOTE = Token(r'"',
                  discard=True,
                  action=lambda ctx: ctx.enter('string', io.StringIO()),
                  javascript='ctx.enter("string", [])')
    STRING_QUOTE = Token(r'"',
                         discard=True,
                         action=lambda ctx: ctx.leave(),
                         javascript='ctx.leave()')
    STRING_ESCAPE = Token(r'\\"',
                          discard=True,
                          context='string',
                          action=lambda ctx: ctx.value.write(ctx.text[1]),
                          javascript='ctx.value.push(ctx.text[1])')
    SRTING_CHAR = Token(r'.',
                        discard=True,
                        context='string',
                        action=lambda ctx: ctx.value.write(ctx.text),
                        javascript='ctx.value.push(ctx.text)')
    STRING = Token('string',
                   capture=True,
                   action=lambda ctx: ctx.value.getvalue(),
                   javascript='return ctx.value.join("")')

    _ = Precedence.Right
    EQUALS = Token(r'=')

    _ = Precedence.Left
    PLUS = Token(r'\+')
    MINUS = Token(r'-')

    _ = Precedence.Left
    TIMES = Token(r'\*')
    DIVIDE = Token(r'\/')

    _ = Precedence.Increase
    LPAR = Token(r'\(')
    RPAR = Token(r'\)')
    UMINUS = Token(r'-')

    _ = Scan(NUMBER, NAME, EQUALS, PLUS, MINUS, TIMES,
             DIVIDE, LPAR, RPAR, QUOTE, NEWLINE, WHITE, MISMATCH)
    _ = Scan(STRING_QUOTE, STRING_ESCAPE, SRTING_CHAR, MISMATCH, name="string")

    @JavaScript('throw Error("missmatch")')
    @Action
    def MISMATCH(context):
        raise MismatchError(f'missmatch: {context.text}')

    @JavaScript('return $1')
    @Rule(NUMBER)
    def EXPR(self, value):
        self._steps.append(value)
        return value

    @JavaScript(function='expr_name')
    @Rule(NAME)
    @staticmethod
    def EXPR(self, name):
        self._steps.append(name)
        return self._names[name]

    @JavaScript('return $1')
    @Rule(STRING)
    def EXPR(self, s):
        self._steps.append(s)
        return s

    @JavaScript(function='expr_minus_expr')
    @Rule(MINUS, EXPR, precedence=UMINUS)
    def EXPR(self, l, expr):
        self._steps.append(f'-{expr}')
        return -expr

    @JavaScript('return $2')
    @Rule(LPAR, EXPR, RPAR)
    def EXPR(self, l, expr, r):
        self._steps.append(f'({expr})')
        return expr

    @ShowName('Expression')
    @JavaScript(function='expr_expr_opr_expr')
    @Rule(EXPR, PLUS, EXPR)
    @Rule(EXPR, MINUS, EXPR)
    @Rule(EXPR, TIMES, EXPR)
    @Rule(EXPR, DIVIDE, EXPR)
    def EXPR(self, l_expr, opr, r_expr):
        code = f'{l_expr}{opr}{r_expr}'
        self._steps.append(code)
        return eval(code)

    @JavaScript(function='expr_name_eq_expr')
    @Rule(NAME, EQUALS, EXPR)
    def EXPR(self, name, _, expr):
        self._steps.append(f'{name}={expr}')
        self._names[name] = expr
        return expr

    _ = Start(EXPR)

    scanner = StaticScanner(default_action=lambda ctx: ctx.step(len(ctx.text)))

    def __init__(self):
        self._names = {}
        self._steps = []

    def parse_string(self, string):
        return ParserCalc.parse(ParserCalc.scanner(string), context=self)


class TestCalc(unittest.TestCase):
    def test_right_associativity(self):
        compiler = ParserCalc()
        result = compiler.parse_string('a=b=3')
        self.assertEqual(result, 3)
        self.assertListEqual(compiler._steps, [3, 'b=3', 'a=3'])

    def test_left_associativity(self):
        compiler = ParserCalc()
        result = compiler.parse_string('2+3+4')
        self.assertEqual(result, 9)
        self.assertListEqual(compiler._steps, [2, 3, '2+3', 4, '5+4'])

    def test_reference(self):
        compiler = ParserCalc()
        compiler._names['a'] = 3
        result = compiler.parse_string('a*4')
        self.assertEqual(result, 12)
        self.assertListEqual(compiler._steps, ['a', 4, '3*4'])

    def testprecedence(self):
        compiler = ParserCalc()
        result = compiler.parse_string('2+3*4')
        self.assertEqual(result, 14)
        self.assertListEqual(compiler._steps, [2, 3, 4, '3*4', '2+12'])

    def test_group(self):
        compiler = ParserCalc()
        result = compiler.parse_string('2+(3+4)')
        self.assertEqual(result, 9)
        self.assertListEqual(compiler._steps, [2, 3, 4, '3+4', '(7)', '2+7'])

    def test_minus(self):
        compiler = ParserCalc()
        result = compiler.parse_string('-2*3')
        self.assertEqual(result, -6)
        self.assertListEqual(compiler._steps, [2, '-2', 3, '-2*3'])

    def test_assign(self):
        compiler = ParserCalc()
        result = compiler.parse_string('x=1+2*-3')
        self.assertEqual(result, -5)
        self.assertEqual(compiler._names['x'], -5)
        self.assertListEqual(
            compiler._steps, [1, 2, 3, '-3', '2*-3', '1+-6', 'x=-5'])

    def test_ignorabletoken(self):
        compiler = ParserCalc()
        result = compiler.parse_string('2+3 *4+5')
        self.assertEqual(result, 19)
        self.assertListEqual(
            compiler._steps, [2, 3, 4, '3*4', '2+12', 5, '14+5'])

    def test_string(self):
        compiler = ParserCalc()
        result = compiler.parse_string('x="123"')
        self.assertEqual(result, "123")
        self.assertListEqual(
            compiler._steps, ['123', 'x=123'])

    def test_calc2(self):
        compiler = ParserCalc()

        scanner = Scanner(
            ParserCalc, default_action=lambda ctx: ctx.step())

        tokens = []

        for tv in scanner("a=1+1"):
            tokens.append(tv.token)

        self.assertListEqual(tokens, [
            compiler.NAME, compiler.EQUALS, compiler.NUMBER, compiler.PLUS, compiler.NUMBER])


class TestConflict(unittest.TestCase):
    def test_reduce_reduce(self):
        syntax = Syntax()
        EOF = syntax.token('__EOF__')

        A = syntax.token('A')
        B = syntax.token('B')

        LIST = syntax.symbol('LIST')
        LIST.add_rule(A, B)

        EXPR = syntax.symbol('EXPR')
        EXPR.add_rule(LIST)
        EXPR.add_rule(A, B)

        self.assertRaises(ConflictReduceReduceError,
                          lambda: syntax.generate(EXPR, EOF))

    def test_shift_reduce(self):
        syntax = Syntax(auto_shift=False)
        EOF = syntax.token('__EOF__')

        A = syntax.token('A')
        B = syntax.token('B')

        LIST = syntax.symbol('LIST')
        LIST.add_rule(A, B)

        EXPR = syntax.symbol('EXPR')
        EXPR.add_rule(LIST)
        EXPR.add_rule(A)

        self.assertRaises(ConflictShiftReduceError,
                          lambda: syntax.generate(EXPR, EOF))


class ParserPair(metaclass=Parser):
    EOF = Token(None, eof=True, show_name='End-Of-File')
    NAME = Token(r'[a-zA-Z]+')
    DIGITS = Token(r'\d+')
    NEWLINE = Token(r'\n+',
                    action=lambda ctx: ctx.lines(len(ctx.text)))
    WHITE = Token(r'\s+', discard=True)
    MISMATCH = Token(r'.', action=lambda ctx: MismatchError.throw(ctx.text))

    _ = Scan(NAME, DIGITS, NEWLINE, WHITE, MISMATCH)

    @ShowName('Number')
    @Rule(DIGITS)
    def NUMBER(self, val):
        return val

    @Rule(NUMBER, NUMBER)
    def PAIR(self, n1, n2):
        return (n1, n2)

    @Rule(NUMBER, EOF)
    def PAIR(self, n1, _):
        return (n1, None)

    @Rule()
    def LIST(self):
        return []

    @Rule(PAIR)
    def LIST(self, pair):
        return [pair]

    @Rule(LIST, PAIR)
    def LIST(self, expr, pair):
        expr.append(pair)
        return expr

    _ = Start(LIST)

    def __init__(self):
        self._scanner = Scanner(
            ParserPair, default_action=lambda ctx: ctx.step(len(ctx.text)))

    def parse_string(self, string):
        return ParserPair.parse(self._scanner(string), context=self)


class TestPair(unittest.TestCase):
    def test_simple(self):
        compiler = ParserPair()
        lst = compiler.parse_string('2 3')
        self.assertListEqual(lst, [('2', '3')])

    def test_half(self):
        compiler = ParserPair()
        lst = compiler.parse_string('2 3 4')
        self.assertListEqual(lst, [('2', '3'), ('4', None)])

    def test_error(self):
        compiler = ParserPair()
        self.assertRaises(SyntaxError, lambda: compiler.parse_string('2 3 4 x'))


class ParserList(metaclass=Parser):
    DIGITS = Token(r'\d')
    NEWLINE = Token(r'\n+',
                    discard=True,
                    action=lambda ctx: ctx.lines(len(ctx.text)))
    WHITE = Token(r'\s+', discard=True)
    MISMATCH = Token(r'.', action=lambda ctx: MismatchError.throw(ctx.text))

    _ = Scan(DIGITS, NEWLINE, WHITE, MISMATCH)

    @Rule(DIGITS)
    def NUMBER(self, val):
        return val

    @Rule()
    def EXPR(self):
        return []

    @Rule(NUMBER)
    def EXPR(self, val):
        return [val]

    @Rule(EXPR, NUMBER)
    def EXPR(self, expr, num):
        expr.append(num)
        return expr

    _ = Start(EXPR)

    def __init__(self):
        self._scanner = Scanner(
            ParserList, default_action=lambda ctx: ctx.step(len(ctx.text)))

    def parse_string(self, string):
        return ParserList.parse(self._scanner(string), context=self)


class TestList(unittest.TestCase):
    def test_simple(self):
        compiler = ParserList()
        lst = compiler.parse_string('234')
        self.assertListEqual(lst, ['2', '3', '4'])

    def test_new_line(self):
        compiler = ParserList()
        lst = compiler.parse_string('2\n34')
        self.assertListEqual(lst, ['2', '3', '4'])

    def test_empty_list(self):
        compiler = ParserList()
        lst = compiler.parse_string('')
        self.assertListEqual(lst, [])


class TestScanner(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.si = ScanInfo()
        self.si.contexts = {
            '__default__': ['DIGITS', 'QUOTE', 'NEWLINE', 'WHITE', 'MISMATCH'],
            'string': ['STRING_QUOTE', 'STRING_ESCAPE', 'STRING_NEWLINE', 'STRING_CHAR', 'MISMATCH']
        }
        self.si.tokens = {
            'DIGITS': {
                'pattern': r'\d',
                'action': str
            },
            'QUOTE': {
                'pattern': r'"',
                'action': lambda ctx: ctx.enter('string', io.StringIO()),
                'discard': True
            },
            'STRING_QUOTE': {
                'pattern': r'"',
                'action': lambda ctx: ctx.leave(),
                'discard': True
            },
            'STRING_ESCAPE': {
                'pattern': r'\\"',
                'action': lambda ctx: ctx.value.write(ctx.text[1]),
                'discard': True
            },
            'STRING_NEWLINE': {
                'pattern': r'\n',
                'action': lambda ctx: MismatchError.throw('string missing terminator'),
                'discard': True
            },
            'STRING_CHAR': {
                'pattern': r'.',
                'action': lambda ctx: ctx.value.write(ctx.text),
                'discard': True
            },
            'STRING': {
                'capture': 'string',
                'action': lambda ctx: ctx.value.getvalue(),
            },
            'NEWLINE': {
                'pattern': r'\n+',
                'action': lambda ctx: ctx.lines(len(ctx.text)).text,
            },
            'WHITE': {
                'pattern': r'\s+',
                'action': None,
                'discard': True
            },
            'MISMATCH': {
                'pattern': r'.',
                'action': lambda ctx: MismatchError.throw(ctx.text),
                'discard': True
            }
        }

        self.scanner = Scanner(
            self.si, lambda ctx: ctx.step())

        self.scan = lambda s: list(
            map(lambda v: v.value, self.scanner(s)))

    def test_simple(self):
        self.assertListEqual(self.scan('123'), ['1', '2', '3'])

    def test_discard(self):
        self.assertListEqual(self.scan('12 3'), ['1', '2', '3'])

    def test_newline(self):
        self.assertListEqual(self.scan('1\n2'), ['1', '\n', '2'])

    def test_string_missing_terminator(self):
        self.assertRaises(MismatchError, lambda: self.scan('1"\n"2'))

    def test_mismatch(self):
        self.assertRaises(MismatchError, lambda *args: self.scan('x'))
        self.assertRaises(MismatchError, lambda *args: self.scan('x1'))
        self.assertRaises(MismatchError, lambda *args: self.scan('1x'))

    def test_context(self):
        self.assertListEqual(self.scan('1"2\\"2"3'), ['1', '2"2', '3'])

# UPG
# RUN python3 -m unittest tests.py
