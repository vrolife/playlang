# pylint: disable=function-redefined
# pylint: disable=invalid-name

import io
import logging
import unittest
from playlang import Parser, Token, Rule, Precedence, Scan, Start,\
    Action, ShowName, Scanner, StaticScanner, \
    ConflictReduceReduceError, ConflictShiftReduceError
from playlang.classes import SymbolRule, Terminal
from playlang.syntex import Syntax
from playlang.javascript import JavaScript

logging.basicConfig(level='DEBUG')


class MismatchError(Exception):
    pass


def throw(e, *args):
    raise e(*args)


class TestConflict(unittest.TestCase):
    def test_reduce_reduce(self):
        syntax = Syntax('TEST')

        A = syntax.terminal('A')
        B = syntax.terminal('B')

        LIST = syntax.symbol('LIST')
        LIST.rules.append(SymbolRule(LIST, (A, B, )))

        EXPR = syntax.symbol('EXPR')
        EXPR.rules.append(SymbolRule(EXPR, (LIST,)))
        EXPR.rules.append(SymbolRule(EXPR, (A, B)))

        self.assertRaises(ConflictReduceReduceError,
                          lambda: syntax.generate(EXPR))

    def test_shift_reduce(self):
        syntax = Syntax('TEST', auto_shift=False)

        A = syntax.terminal('A')
        B = syntax.terminal('B')

        LIST = syntax.symbol('LIST')
        LIST.rules.append(SymbolRule(LIST, (A, B,)))

        EXPR = syntax.symbol('EXPR')
        EXPR.rules.append(SymbolRule(EXPR, (LIST,)))
        EXPR.rules.append(SymbolRule(EXPR, (A,)))

        self.assertRaises(ConflictShiftReduceError,
                          lambda: syntax.generate(EXPR))


class ParserCalc(metaclass=Parser):
    NUMBER = Token(r'[0-9]+',
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
                          action=lambda ctx: ctx.value.write(ctx.text[1]),
                          javascript='ctx.value.push(ctx.text[1])')
    STRING_CHAR = Token(r'.',
                        discard=True,
                        action=lambda ctx: ctx.value.write(ctx.text),
                        javascript='ctx.value.push(ctx.text)')
    STRING = Token(action=lambda ctx: ctx.value.getvalue(),
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
    _ = Scan(STRING_QUOTE, STRING_ESCAPE, STRING_CHAR,
            name="string", capture=STRING)

    @JavaScript('throw Error("missmatch")')
    @Action
    @staticmethod
    def MISMATCH(context):
        raise MismatchError(f'missmatch: {context.text}')

    @JavaScript('return $1')
    @Rule(NUMBER)
    @staticmethod
    def EXPR(context, value):
        context.steps.append(value)
        return value

    @JavaScript(function='expr_name')
    @Rule(NAME)
    @staticmethod
    def EXPR(context, name):
        context.steps.append(name)
        return context.names[name]

    @JavaScript('return $1')
    @Rule(STRING)
    @staticmethod
    def EXPR(context, s):
        context.steps.append(s)
        return s

    @JavaScript(function='expr_minus_expr')
    @Rule(MINUS, EXPR, precedence=UMINUS)
    @staticmethod
    def EXPR(context, l, expr):
        context.steps.append(f'-{expr}')
        return -expr

    @JavaScript('return $2')
    @Rule(LPAR, EXPR, RPAR)
    @staticmethod
    def EXPR(context, l, expr, r):
        context.steps.append(f'({expr})')
        return expr

    @ShowName('Expression')
    @JavaScript(function='expr_expr_opr_expr')
    @Rule(EXPR, PLUS, EXPR)
    @Rule(EXPR, MINUS, EXPR)
    @Rule(EXPR, TIMES, EXPR)
    @Rule(EXPR, DIVIDE, EXPR)
    @staticmethod
    def EXPR(context, l_expr, opr, r_expr):
        code = f'{l_expr}{opr}{r_expr}'
        context.steps.append(code)
        return eval(code)  # pylint: disable=eval-used

    @JavaScript(function='expr_name_eq_expr')
    @Rule(NAME, EQUALS, EXPR)
    @staticmethod
    def EXPR(context, name, _, expr):
        context.steps.append(f'{name}={expr}')
        context.names[name] = expr
        return expr

    _ = Start(EXPR)

    scanner = StaticScanner(default_action=lambda ctx: ctx.step(len(ctx.text)))

    def __init__(self):
        self.names = {}
        self.steps = []

    def parse_string(self, string):
        return ParserCalc.parse(ParserCalc.scanner(string), context=self)


class TestCalc(unittest.TestCase):
    def test_right_associativity(self):
        compiler = ParserCalc()
        result = compiler.parse_string('a=b=3')
        self.assertEqual(result, 3)
        self.assertListEqual(compiler.steps, [3, 'b=3', 'a=3'])

    def test_left_associativity(self):
        compiler = ParserCalc()
        result = compiler.parse_string('2+3+4')
        self.assertEqual(result, 9)
        self.assertListEqual(compiler.steps, [2, 3, '2+3', 4, '5+4'])

    def test_reference(self):
        compiler = ParserCalc()
        compiler.names['a'] = 3
        result = compiler.parse_string('a*4')
        self.assertEqual(result, 12)
        self.assertListEqual(compiler.steps, ['a', 4, '3*4'])

    def testprecedence(self):
        compiler = ParserCalc()
        result = compiler.parse_string('2+3*4')
        self.assertEqual(result, 14)
        self.assertListEqual(compiler.steps, [2, 3, 4, '3*4', '2+12'])

    def test_group(self):
        compiler = ParserCalc()
        result = compiler.parse_string('2+(3+4)')
        self.assertEqual(result, 9)
        self.assertListEqual(compiler.steps, [2, 3, 4, '3+4', '(7)', '2+7'])

    def test_minus(self):
        compiler = ParserCalc()
        result = compiler.parse_string('-2*3')
        self.assertEqual(result, -6)
        self.assertListEqual(compiler.steps, [2, '-2', 3, '-2*3'])

    def test_assign(self):
        compiler = ParserCalc()
        result = compiler.parse_string('x=1+2*-3')
        self.assertEqual(result, -5)
        self.assertEqual(compiler.names['x'], -5)
        self.assertListEqual(
            compiler.steps, [1, 2, 3, '-3', '2*-3', '1+-6', 'x=-5'])

    def test_ignorabletoken(self):
        compiler = ParserCalc()
        result = compiler.parse_string('2+3 *4+5')
        self.assertEqual(result, 19)
        self.assertListEqual(
            compiler.steps, [2, 3, 4, '3*4', '2+12', 5, '14+5'])

    def test_string(self):
        compiler = ParserCalc()
        result = compiler.parse_string('x="123"')
        self.assertEqual(result, "123")
        self.assertListEqual(
            compiler.steps, ['123', 'x=123'])

    def test_calc2(self):
        compiler = ParserCalc()

        scanner = Scanner(
            ParserCalc, default_action=lambda ctx: ctx.step())

        tokens = []

        for tv in scanner("a=1+1"):
            tokens.append(tv.token)

        self.assertListEqual(tokens, [
            compiler.NAME, compiler.EQUALS, compiler.NUMBER, compiler.PLUS, compiler.NUMBER])


class TemplateParser(metaclass=Parser):
    EOF = Token(eof=True)

    BEGIN = Token(r'\${',
                  discard=True,
                  action=lambda ctx: ctx.enter('expression'),
                  javascript='ctx.enter("expression")')

    TEXT = Token(r'[^\\$]+',
                 action=lambda ctx: ctx.text,
                 javascript='return ctx.text')

    MISMATCH = Token(r'.',
                     discard=True,
                     action=lambda ctx: throw(
                         MismatchError, ctx.location, ctx.text),
                     javascript='throw Error(`missmatch: ${ctx.text}`)')

    NAME = Token(r'[a-zA-Z_]+\w*',
                 action=lambda ctx: ctx.text,
                 javascript='return ctx.text')

    INTEGER = Token(r'[0-9]+\b',
                    action=int,
                    javascript='return parseInt(ctx.text)')

    DOT = Token(r'\.')
    LB = Token(r'\[')
    RB = Token(r'\]')
    END = Token(r'}',
                discard=True,
                action=lambda ctx: ctx.leave(),
                javascript='ctx.leave()')

    _ = Scan(BEGIN, TEXT, MISMATCH)
    expression = Scan(END, NAME, DOT, LB, RB, INTEGER,
                      MISMATCH, name='expression')

    @JavaScript('return ctx => ctx.get_prev_instance()[$2]')
    @Rule(DOT, NAME)
    @staticmethod
    def REF(ctx, _, name):
        return lambda ctx: ctx.get_prev_instance().get(name)

    @JavaScript('return ctx => ctx.get_instance($2)')
    @Rule(NAME)
    @staticmethod
    def REF(ctx, name):
        return lambda ctx: ctx.get_instance(name)

    @JavaScript('return ctx => $1(ctx)[$3]')
    @Rule(REF, DOT, NAME)
    @staticmethod
    def REF(ctx, ref, _, name):
        return lambda ctx: ref(ctx).get(name)

    @JavaScript('return ctx => $1(ctx)[$3]')
    @Rule(REF, LB, INTEGER, RB)
    @staticmethod
    def REF(ctx, ref, lb, idx, rb):
        return lambda ctx: ref(ctx)[idx]

    @JavaScript('return $1')
    @Rule(REF)
    @staticmethod
    def COMPONENT(ctx, ref):
        return ref

    @JavaScript('return ctx => $1')
    @Rule(TEXT)
    @staticmethod
    def COMPONENT(ctx, text):
        return lambda ctx: text

    @JavaScript('return [$1]')
    @Rule(COMPONENT)
    @staticmethod
    def ASSEMBLY(ctx, component):
        return [component]

    @JavaScript('$1.push($2); return $1')
    @Rule(ASSEMBLY, COMPONENT)
    @staticmethod
    def ASSEMBLY(ctx, lst, text):
        lst.append(text)
        return lst

    _ = Start(ASSEMBLY)

    scan = StaticScanner(default_action=lambda ctx: ctx.step())

    def __init__(self):
        pass

    def parse_string(self, content):
        return TemplateParser.parse(TemplateParser.scan(content), context=self)

    def to_string(self, content, context):
        return ''.join([str(x(context)) for x in self.parse_string(content)])


class TestContext:
    def __init__(self, instances):
        self._instances = instances

    def get_prev_instance(self):
        return self._instances.get('prev')

    def get_instance(self, name):
        return self._instances.get(name)


class TestTemplateParser(unittest.TestCase):

    def test_scanner_ref_only(self):
        c = TemplateParser

        self.assertListEqual([tv.token for tv in c.scan('${.hello}')], [
            c.DOT,
            c.NAME,
        ])

    def test_scanner_text_and_ref(self):
        c = TemplateParser
        self.assertListEqual([tv.token for tv in c.scan('A${.hello}B')], [
            c.TEXT,
            c.DOT,
            c.NAME,
            c.TEXT
        ])

    def test_ref(self):
        parser = TemplateParser()
        context = TestContext({
            'prev': {
                'hello': 'world!',
                'node': {
                    'array': [
                        'a',
                        {
                            'name': 'ya'
                        }
                    ]
                }
            },
            'foo': 'bar'
        })

        self.assertEqual(parser.to_string('${foo}', context), 'bar')
        self.assertEqual(parser.to_string('${.hello}', context), 'world!')
        self.assertEqual(parser.to_string(
            '${.node.array[1].name}', context), 'ya')
        self.assertEqual(parser.to_string('A${.hello}B', context), 'Aworld!B')


class ParserListWithTemplate(metaclass=Parser):
    TMP = TemplateParser
    DIGITS = Token(r'\d',
                   javascript='return parseInt(ctx.text)')
    NEWLINE = Token(r'\n+',
                    discard=True,
                    action=lambda ctx: ctx.lines(len(ctx.text)),
                    javascript='ctx.lines(ctx.text.length)')
    WHITE = Token(r'\s+', discard=True)
    MISMATCH = Token(r'.',
                     action=lambda ctx: throw(MismatchError, ctx.text),
                     javascript='throw Error(`missmatch: ${ctx.text}`)')

    _ = Scan(TMP.BEGIN, DIGITS, NEWLINE, WHITE, MISMATCH)
    expression = TMP.expression

    @JavaScript('return $1')
    @Rule(DIGITS)
    @Rule(TMP.REF)
    @staticmethod
    def ITEM(context, val):
        return val

    @JavaScript('return []')
    @Rule()
    @staticmethod
    def EXPR(context):
        return []

    @JavaScript('return [$1]')
    @Rule(ITEM)
    @staticmethod
    def EXPR(context, val):
        return [val]

    @JavaScript('$1.push($2); return $1')
    @Rule(EXPR, ITEM)
    @staticmethod
    def EXPR(context, expr, num):
        expr.append(num)
        return expr

    _ = Start(EXPR)

    def __init__(self):
        self._scanner = Scanner(
            ParserListWithTemplate, default_action=lambda ctx: ctx.step(len(ctx.text)))

    def parse_string(self, string):
        return ParserListWithTemplate.parse(self._scanner(string), context=self)


class TestListWithTemplate(unittest.TestCase):
    def test_simple(self):
        compiler = ParserListWithTemplate()
        ctx = TestContext({
            'prev': {
                'hello': 'world!'
            }
        })
        lst = compiler.parse_string('2${.hello}4')

        self.assertListEqual(
            [i(ctx) if callable(i) else i for i in lst], ['2', 'world!', '4'])


class ParserPair(metaclass=Parser):
    EOF = Token(None, eof=True, show_name='End-Of-File')
    NAME = Token(r'[a-zA-Z]+')
    DIGITS = Token(r'\d+')
    NEWLINE = Token(r'\n+',
                    action=lambda ctx: ctx.lines(len(ctx.text)))
    WHITE = Token(r'\s+', discard=True)
    MISMATCH = Token(r'.', action=lambda ctx: throw(MismatchError, ctx.text))

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
        self.assertRaises(
            SyntaxError, lambda: compiler.parse_string('2 3 4 x'))


class ParserList(metaclass=Parser):
    DIGITS = Token(r'\d')
    NEWLINE = Token(r'\n+',
                    discard=True,
                    action=lambda ctx: ctx.lines(len(ctx.text)))
    WHITE = Token(r'\s+', discard=True)
    MISMATCH = Token(r'.', action=lambda ctx: throw(MismatchError, ctx.text))

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

# dragon book. 4.18
class ParserList2(metaclass=Parser):
    DIGITS = Token(r'\d')
    NEWLINE = Token(r'\n+',
                    discard=True,
                    action=lambda ctx: ctx.lines(len(ctx.text)))
    WHITE = Token(r'\s+', discard=True)
    MISMATCH = Token(r'.', action=lambda ctx: throw(MismatchError, ctx.text))

    _ = Precedence.Increase
    A_FIRST = Token()

    _ = Scan(DIGITS, NEWLINE, WHITE, MISMATCH)

    @Rule(DIGITS)
    def NUMBER(self, val):
        return val

    @Rule(NUMBER)
    def S(self, val):
        return [val]

    @Rule()
    def A(self):
        return []

    @Rule(A, NUMBER, precedence=A_FIRST)
    def A(self, expr, val):
        expr.append(val)
        return expr

    @Rule(S, NUMBER)
    def A(self, expr, val):
        expr.append(val)
        return expr

    @Rule(A, NUMBER)
    def S(self, expr, num):
        expr.append(num)
        return expr

    _ = Start(S)

    def __init__(self):
        self._scanner = Scanner(
            ParserList2, default_action=lambda ctx: ctx.step(len(ctx.text)))

    def parse_string(self, string):
        return ParserList2.parse(self._scanner(string), context=self)

class TestList2(unittest.TestCase):
    def test_simple(self):
        compiler = ParserList2()
        lst = compiler.parse_string('234')
        self.assertListEqual(lst, ['2', '3', '4'])

class TestScanner(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        scan_info = {
            '__default__': ['DIGITS', 'QUOTE', 'NEWLINE', 'WHITE', 'MISMATCH'],
            'string': ['STRING_QUOTE', 'STRING_ESCAPE', 'STRING_NEWLINE',
                       'STRING_CHAR', 'MISMATCH', 'STRING']
        }

        tokens = {
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
                'action': lambda ctx: throw(MismatchError, 'string missing terminator'),
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
                'action': lambda ctx: throw(MismatchError, ctx.text),
                'discard': True
            }
        }

        si = {}

        for ctx, toks in scan_info.items():
            lst = []
            for name in toks:
                info = tokens[name]
                token = Terminal(name, name, precedence=None)
                token.data.update(info)
                lst.append(token)
            si[ctx] = lst

        self.scanner = Scanner(si, lambda ctx: ctx.step())

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
