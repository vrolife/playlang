import io
import re
from typing import List
from playlang.syntex import State
from playlang.api import TokenInfo, SymbolInfo, ScanInfo


_CLASSES = """
class TokenReader {
    constructor(tokenizer, start, eof) {
        this._tokenizer = tokenizer
        this._start = start
        this._eof = eof
        this._stack = []
        this._next_token = null
    }
    
    _read() {
        try {
            const {done, value} = this._tokenizer.next()
            if (done) {
                return [this._eof, null]
            }
            return value
        } catch(error) {
            return [this._eof, null]
        }
    }
    
    done() { return this._stack.length == 1 && this._stack[this._stack.length-1][0] === this._start; }
    top() { return this._stack[this._stack.length - 1]; }
    peek() {
        if (this._next_token === null) {
            this._next_token = this._read()
        }
        return this._next_token
    }
    
    discard() { this._next_token = null; }
    
    read() {
        var t = this._next_token
        if (t === null) {
            t = this._read()
        } else {
            this._next_token = null
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

class Location {
    constructor(filename, line_num, column) {
        this._filename = filename
        this._line_num = line_num
        this._column = column
    }

    lines(n) {
        this._line_num += n
        this._column = 0
        return null
    }

    step(n) {
        this._column += n
        return null
    }

    copy() {
        return new Location(this._line_num, this._column, this._filename)
    }
}

class Context {
    constructor(name, regexp, value, location, enter, leave) {
        this.name = name
        this._regexp = regexp
        this._value = value
        this.text = null
        this._location = location

        this.enter = enter
        this.leave = leave
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
    }

    lines(n) {
        this._location.lines(n)
    }
}
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

class JavaScript:
    def __init__(self, code):
        self._code = code

    def __call__(self, symbol):
        if isinstance(symbol, SymbolInfo):
            symbol.extra_info['javascript'] = self._code
            return symbol
        elif isinstance(symbol, TokenInfo):
            symbol['javascript'] = self._code
            return symbol
        raise TypeError('unsupported target %s' % symbol)

    @staticmethod
    def generate(parser, file):
        scan_info = parser.__scan_info__ # type: ScanInfo
        p = Printer(file)
        p + '// generated code'

        p + _CLASSES

        idx = 1
        for token, token_info in scan_info.tokens.items():
            if token_info.get('ignorable', False):
                p + f'const {token} = {idx * 100000}'
            else:
                p + f'const {token} = {idx}'
            idx += 1
        # TODO ignorable
        p + f'const {parser.__eof_symbol__.name} = {idx}'
        idx += 1

        idx = -1
        p + f'const {parser.__start_symbol__.name} = {idx}'
        idx -= 1

        for symbol in parser.__symbol_list__:
            p + f'const {symbol} = {idx}'
            idx -= 1

        p + ''
        p < 'const capture = {'
        for name, token_info in scan_info.tokens.items():
            pattern, capture = map(token_info.get, ('pattern', 'capture'))
            action = token_info.get('javascript', 'return ctx.text')
            discard = token_info.get('discard')

            if capture is not None:
                p + f'"{capture}": [{name}, {bool(discard).numerator}, (ctx) => {{ {action} }}],'

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

                p + f'{group}:[{token}, {bool(discard).numerator}, (ctx) => {{ {action} }}],'
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

    stack.push(new Context('__default__', regexps['__default__'], null, location, enter, leave))

    while (true) {{
        var ctx = stack[stack.length - 1]

        if (leave_flag) {{
            leave_flag = false
            const [tok, discard, action] = capture[ctx.name]
            const value = action(ctx)
            if (!discard) {{
                yield [tok, value]
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
                    yield [tok, value]
                }}
                break
            }}
        }}
    }}

    yield [__EOF__, null]
}}"""

        states_ids = {}
        for idx, state in enumerate(parser.__state_list__):
            states_ids[state] = idx

        p + ''
        p < 'export function parse(tokenizer, context) {'
        p + f'const state_stack = [{states_ids[parser.__state_tree__]}]'
        p + \
            f'const token_reader = new TokenReader(tokenizer, {parser.__start_symbol__.name}, {parser.__eof_symbol__.name})'
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
                    p + 'if (lookahead[0] > 0) token_reader.read()'
                    p + 'lookahead = token_reader.peek()'
                    p >> 'break'

            p + 'default:'
            p << 'if (lookahead[0] > 0 && lookahead[0]> 100000)'
            p < '{'
            p + 'token_reader.discard()'
            p + 'lookahead = token_reader.peek()'
            p + 'break'
            p > '}'

            if state.reduce_rule is not None:
                if state.reduce_rule.action is None:
                    p + f'token_reader.consume({len(state.reduce_rule)})'
                    p + f'token_reader.commit([{state.reduce_rule.symbol}, null])'
                else:
                    p + 'const args = []'
                    p + \
                        f'for (const tv of token_reader.consume({len(state.reduce_rule)})) {{ args.push(tv[1]) }}'
                    if state.reduce_rule.symbol.name != '__START__':
                        if 'javascript' not in state.reduce_rule.extra_info:
                            raise TypeError("rule %s missing javascript action" % state.reduce_rule)
                        p + \
                            f'const value = context["{state.reduce_rule.extra_info["javascript"]}"].apply(context, args)'
                    else:
                        p + 'const value = args[0]'
                    p + f'token_reader.commit([{state.reduce_rule.symbol}, value])'
                p + \
                    f'state_stack.splice(state_stack.length - {len(state.reduce_rule)}, {len(state.reduce_rule)})'
                p + 'lookahead = token_reader.top()'
            else:
                p + 'throw Error(`unexpected token ${lookahead[0]}`)'

            p >> 'break'
            p > '}'
            p + 'break'
            p > ''

        p > '}'
        p > '}'  # while
        p + 'return token_reader.pop()[1]'
        p > '}'  # function

