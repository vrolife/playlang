import playlang as pl

syntax = pl.Syntax()

NUMBER = syntax.token('NUMBER')
NAME = syntax.token('NAME')
NEWLINE = syntax.token('NEWLINE')
syntax.right()
EQUALS = syntax.token('EQUALS')
syntax.left()
PLUS = syntax.token('PLUS')
MINUS = syntax.token('MINUS')
syntax.left()
TIMES = syntax.token('TIMES')
DIVIDE = syntax.token('DIVIDE')
syntax.precedence()
LPAR = syntax.token('LPAR')
RPAR = syntax.token('RPAR')

names = {}


@syntax(NUMBER)
def EXPR(value):
    return value


@syntax(NAME)
def EXPR(name):
    return names[name]


@syntax(MINUS, EXPR)
def EXPR(l, expr):
    return -expr


@syntax(LPAR, EXPR, RPAR)
def EXPR(l, expr, r):
    return expr


@syntax(EXPR, PLUS, EXPR)
@syntax(EXPR, MINUS, EXPR)
@syntax(EXPR, TIMES, EXPR)
@syntax(EXPR, DIVIDE, EXPR)
def EXPR(l_expr, opr, r_expr):
    code = f'{l_expr}{opr}{r_expr}'
    print(code)
    return eval(code)


@syntax(NAME, EQUALS, EXPR)
def EXPR(name, _, expr):
    print(f'{name}={expr}')
    names[name] = expr
    return expr


states = syntax.generate(EXPR)

tokenizer = pl.Tokenizer([
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

# while True:
#     try:
#         s = input('#> ')
#         print(pl.parse(states, tokenizer.scan_string(s)))
#     except SyntaxError as e:
#         print(e)
#         pass

result = pl.parse(states, tokenizer.scan_string('a=b=3'))
print(f'={result}')

result = pl.parse(states, tokenizer.scan_string('2+3+4'))
print(f'={result}')

result = pl.parse(states, tokenizer.scan_string('2+3*4'))
print(f'={result}')
