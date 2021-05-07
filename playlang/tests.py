import unittest
import playlang as pl


class CompilerCalc:
    _syntax = pl.Syntax()

    NUMBER = _syntax.token('NUMBER')
    NAME = _syntax.token('NAME')
    NEWLINE = _syntax.token('NEWLINE')
    _syntax.right()
    EQUALS = _syntax.token('EQUALS')
    _syntax.left()
    PLUS = _syntax.token('PLUS')
    MINUS = _syntax.token('MINUS')
    _syntax.left()
    TIMES = _syntax.token('TIMES')
    DIVIDE = _syntax.token('DIVIDE')
    _syntax.precedence()
    LPAR = _syntax.token('LPAR')
    RPAR = _syntax.token('RPAR')
    UMINUS = _syntax.token('UMINUS')

    _tokenizer = pl.Tokenizer([
        (NUMBER, r'\d+', int),
        (NAME, r'\w+', str),
        (NEWLINE, r'\n+', lambda loc, text: loc.lines(len(text))),
        (EQUALS, r'='),
        (PLUS, r'\+', str),
        (MINUS, r'-', str),
        (TIMES, r'\*', str),
        (DIVIDE, r'/', str),
        (LPAR, r'\('),
        (RPAR, r'\)'),
        ("WHITE", r'\s+'),
        ("MISMATCH", r'.', lambda loc, text: pl.throw(pl.MismatchError(loc, text)))
    ], default_action=lambda loc, text: loc.step(len(text)))

    @_syntax(NUMBER)
    def EXPR(self, value):
        self._steps.append(value)
        return value

    @_syntax(NAME)
    def EXPR(self, name):
        self._steps.append(name)
        return self._names[name]

    @_syntax(MINUS, EXPR, precedence=UMINUS)
    def EXPR(self, l, expr):
        self._steps.append(f'-{expr}')
        return -expr

    @_syntax(LPAR, EXPR, RPAR)
    def EXPR(self, l, expr, r):
        self._steps.append(f'({expr})')
        return expr

    @_syntax(EXPR, PLUS, EXPR)
    @_syntax(EXPR, MINUS, EXPR)
    @_syntax(EXPR, TIMES, EXPR)
    @_syntax(EXPR, DIVIDE, EXPR)
    def EXPR(self, l_expr, opr, r_expr):
        code = f'{l_expr}{opr}{r_expr}'
        self._steps.append(code)
        return eval(code)

    @_syntax(NAME, EQUALS, EXPR)
    def EXPR(self, name, _, expr):
        self._steps.append(f'{name}={expr}')
        self._names[name] = expr
        return expr

    _states = _syntax.generate(EXPR)

    def __init__(self):
        self._names = {}
        self._steps = []

    def compile_string(self, string):
        return pl.parse(self._states, self._tokenizer.scan_string(string), context=self)


class TestCalc(unittest.TestCase):
    def test_right_associativity(self):
        compiler = CompilerCalc()
        result = compiler.compile_string('a=b=3')
        self.assertEqual(result, 3)
        self.assertListEqual(compiler._steps, [3, 'b=3', 'a=3'])

    def test_left_associativity(self):
        compiler = CompilerCalc()
        result = compiler.compile_string('2+3+4')
        self.assertEqual(result, 9)
        self.assertListEqual(compiler._steps, [2, 3, '2+3', 4, '5+4'])

    def test_precedence(self):
        compiler = CompilerCalc()
        result = compiler.compile_string('2+3*4')
        self.assertEqual(result, 14)
        self.assertListEqual(compiler._steps, [2, 3, 4, '3*4', '2+12'])

    def test_group(self):
        compiler = CompilerCalc()
        result = compiler.compile_string('2+(3+4)')
        self.assertEqual(result, 9)
        self.assertListEqual(compiler._steps, [2, 3, 4, '3+4', '(7)', '2+7'])

    def test_minus(self):
        compiler = CompilerCalc()
        result = compiler.compile_string('-2*3')
        self.assertEqual(result, -6)
        self.assertListEqual(compiler._steps, [2, '-2', 3, '-2*3'])

    def test_assign(self):
        compiler = CompilerCalc()
        result = compiler.compile_string('x=1+2*-3')
        self.assertEqual(result, -5)
        self.assertEqual(compiler._names['x'], -5)
        self.assertListEqual(compiler._steps, [1, 2, 3, '-3', '2*-3', '1+-6', 'x=-5'])


class TestConflict(unittest.TestCase):
    def test_reduce_reduce(self):
        syntax = pl.Syntax()
        A = syntax.token('A')
        B = syntax.token('B')

        LIST = syntax.symbol('LIST')
        LIST.add(A, B)

        EXPR = syntax.symbol('EXPR')
        EXPR.add(LIST)
        EXPR.add(A, B)

        self.assertRaises(pl.ConflictReduceReduceError, lambda: syntax.generate(EXPR))

    def test_shift_reduce(self):
        syntax = pl.Syntax(auto_shift=False)

        A = syntax.token('A')
        B = syntax.token('B')

        LIST = syntax.symbol('LIST')
        LIST.add(A, B)

        EXPR = syntax.symbol('EXPR')
        EXPR.add(LIST)
        EXPR.add(A)

        self.assertRaises(pl.ConflictShiftReduceError, lambda: syntax.generate(EXPR))


class CompilerList:
    _syntax = pl.Syntax()

    DIGITS = _syntax.token('DIGITS')

    _tokenizer = pl.Tokenizer([
        (DIGITS, r'\d', str),
        ("NEWLINE", r'\n+', lambda loc, text: loc.lines(len(text))),
        ("WHITE", r'\s+'),
        ("MISMATCH", r'.', lambda loc, text: pl.throw(pl.MismatchError(loc, text)))
    ], default_action=lambda loc, text: loc.step(len(text)))

    @_syntax(DIGITS)
    def NUMBER(self, val):
        return val

    @_syntax()
    def EXPR(self):
        return []

    @_syntax(NUMBER)
    def EXPR(self, val):
        return [val]

    @_syntax(EXPR, NUMBER)
    def EXPR(self, expr, num):
        expr.append(num)
        return expr

    _states = _syntax.generate(EXPR)

    def compile_string(self, string):
        return pl.parse(self._states, self._tokenizer.scan_string(string), context=self)


class TestList(unittest.TestCase):
    def test_new_line(self):
        compiler = CompilerList()
        lst = compiler.compile_string('2\n\n34')
        self.assertListEqual(lst, ['2', '3', '4'])

    def test_empty_list(self):
        compiler = CompilerList()
        lst = compiler.compile_string('')
        self.assertListEqual(lst, [])


class TestTokenizer(unittest.TestCase):
    def test_mismatch(self):
        _syntax = pl.Syntax()

        DIGITS = _syntax.token('DIGITS')

        _tokenizer = pl.Tokenizer([
            (DIGITS, r'\d', str),
            ("NEWLINE", r'\n+', lambda loc, text: loc.lines(len(text))),
            ("WHITE", r'\s+'),
            ("MISMATCH", r'.', lambda loc, text: pl.throw(pl.MismatchError(loc, text)))
        ], default_action=lambda loc, text: loc.step(len(text)))

        def scan(s):
            return list(map(lambda v: v.value, _tokenizer.scan_string(s, raise_eof=False)))

        self.assertListEqual(scan('123'), ['1', '2', '3'])
        self.assertListEqual(scan('12\n3'), ['1', '2', '3'])
        self.assertListEqual(scan('12 3'), ['1', '2', '3'])

        self.assertRaises(pl.MismatchError, lambda *args: scan('x'))
        self.assertRaises(pl.MismatchError, lambda *args: scan('x1'))
        self.assertRaises(pl.MismatchError, lambda *args: scan('1x'))
