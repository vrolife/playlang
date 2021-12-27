import re
from playlang.syntex import State
from playlang.api import TokenInfo, SymbolInfo, ScanInfo

_CLASSES = """
class TokenReader {
    constructor(tokenizer, start, eof) {
        this._tokenizer = tokenizer
        this._start = start
        this._eof = eof
        this._stack = []
        this._next_token = undefined
    }
    
    _read() {
        const {done, value} = this._tokenizer.next()
        if (done) {
            return [this._eof, undefined, undefined]
        }
        return value
    }
    
    done() { return this._stack.length == 1 && this._stack[this._stack.length-1][0] === this._start; }
    top() { return this._stack[this._stack.length - 1]; }
    peek() {
        if (this._next_token === undefined) {
            this._next_token = this._read()
        }
        return this._next_token
    }
    
    discard() { this._next_token = undefined; }
    
    read() {
        var t = this._next_token
        if (t === undefined) {
            t = this._read()
        } else {
            this._next_token = undefined
        }
        this._stack.push(t)
    }
    
    consume(n) {
        if (n == 0) {
            return []
        }
        return this._stack.splice(this._stack.length - n, n)
    }
    
    commit(tv) {
        this._stack.push(tv)
    }
    
    pop() {
        return this._stack.pop()
    }
    
    push(tv) {
        this._stack.push(tv)
    }
}

export class Location {
    constructor(filename, line_num, column) {
        this._filename = filename
        this._line_num = line_num
        this._column = column
    }

    get filename() {
        return this._filename
    }

    get line() {
        return this._line_num
    }

    get column() {
        return this._column
    }

    lines(n) {
        this._line_num += n
        this._column = 0
        return undefined
    }

    step(n) {
        this._column += n
        return undefined
    }

    copy() {
        return new Location(this._line_num, this._column, this._filename)
    }
}

export class Context {
    constructor(name, regexp, value, location, enter, leave) {
        this.name = name
        this._regexp = regexp
        this._value = value
        this.text = undefined
        this._location = location

        this.enter = (name, value) => { enter(name, value); return this; }
        this.leave = () => { leave(); return this; }
    }

    get value() {
        return this._value
    }

    get location() {
        return this._location
    }

    step(n) {
        if(n === undefined) {
            location.step(this.text.length)
        } else {
            location.step(n)
        }
        return this
    }

    lines(n) {
        this._location.lines(n)
        return this
    }
}

export class TrailingJunk extends Error {}
export class SyntaxError extends Error {}
"""


class LineAppend:

    def __init__(self, file):
        self._file = file

    def __del__(self):
        self._file.write('\n')

    def __add__(self, text):
        self._file.write(text)
        return self


class Printer:

    def __init__(self, file):
        self._indent = 0
        self._file = file

    def __call__(self):
        return LineAppend(self._file)

    def __lt__(self, line):
        self + line
        self._indent += 4
        return None

    def __add__(self, line):
        self._file.write(' ' * self._indent)
        self._file.write(line)
        return LineAppend(self._file)

    def __or__(self, line):
        self._file.write(line)
        return LineAppend(self._file)

    def __gt__(self, line):
        self._indent -= 4
        self + line
        return None

    def __lshift__(self, line):
        self._indent += 4
        self + line

    def __rshift__(self, line):
        self + line
        self._indent -= 4

    def array(self, items, single_line=False):
        if single_line:
            self + ', '.join(items)
        else:
            for item in items:
                self + item + ','


def _generate(parser, file):
    scan_info = parser.__scan_info__  # type: ScanInfo
    p = Printer(file)
    p + '// generated code'

    p + _CLASSES

    symbol_map = {}

    idx = 1
    for token, token_info in scan_info.tokens.items():
        if token_info.get('ignorable', False):
            symbol_map[token] = idx + 10000
        else:
            symbol_map[token] = idx
        idx += 1

    # TODO ignorable
    symbol_map[parser.__eof_symbol__] = idx
    idx += 1

    idx = 20000
    symbol_map[parser.__start_symbol__] = idx
    idx += 1

    for symbol in parser.__symbol_list__:
        symbol_map[symbol] = idx
        idx += 1

    for sym, idx in symbol_map.items():
        p + f'const {sym} = {idx}'

    p + ''
    p < 'const show_name = {'
    for sym, idx in symbol_map.items():
        if isinstance(sym, str):
            ti = scan_info.tokens[sym]
            name = ti.get('show_name', sym)
        else:
            name = sym.show_name
        p + f'{idx}: "{name}",'
    p > '}'

    p + ''
    p < 'const capture = {'
    for name, token_info in scan_info.tokens.items():
        pattern, capture = map(token_info.get, ('pattern', 'capture'))
        action = token_info.get('javascript', 'return ctx.text')
        discard = token_info.get('discard')

        if capture is not None:
            p + f'"{capture}": [{name}, {bool(discard).numerator}, (ctx) => {{ {action} }}],'  # nopep8

    p > '}'

    r = re.compile(r'(?:[^\\]|^)\(')

    regexps = {}
    p + ''
    p < 'const actions = {'
    for context, tokens in scan_info.contexts.items():
        buf = []
        group = 1

        p < f'"{context}": {{'
        for token in tokens:
            token_info = scan_info.tokens[str(token)]
            action = token_info.get('javascript', 'return ctx.text')
            pattern = token_info.get('pattern')
            discard = token_info.get('discard')

            if token_info.get('capture', False):
                continue

            if pattern is None:
                raise TypeError('token missing pattern: %s' % token)

            p + f'{group}:[{token}, {bool(discard).numerator}, (ctx) => {{ {action} }}],'  # nopep8
            buf.append(f'({pattern})')
            group += len(r.findall(pattern)) + 1
        p > '},'

        regexps[context] = '|'.join(buf)
    p > '} // actions'
    p + ''
    p < 'const regexps = {'
    for context, _ in scan_info.contexts.items():
        p + f'"{context}": /{regexps[context]}/g,'
    p > '}'

    p + f"""
export function* scan(content, filename) {{
    if (filename === undefined) {{
        filename = '<memory>'
    }}
    const location = new Location(filename, 0, 0)
    const stack = []
    var leave_flag = false
    var pos = 0

    const leave = () => {{
        leave_flag = true
    }}

    const enter = (name, value) => {{
        stack.push(new Context(name, regexps[name], value, location, enter, leave))
    }}

    stack.push(new Context('__default__', regexps['__default__'], undefined, location, enter, leave))

    while (true) {{
        var ctx = stack[stack.length - 1]

        if (leave_flag) {{
            leave_flag = false
            if (ctx.name in capture) {{
                const [tok, discard, action] = capture[ctx.name]
                const value = action(ctx)
                if (!discard) {{
                    yield [tok, value, location]
                }}
            }}
            stack.pop()
            ctx = stack[stack.length - 1]
        }}

        ctx._regexp.lastIndex = pos
        const m = ctx._regexp.exec(content)
        if (m === null) {{
            break
        }}
        pos = ctx._regexp.lastIndex

        const action_map = actions[ctx.name]

        for (const [idx, token_info] of Object.entries(action_map)) {{
            if (m[idx] !== undefined) {{
                ctx.text = m[idx]
                const [tok, discard, action] = token_info
                const value = action(ctx)
                if (!discard) {{
                    yield [tok, value, location]
                }}
                break
            }}
        }}
    }}

    if (pos !== content.length){{
        throw new TrailingJunk(location)
    }}
}}"""

    states_ids = {}
    for idx, state in enumerate(parser.__state_list__):
        states_ids[state] = idx

    p + ''
    p < 'export function parse(tokenizer, context) {'
    p + f'const state_stack = [{states_ids[parser.__state_tree__]}]'
    p + f'const token_reader = new TokenReader(tokenizer, {parser.__start_symbol__.name}, {parser.__eof_symbol__.name})'  # nopep8
    p + 'var lookahead = token_reader.peek()'

    p < 'while(!token_reader.done()) {'

    p < 'switch(state_stack[state_stack.length - 1]) {'
    for state in parser.__state_list__:
        p < f'case {states_ids[state]}:'

        p < 'switch(lookahead[0]) {'

        if len(state.branchs) > 0:
            for ts, st in state.branchs.items():
                p + f'case {ts.name}:'
                p << f'state_stack.push({states_ids[st]})'
                p + 'if (lookahead[0] < 20000) token_reader.read()'
                p + 'lookahead = token_reader.peek()'
                p >> 'break'

        p < 'default:'

        if state.reduce_rule is not None:
            if state.reduce_rule.action is None:
                p + f'token_reader.consume({len(state.reduce_rule)})'
                p + f'token_reader.commit([{state.reduce_rule.symbol}, undefined])'  # nopep8
            else:
                p + f'const args = token_reader.consume({len(state.reduce_rule)}).map(tv => tv[1])'   # nopep8
                if state.reduce_rule.symbol.name != '__START__':
                    code, func = map(state.reduce_rule.extra_info.get,
                                     ('javascript', 'javascript_function'))
                    if code is not None:
                        p < f'function action({", ".join([f"${x+1}" for x in range(len(state.reduce_rule))])}) {{'
                        p + code
                        p > '}'
                    elif func is not None:
                        p + f'const action = context["{func}"]'
                    else:
                        raise TypeError("rule %s missing javascript action" % state.reduce_rule)  # nopep8

                    p + f'const value = action.apply(context, args)'

                else:
                    p + 'const value = args[0]'
                p + f'token_reader.commit([{state.reduce_rule.symbol}, value])'  # nopep8
            p + f'state_stack.splice(state_stack.length - {len(state.reduce_rule)}, {len(state.reduce_rule)})'  # nopep8
            p + 'lookahead = token_reader.top()'
        else:
            p + 'if (lookahead[0] < 20000 && lookahead[0]> 10000)'
            p < '{'
            p + 'token_reader.discard()'
            p + 'lookahead = token_reader.peek()'
            p + 'break'
            p > '}'

            count = len(state.immediate_tokens)
            message = ""

            if count == 1:
                message = f', expecting {state.immediate_tokens[0].show_name}'
            elif count == 2:
                message = f', expecting {state.immediate_tokens[0].show_name} or {state.immediate_tokens[1].show_name}'
            else:
                message = f', expecting one of [{" ".join([t.show_name for t in state.immediate_tokens])}]'

            p + 'const [token, value, loc] = lookahead'
            p + 'var location = ""'
            p + 'if (loc !== undefined) { location = `${loc.filename}${loc.line}:${loc.column} => ` }'  # nopep8
            p + f'throw new SyntaxError(`${{location}}unexpected token ${{show_name[token]}}(${{value}}){message}`)'  # nopep8

        p >> 'break'
        p > '}'
        p + 'break'
        p > ''

    p > '}'
    p > '}'  # while
    p + 'return token_reader.pop()[1]'
    p > '}'  # function


class JavaScript:

    def __init__(self, code=None, function=None):
        self._js_info = {}
        if code is not None:
            self._js_info['javascript'] = code

        if function is not None:
            self._js_info['javascript_function'] = function

    def __call__(self, symbol):
        if isinstance(symbol, SymbolInfo):
            symbol.extra_info.update(self._js_info)
            return symbol
        elif isinstance(symbol, TokenInfo):
            symbol.update(self._js_info)
            return symbol
        raise TypeError('unsupported target %s' % symbol)

    @staticmethod
    def generate(parser, file):
        return _generate(parser, file)
