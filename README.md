# PLAYLANG

Another simple LR(1) parser generator.

Support Python Javascript C++.

Generated parser licensed under MIT or GPL/LGPL

## Example

```python
class ParserCalc(metaclass=Parser):
    NUMBER = Token(r'[0-9]+',
                   action=int,
                   show_name='Number',
                   javascript='return parseInt(ctx.text)')
    NAME = Token(r'[a-zA-Z_]+',
                 action=str,
                 show_name='Name',
                 javascript='return ctx.text')
    NEWLINE = Token(r'\n+',
                    discard=True,
                    action=lambda ctx: ctx.lines(len(ctx.text)))
    WHITE = Token(r'[ \r\t\v]+', discard=True)
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
    PLUS = Token(r'\+', show_name='Plus')
    MINUS = Token(r'-')

    _ = Precedence.Left
    TIMES = Token(r'\*')
    DIVIDE = Token(r'\/')

    _ = Precedence.Increase
    LPAR = Token(r'\(')
    RPAR = Token(r'\)')
    UMINUS = Token(r'-')

    _ = Scanner(NUMBER, NAME, EQUALS, PLUS, MINUS, TIMES,
            DIVIDE, LPAR, RPAR, QUOTE, NEWLINE, WHITE, MISMATCH)
    _ = Scanner(STRING_QUOTE, STRING_ESCAPE, STRING_CHAR,
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

    scanner = StaticTokenizer(default_action=lambda ctx: ctx.step(len(ctx.text)))

    def __init__(self):
        self.names = {}
        self.steps = []

    def parse_string(self, string):
        return ParserCalc.parse(ParserCalc.scanner(string), context=self)
```

## License

The generated files licensed under `MIT OR LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`

The runtime files licensed under `MIT OR LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`

The generator and the git history commits licensed under `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`
