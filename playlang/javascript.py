import io
import re
from playlang.parser import Syntax, Symbol, Token


_TOKEN_READER = """
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


def _generate(syntax: Syntax, states: list, patterns, file):
    p = Printer(file)
    p + '// generated code'

    idx = 1
    for token,*_ in patterns:
        if isinstance(token, Token) and token.ignorable:
            p + f'const {token} = {idx * 100000}'
        else:
            p + f'const {token} = {idx}'
        idx += 1
    # TODO ignorable
    p + f'const {states.__EOF__.name} = {idx}'
    idx += 1

    idx = -1
    p + f'const {states.__START__.name} = {idx}'
    idx -= 1

    for symbol in syntax._defined_symbols:
        p + f'const {symbol} = {idx}'
        idx -= 1

    r = re.compile(r'(?:[^\\]|^)\(')

    buf = []
    group = 1

    p + ''
    p < 'const token_map = {'
    for token, pattern, action, *extra_info in patterns:
        if len(extra_info) > 0 and extra_info[0] is not None:
            action = extra_info[0].get('javascript', 'return $1')
        else:
            action = 'return $1'
        p + f'{group}:[{token}, ($1) => {{ {action} }}],'
        buf.append(f'({pattern})')
        group += len(r.findall(pattern)) + 1
    p > '}'

    p + f"""
const regex = /{'|'.join(buf)}/g
export function* scan(content) {{
    for (const m of content.matchAll(regex)) {{
        for (const [idx, tok] of Object.entries(token_map)) {{
            if (m[idx] !== undefined) {{
                const [tok, act] = token_map[idx]
                yield [tok, act(m[idx])]
            }}
        }}
    }}
    yield [__EOF__, null]
}}"""

    states_ids = {}
    for idx, state in enumerate(syntax._merged_states):
        states_ids[state] = idx

    p + _TOKEN_READER

    p + ''
    p < 'export function parse(tokenizer, context) {'
    p + f'const state_stack = [{states_ids[states]}]'
    p + f'const token_reader = new TokenReader(tokenizer, {states.__START__.name}, {states.__EOF__.name})'
    p + 'var lookahead = token_reader.peek()'

    p < 'while(!token_reader.done()) {'

    p < 'switch(state_stack[state_stack.length - 1]) {'
    for state in syntax._merged_states:
        p < f'case {states_ids[state]}:'

        p < 'switch(lookahead[0]) {'

        if len(state.next_states) > 0:
            for ts, st in state.next_states.items():
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
                p + f'for (const tv of token_reader.consume({len(state.reduce_rule)})) {{ args.push(tv[1]) }}'
                if state.reduce_rule.symbol.name != '__START__':
                    p + f'const value = context["{state.reduce_rule["javascript"]}"].apply(context, args)'
                else:
                    p + 'const value = args[0]'
                p + f'token_reader.commit([{state.reduce_rule.symbol}, value])'
            p + f'state_stack.splice(state_stack.length - {len(state.reduce_rule)}, {len(state.reduce_rule)})'
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


class JavaScript:
    @staticmethod
    def generate(compiler, file, **kwargs):
        syntax = getattr(compiler, '__syntax__')
        states = getattr(compiler, '__states__')
        patterns = getattr(compiler, '__patterns__')
        return _generate(syntax, states, patterns, file)
