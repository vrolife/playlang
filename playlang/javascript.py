# pylint: disable=pointless-statement,expression-not-assigned,line-too-long

import re
from playlang.classes import SymbolInfo, TokenInfo
from playlang.printer import Printer


def _generate(parser, file, prefix):
    scan_info = parser.__scanners__  # type: dict
    p = Printer(file)
    p + '// generated code'
    p + 'import { TokenReader, SyntaxError, create_scanner } from "./playlang.js"'

    show_name = {}

    # generate ids

    next_tid = 1

    all_tokens = set()
    for _, scanner in scan_info.items():
        for token in scanner.tokens:
            all_tokens.add(token)

    all_tokens = list(all_tokens)
    all_tokens.sort(key=lambda t: t.fullname)

    for token in all_tokens:
        tid = next_tid + (10000 if token.ignorable else 0)
        p + f'const {token.fullname} = {tid}'  # nopep8
        show_name[tid] = token.show_name
        next_tid += 1

    assert next_tid < 20000
    next_tid = 20000

    for symbol in parser.__symbols__:
        p + f'const {symbol.fullname} = {next_tid}'
        show_name[tid] = symbol.show_name
        next_tid += 1

    # generate show name

    p + ''
    p < 'const show_name = {'
    for tid, name in show_name.items():
        p + f'{tid}: "{name}",'
    p > '}'

    p + ''
    p < 'const capture = {'
    for condition, scanner in scan_info.items():
        for token in scanner.tokens:
            if token.capture:
                pattern, discard, fullname = map(
                    token.data.get, ('pattern', 'discard', 'fullname'))
                action = token.data.get('javascript', 'return ctx.text')
                p + f'"{condition}": [{fullname}, {bool(discard).numerator}, (ctx) => {{ {action} }}],'  # nopep8
    p > '}'

    r = re.compile(r'(?:[^\\]|^)\(')

    regexps = {}
    p + ''
    p < 'const actions = {'
    for condition, scanner in scan_info.items():
        buf = []
        group = 1

        p < f'"{condition}": {{'
        for token in scanner.tokens:
            action = token.data.get('javascript', 'return ctx.text')
            pattern, discard, fullname = map(
                token.data.get, ('pattern', 'discard', 'fullname'))

            if token.capture:
                continue

            if token.is_eof:
                continue

            if pattern is None:
                raise TypeError(f'token missing pattern: {token}')

            p + f'{group}:[{fullname}, {bool(discard).numerator}, (ctx) => {{ {action} }}],'  # nopep8
            buf.append(f'({pattern})')
            group += len(r.findall(pattern)) + 1
        p > '},'

        regexps[condition] = '|'.join(buf)
    p > '} // actions'
    p + ''
    p < 'const regexps = {'
    for condition, _ in scan_info.items():
        p + f'"{condition}": /{regexps[condition]}/g,'
    p > '}'

    p + f'export const {prefix}scan = create_scanner(actions, regexps, capture)'
    
    state_list = list(parser.__state_list__)
    state_list.sort(key=lambda s: str(s.bind_rule) + str(s.bind_index))

    states_ids = {}
    for idx, state in enumerate(state_list):
        states_ids[state] = idx

    p + ''
    p < f'export function {prefix}parse(tokenizer, context) {{'
    p + f'const state_stack = [{states_ids[parser.__state_tree__]}]'
    p + f'const token_reader = new TokenReader(tokenizer, {parser.__start_wrapper__.name}, __EOF__)'  # nopep8
    p + 'var lookahead = token_reader.peek()'

    p < 'while(!token_reader.done()) {'

    p < 'switch(state_stack[state_stack.length - 1]) {'
    for state in state_list:
        p < f'case {states_ids[state]}:'

        p < 'switch(lookahead[0]) {'

        if len(state.branchs) > 0:
            for ts, st in state.branchs.items():
                p + f'case {ts.fullname}:'
                p << f'state_stack.push({states_ids[st]})'
                p + 'if (lookahead[0] < 20000) token_reader.read()'
                p + 'lookahead = token_reader.peek()'
                p >> 'break'

        p < 'default:'

        if state.reduce_rule is not None:
            fullname = state.reduce_rule.symbol.fullname

            if state.reduce_rule.action is None:
                p + f'token_reader.consume({len(state.reduce_rule)})'
                p + f'token_reader.commit([{fullname}, undefined])'  # nopep8
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
                        raise TypeError(f"rule {state.reduce_rule} missing javascript action")  # nopep8

                    p + 'const value = action.apply(context, args)'

                else:
                    p + 'const value = args[0]'
                p + f'token_reader.commit([{fullname}, value])'  # nopep8
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
            symbol.data.update(self._js_info)
            return symbol
        elif isinstance(symbol, TokenInfo):
            symbol.data.update(self._js_info)
            return symbol
        raise TypeError(f'unsupported target {symbol}')

    @staticmethod
    def generate(parser, file, prefix=""):
        return _generate(parser, file, prefix)
