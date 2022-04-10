# pylint: disable=pointless-statement,expression-not-assigned,line-too-long

import re
from playlang.classes import SymbolInfo, TokenInfo, Symbol
from playlang.printer import Printer

def apply_args(reduce_rule):
    args = []
    for i, t in enumerate(reduce_rule):
        if isinstance(t, Symbol):
            args.append(f'value_of(args, {i}, typename Tokenizer::type_{t})')
        else:
            args.append(f'args.at({i})._value.as<Tokenizer::type_{t}>')
    return ', '.join(args)

def _generate(parser, file, prefix):
    scan_info = parser.__scan_info__  # type: dict
    p = Printer(file)
    p + '// generated code'
    p + f'#define PLAYLANG_PARSER_NAMESPACE {prefix}'
    p + '#include "scanner.hpp"'

    show_name = {}

    # generate ids

    next_tid = 1

    p + f'#define TID___EOF__ {next_tid}'  # nopep8
    show_name[next_tid] = parser.__eof_symbol__.show_name
    next_tid += 1

    all_tokens = set()
    for _, tokens in scan_info.items():
        for token in tokens:
            all_tokens.add(token)

    all_tokens = list(all_tokens)
    all_tokens.sort(key=lambda t: t.fullname)

    for token in all_tokens:
        tid = next_tid + (10000 if token.ignorable else 0)
        p + f'#define TID_{token.fullname} {tid}'  # nopep8
        show_name[tid] = token.show_name
        next_tid += 1

    assert next_tid < 20000
    next_tid = 20000

    for symbol in parser.__symbols__:
        p + f'#define TID_{symbol.fullname} {next_tid}'
        show_name[tid] = symbol.show_name
        next_tid += 1

    # Scanner
    p + '''
struct Location {
    std::string _filename{};
    int _line_number;
    int _column;

    Location() : _line_number(0), _column(0) { }
    Location(const Location&) = default;

    void lines(int n) {
        this->_line_number += n;
        this->_column = 0;
    }

    void step() {
        this->_column += 1;
    }

    bool valid() const {
        return _line_number >= 0 and _column >= 0;
    }
};

class ScannerContext
{
    std::string _name;
    std::regex _regexp;
    Location _location;
    std::string _text;

public:
    ScannerContext(const std::string& name, )
    std::string& text() {
        return _text;
    }

    void step() {
        _location.step(_text.size());
    }

    void step(int n) {
        _location.step(n);
    }

    void lines(int n) {
        _location.lines(n);
    }
};
'''
    p + 'template<typename Impl>'
    p + f'class {prefix} : public Impl {{'
    p + 'public:'
    p << ''
    p + 'class Value;'
    p + 'class TokenValue;'

    # token action
    r = re.compile(r'(?:[^\\]|^)\(')
    regexps = {}
    for context, tokens in scan_info.items():
        buf = []
        group_to_action = {}
        group = 1

        for token in tokens:
            action = token.data.get('cpp', 'return ctx.text()')
            pattern, discard, fullname = map(
                token.data.get, ('pattern', 'discard', 'fullname'))
            if token.capture:
                continue
            if pattern is None:
                raise TypeError(f'token missing pattern: {token}')
            p + f'auto action_{fullname}(ContextScan& ctx) {{'
            p + f'    {action};'
            p + '}'
            group_to_action[group] = (fullname, discard, f'action_{fullname}')
            buf.append(f'({pattern})')
            group += len(r.findall(pattern)) + 1

        regexps[context] = '|'.join(buf).replace("\"", r"\\\"")

        p < f'TokenValue run_token_action_{context}(ContextScan& ctx, int regexp_index) {{'
        p < 'switch(regexp_index) {'
        for g, (fullname, discard, action) in group_to_action.items():
            p + f'case {g}: return TokenValue{{ TID_{fullname}, {str(bool(discard)).lower()}, {action}(ctx) }};'
        p > '}'
        p + 'assert(0 && "invalid index");'
        p > '}'
        
    p < 'const regexps = {'
    for context, _ in scan_info.items():
        p + f'"{context}": "{regexps[context]}",'
    p > '}'

    p >> ''
    p + '};'
    p + ''

    p + '#define TOKEN_LIST(F) \\'
    for token in all_tokens:
        p + f'    F({token.fullname}) \\'
    p + ''

    p + f'''
#define TYPE_OF_TOKEN(n) std::result_of<{prefix}<Impl>::action_##n)>::type
#define VALUE_UNION_MEMBER(n) TYPE_OF_TOKEN(n) _##n;
#define VALUE_GET_VALUE(n) inline auto get_##n() {{ return _u._##n; }}
#define VALUE_ENUM_MEMBER(n) ValueType##n,
#define VALUE_MOVE_CONSTRUCTOR(n) case ValueType##n: _u._##n = std::move(other._##n);break;
#define VALUE_COPY_CONSTRUCTOR(n) case ValueType##n: _u._##n = other._u._##n;break;
#define VALUE_CONSTRUCTOR(n) Value(TYPE_OF_TOKEN(n)&& val) : _type(ValueType##n) {{ _u._#n = std::move(val); }}

template<typename Impl>
struct {prefix}_tokenizer<Impl>::Value {{

    enum ValueType {{
        ValueTypePlaylangUnknownValue,
        TOKEN_LIST(VALUE_ENUM_MEMBER)
    }};
    union {{
        int _playlang_unknown_value{{0}};
        TOKEN_LIST(VALUE_UNION_MEMBER)
    }} _u;

    ValueType _type{{ValueTypePlaylangUnknownValue}};

    Value() = default;
    TOKEN_LIST(VALUE_CONSTRUCTOR)
    Value(Value&& other) {{
        _type = other._type;
        switch(_type) {{
            TOKEN_LIST(VALUE_COPY_CONSTRUCTOR)
        }}
        other._type = ValueTypePlaylangUnknownValue;
    }}

    Value(const Value& other) {{
        _type = other._type;
        switch(_type) {{
            TOKEN_LIST(VALUE_COPY_CONSTRUCTOR)
        }}
    }}

    Value& operator =(Value&& other) {{
        _type = other._type;
        switch(_type) {{
            TOKEN_LIST(VALUE_MOVE_CONSTRUCTOR)
        }}
        other._type = ValueTypePlaylangUnknownValue;
        return *this;
    }}

    Value& operator =(const Value& other) {{
        _type = other._type;
        switch(_type) {{
            TOKEN_LIST(VALUE_COPY_CONSTRUCTOR)
        }}
        return *this;
    }}

    bool empty() const {{ return _type == ValueTypePlaylangUnknownValue; }}
}};

template<typename Impl>
struct {prefix}<Impl>::TokenValue {{
    int _token{{0}};
    bool _discard{{false}};
    Value _value{{}};
    Location _location{{}};

    template<typename V>
    TokenValue(int token, V&& value)
    : _token(token), _value(std::forward<V>(value))
    {{

    }}

    template<typename V>
    TokenValue(int token, bool discard, V&& value)
    : _token(token), _discard(discard), _value(std::forward<V>(value))
    {{

    }}

    TokenValue() = default;
    TokenValue(TokenValue&& other) {{
        _token = other._token;
        _discard = other._discard;
        _value = std::move(other._value);
        _location = other._location;
        other._token = 0;
        other._discard = false;
    }}
    TokenValue(const TokenValue&) = default;
    TokenValue& operator = (TokenValue&&) {{
        _token = other._token;
        _discard = other._discard;
        _value = std::move(other._value);
        _location = other._location;
        other._token = 0;
        other._discard = false;
        return *this;
    }}
    TokenValue& operator = (const TokenValue&) = default;

    bool empty() const {{ return _token == 0; }}
}};

template<typename Tokenizer>
class TokenReader
{{
    Tokenizer _tokenizer;
    int _start;
    int _eof;

    typedef typename Tokenizer::TokenValue TokenValue;

    std::stack<TokenValue> _stack;
    TokenValue _next_token;

    std::pair<int, Value> _read() {{
        auto tmp = _tokenizer++;
        if (tmp->first == _eof) {{
            return {{_eof, {{}};
        }}
        return std::move(*tmp);
    }}

public:
    TokenReader(Tokenizer&& tokenizer, int start, int eof)
    : _tokenizer(std::move(tokenizer)), _start(start), _eof(eof)
    {{
        
    }}

    bool done() {{
        return _stack.size() == 1 and _stack.back().first == _start;
    }}
    
    TokenValue& top() {{ return _stack.top(); }}

    TokenValue* peek() {{
        if (_next_token.empty()) {{
            _next_token = this._read();
        }}
        return &_next_token;
    }}

    void discard() {{
        _next_token = {{0, {{}}}};
    }}

    void read() {{
        auto t = std::move(_next_token);
        if (t.empty()) {{
            t = _read();
        }}
        _stack.emplace(std::move(t));
    }}

    template<size_t N>
    void consume(std::array<TokenValue, N>& output) {{
        if (N == 0) {{
            return;
        }}
        size_t n = N;
        while (n) {{
            output.at(n) = std::move(_stack.top());
            _stack.pop();
            n -= 1;
        }}
    }}

    void commit(TokenValue&& tv) {{
        _stack.emplace(std::move(tv));
    }}

    TokenValue pop() {{
        auto tv = std::move(_stack.top());
        _stack.pop();
        return tv;
    }}

    void push(TokenValue&& tv) {{
        _stack.emplace(std::move(tv));
    }}
}};
'''
    p + 'template<typename Tokenizer, typename Impl>'
    p + f'class {prefix}_parser : public Impl {{'
    p < 'public:'

    symbol_action_functions = {}

    state_list = list(parser.__state_list__)
    state_list.sort(key=lambda s: str(s.bind_rule) + str(s.bind_index))

    states_ids = {}
    for idx, state in enumerate(state_list):
        states_ids[state] = idx

    p + ''
    p < f'auto {prefix}parse(Tokenizer& tokenizer) {{'
    p + f'std::stack<int> state_stack{{}};'
    p + f'state_stack.push({states_ids[parser.__state_tree__]});'
    p + f'TokenReader<Tokenizer> token_reader{{tokenizer, {parser.__start_symbol__.name}, __EOF__}};'  # nopep8
    p + 'auto* lookahead = token_reader.peek();'

    p < 'while(!token_reader.done()) {'

    p < 'switch(state_stack.top()) {'
    for state in state_list:
        p < f'case {states_ids[state]}:'

        p < 'switch(lookahead->_token) {'

        if len(state.branchs) > 0:
            for ts, st in state.branchs.items():
                p + f'case {ts.fullname}:'
                p << f'state_stack.push({states_ids[st]})'
                p + 'if (lookahead->_token < 20000) token_reader.read()'
                p + 'lookahead = token_reader.peek()'
                p >> 'break;'

        p < 'default:'

        if state.reduce_rule is not None:
            fullname = state.reduce_rule.symbol.fullname
            p + f'std::array<TokenValue, {len(state.reduce_rule)}> args;'
            if state.reduce_rule.action is None:
                p + f'token_reader.consume(args)'
                p + f'token_reader.commit(TokenValue{{TID_{fullname}, {{}}}})'  # nopep8
            else:
                p + f'token_reader.consume(args);'   # nopep8
                if state.reduce_rule.symbol.name != '__START__':
                    code, func = map(state.reduce_rule.extra_info.get,
                                     ('cpp', 'cpp_function'))
                    if func is None:
                        if code is None:
                            raise TypeError(f"rule {state.reduce_rule} missing cpp action")  # nopep8
                        symbol_action_functions[fullname] = state.reduce_rule;
                        func = fullname

                    p + f'auto value = this->{func}({apply_args(state.reduce_rule)});'

                else:
                    p + 'const value = std::move(args[0]);'
                p + f'token_reader.commit(TokenValue{{{fullname}, std::move(value)}})'  # nopep8
            p + f'for(int i = 0 ; i < {len(state.reduce_rule)}; ++i) {{ state_stack.pop(); }}'
            p + 'lookahead = token_reader.top();'
        else:
            p + 'if (lookahead->_token < 20000 && lookahead->_token> 10000)'
            p < '{'
            p + '// ignorable'
            p + 'token_reader.discard()'
            p + 'lookahead = token_reader.peek()'
            p + 'break;'
            p > '}'

            count = len(state.immediate_tokens)
            message = ""

            if count == 1:
                message = f', expecting {state.immediate_tokens[0].show_name}'
            elif count == 2:
                message = f', expecting {state.immediate_tokens[0].show_name} or {state.immediate_tokens[1].show_name}'
            else:
                message = f', expecting one of [{" ".join([t.show_name for t in state.immediate_tokens])}]'

            p + 'std::ostringstream oss;'
            p + 'if (lookahead->_location.valid()) { oss << lookahead->_location.to_string() << " => "; }'  # nopep8
            p + f'oss << "unexpected token " << lookahead->_tokenn << "{message}";'
            p + 'throw SyntaxError(oss.str());'

        p >> 'break;'
        p > '}'
        p + 'break;'
        p > ''

    p > '}'
    p > '}'  # while
    p + 'return token_reader.pop()[1]'
    p > '}'  # function

    p >> ''
    p + '};'

def _generate2(parser, file, prefix):
    scan_info = parser.__scan_info__  # type: dict
    p = Printer(file)
    p + '// generated code'
    p + f'#define PLAYLANG_PARSER_NAMESPACE {prefix}'
    p + '#include "scanner.hpp"'

    show_name = {}

    # generate ids

    next_tid = 1

    p + f'#define TID___EOF__ {next_tid}'  # nopep8
    show_name[next_tid] = parser.__eof_symbol__.show_name
    next_tid += 1

    all_tokens = set()
    for _, tokens in scan_info.items():
        for token in tokens:
            all_tokens.add(token)

    all_tokens = list(all_tokens)
    all_tokens.sort(key=lambda t: t.fullname)

    for token in all_tokens:
        tid = next_tid + (10000 if token.ignorable else 0)
        p + f'#define TID_{token.fullname} {tid}'  # nopep8
        show_name[tid] = token.show_name
        next_tid += 1

    assert next_tid < 20000
    next_tid = 20000

    for symbol in parser.__symbols__:
        p + f'#define TID_{symbol.fullname} {next_tid}'
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
    for context, tokens in scan_info.items():
        for token in tokens:
            if token.capture:
                pattern, discard, fullname = map(
                    token.data.get, ('pattern', 'discard', 'fullname'))
                action = token.data.get('cpp', 'return ctx.text')
                p + f'"{context}": [{fullname}, {bool(discard).numerator}, (ctx) => {{ {action} }}],'  # nopep8
    p > '}'

    r = re.compile(r'(?:[^\\]|^)\(')

    # token action
    regexps = {}
    for context, tokens in scan_info.items():
        buf = []
        group_to_action = {}
        group = 1

        for token in tokens:
            action = token.data.get('cpp', 'return ctx.text()')
            pattern, discard, fullname = map(
                token.data.get, ('pattern', 'discard', 'fullname'))
            if token.capture:
                continue
            if pattern is None:
                raise TypeError(f'token missing pattern: {token}')
            p + f'auto action_{fullname}(ContextScan& ctx) {{'
            p + f'    {action};'
            p + '}'
            group_to_action[group] = (fullname, discard, f'action_{fullname}')
            buf.append(f'({pattern})')
            group += len(r.findall(pattern)) + 1

        regexps[context] = '|'.join(buf).replace("\"", r"\\\"")

        p < f'TokenValue run_token_action_{context}(ContextScan& ctx, int regexp_index) {{'
        p < 'switch(regexp_index) {'
        for g, (fullname, discard, action) in group_to_action.items():
            p + f'case {g}: return TokenValue{{ TID_{fullname}, {str(bool(discard)).lower()}, {action}(ctx) }};'
        p > '}'
        p + 'assert(0 && "invalid index");'
        p > '}'
        
    p < 'const regexps = {'
    for context, _ in scan_info.items():
        p + f'"{context}": "{regexps[context]}",'
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
    p + f'const token_reader = new TokenReader(tokenizer, {parser.__start_symbol__.name}, __EOF__)'  # nopep8
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
                                     ('cpp', 'cpp_function'))
                    if code is not None:
                        p < f'function action({", ".join([f"${x+1}" for x in range(len(state.reduce_rule))])}) {{'
                        p + code
                        p > '}'
                    elif func is not None:
                        p + f'const action = context["{func}"]'
                    else:
                        raise TypeError(f"rule {state.reduce_rule} missing cpp action")  # nopep8

                    p + f'auto value = this->{func}();'

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


class CPlusPlus:

    def __init__(self, code=None, function=None):
        self._js_info = {}
        if code is not None:
            self._js_info['cpp'] = code

        if function is not None:
            self._js_info['cpp_function'] = function

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
