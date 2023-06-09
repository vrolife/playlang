# Copyright (C) 2023 pom@vro.life
# SPDX-License-Identifier: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only

# pylint: disable=pointless-statement,expression-not-assigned,line-too-long

import re
import sys
import io
import argparse
from playlang.classes import SymbolInfo, TokenInfo, Symbol
from playlang.printer import Printer


def _generate_tokenizer(cls, args):
    scan_info = cls.__scanners__  # type: dict
    p = Printer(args.tokenizer)
    p + '''// Copyright (C) 2023 pom@vro.life
// SPDX-License-Identifier: MIT OR LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only'''
    p + '// generated code'
    p + f'#ifndef __{args.namespace}_tokenizer_hpp__'
    p + f'#define __{args.namespace}_tokenizer_hpp__'
    p + f'#include "playlang/playlang.hpp"'
    p + f'#include "{args.include}"'
    p + f"""
#ifndef PLAYLANG_TOKENIZER_FLEX
#define PLAYLANG_TOKENIZER_FLEX 1
#endif

#if defined(PLAYLANG_TOKENIZER_FLEX) && PLAYLANG_TOKENIZER_FLEX

#ifndef yyFlexLexer
#define yyFlexLexer {args.namespace}FlexLexer
#endif

#ifndef yyFlexLexerOnce
#include <FlexLexer.h>
#endif

#endif
"""
    p + f'namespace {args.namespace} {{'
    p + f"""
#if defined(PLAYLANG_TOKENIZER_FLEX) && PLAYLANG_TOKENIZER_FLEX
template <typename TokenValue>
class TokenizerFlex
: protected yyFlexLexer
{{
public:
    TokenizerFlex(const std::string& filename, std::istream& in,
        std::ostream& out)
        : yyFlexLexer(in, out)
    {{
    }}

    explicit TokenizerFlex(const std::string& filename, std::istream* in = 0,
        std::ostream* out = 0)
        : yyFlexLexer(in, out)
    {{
    }}

    operator std::string() const {{ return {{ text(), text_length() }}; }}

    char at(size_t idx) const {{
        assert(idx < text_length());
        return text()[idx];
    }}

private:
    const char* text() const {{ return YYText(); }}
    size_t text_length() const {{ return YYLeng(); }}
}};
#endif
"""

    show_name = {}

    # generate ids

    next_tid = 1

    captures = []

    all_start_conditions = list()
    all_tokens = set()
    eof_token = None
    for condition, scanner in scan_info.items():
        if condition == '__default__':
            eof_token = scanner.eof_token
        else:
            all_start_conditions.append(f"    static const int {condition};\n")

        for token in scanner.tokens:
            discard, fullname = map(
                token.data.get, ('discard', 'fullname'))
            all_tokens.add(token)
            if token.capture:
                captures.append(f'        if ({condition} == ctx) {{ return {{ {str(discard).lower()}, TokenValue{{ this->location(), std::move(val), TID_{fullname} }} }}; }}')

    all_tokens = list(all_tokens)
    all_tokens.sort(key=lambda t: t.fullname)
    
    for token in all_tokens:
        tid = next_tid + (10000 if token.ignorable else 0)
        p + f'#define TID_{token.fullname} {tid}'  # nopep8
        show_name[tid] = token.show_name
        next_tid += 1

    assert next_tid < 20000
    next_tid = 20000

    for symbol in cls.__symbols__:
        p + f'#define TID_{symbol.fullname} {next_tid}'
        show_name[tid] = symbol.show_name
        next_tid += 1

    types = []
    for token in all_tokens:
        types.append(token.name)
    for symbol in cls.__symbols__:
        types.append(symbol.name)

    type_lines = [f'\n/* {i} */ \t{n}' for i,n in enumerate(types)]

    if '__EOF__' == eof_token.name:
        p + f"""
struct __EOF__ : public playlang::Token<void> {{
    template<typename C>
    explicit __EOF__(C& ctx) {{}};
    __EOF__() = default;
}};"""

    p + f"""
struct __START__ : public playlang::Symbol<typename {cls.__start_symbol__.name}::ValueType> {{
    typedef typename {cls.__start_symbol__.name}::ValueType ResultType;
    __START__({cls.__start_symbol__.name}& s, {eof_token.name}& _) 
    : playlang::Symbol<typename {cls.__start_symbol__.name}::ValueType>(std::move(s.value()))
    {{ }}
}};

typedef playlang::Variant<{", ".join(type_lines)}
> VariantValueType;
typedef playlang::TokenValue<VariantValueType> TokenValue;

inline
const char* get_token_name(int token) {{
    switch(token) {{
{chr(10).join([f'        case {i}: return "{n}";' for i,n in show_name.items()])}
        default: abort();
    }}
}}
"""

    p + f"""
#if defined(PLAYLANG_TOKENIZER_FLEX) && PLAYLANG_TOKENIZER_FLEX
typedef TokenizerFlex<TokenValue> TokenizerBase;
#endif

class Tokenizer
: public TokenizerBase
{f', public {args.statefull_tokenizer}' if args.statefull_tokenizer else ''}
{{
    friend class playlang::TokenReader<Tokenizer>;
public:
    typedef TokenValue TokenValueType;
    typedef typename TokenValue::ValueType ValueType;

    constexpr static int TokenID_START = TID___START__;
    typedef struct __START__ START_Type;

{"".join(all_start_conditions)}

    template<typename... Args>
    Tokenizer(Args&&... args) : TokenizerBase(std::forward<Args>(args)...)
    {{
        _tok_stack.emplace(0, ValueType {{}});
    }}

    ValueType& value() {{ return _tok_stack.top().second; }}

    TokenValue read()
    {{
        while (true) {{
            if (_tok_leave_flag) {{
                _tok_leave_flag = false;

                auto& val = _tok_stack.top();
                auto tv = capture(val.first, val.second);

                _tok_stack.pop();
                assert(_tok_stack.size() > 0);

                if (not tv.first) {{ // not discard
                    return std::move(tv.second);
                }}
            }}

            auto tv = this->read_one();
            if (not tv.first) {{ // not discard
                return std::move(tv.second);
            }}
        }}
    }}

    Location& location() {{ return _tok_location; }}

    void step(int n = 1) {{ _tok_location.step(n); }}

    void lines(int n = 1) {{ _tok_location.lines(n); }}

    void leave()
    {{
        this->yy_pop_state();
        _tok_leave_flag = true;
    }}

    void enter(int ctx_id, ValueType&& value)
    {{
        _tok_stack.emplace(ctx_id, std::move(value));
        this->yy_push_state(ctx_id);
    }}

    void enter(int ctx_id)
    {{
        _tok_stack.emplace(ctx_id, ValueType {{}});
        this->yy_push_state(ctx_id);
    }}

protected:
    std::stack<std::pair<int, ValueType>> _tok_stack {{}};
    bool _tok_leave_flag {{ false }};
    Location _tok_location;

    std::pair<bool, TokenValue> read_one();

    std::pair<bool, TokenValue> capture(int ctx, ValueType& val) {{
{chr(10).join(captures)}
        return {{true, TokenValue{{}}}};
    }}
}};
"""
    p + f'}} // namespace {args.namespace}'
    p + '#endif'


def _generate_flex(cls, args):
    scan_info = cls.__scanners__  # type: dict
    p = Printer(args.flex)
    p + '''/* Copyright (C) 2023 pom@vro.life */
/* SPDX-License-Identifier: MIT OR LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only */'''
    p + '/* generated code */'
    p + f"""
%{{
#include "playlang/playlang.hpp"
#include "{args.namespace}_tokenizer.hpp"

using namespace playlang;

#undef YY_DECL
#define YY_DECL std::pair<bool, {args.namespace}::TokenValue> {args.namespace}::Tokenizer::read_one()
#define YY_USER_ACTION  this->step(yyleng);

int {args.namespace}FlexLexer::yylex() {{ abort(); }}
%}}

%option c++ noyywrap prefix="{args.namespace}"
"""
    all_conditions = []
    patterns = []
    for condition, scanner in scan_info.items():
        if condition != '__default__':
            p + f'%x CONDITION_{condition}'
            all_conditions.append(condition)

        for token in scanner.tokens:
            pattern, discard, fullname = map(
                token.data.get, ('pattern', 'discard', 'fullname'))
            if fullname in patterns:
                continue
            patterns.append(fullname)
            if token.capture:
                continue
            if token.is_eof:
                continue
            if pattern is None:
                raise TypeError(f'token missing action: {token}')
            pattern = pattern.replace(r'"', r'\"')
            p + f'{fullname} {pattern}'
        p + ''

    p + f"""
%%
%{{
    this->step ();
%}}
"""
    for condition, scanner in scan_info.items():
        group = ''
        if condition != '__default__':
            group = f'<CONDITION_{condition}>'
        for token in scanner.tokens:
            if token.capture:
                continue
            pattern, discard, fullname, trailing = map(
                token.data.get, ('pattern', 'discard', 'fullname', 'trailing'))
            code = f'return {{ {str(bool(discard)).lower()}, {args.namespace}::TokenValue{{this->location(), VariantValueType{{{token.name}{{*this}}}}, TID_{fullname}}} }};'
            if token.is_eof:
                if condition == '__default__':
                    pattern_name = '<INITIAL><<EOF>>'
                else:
                    pattern_name = '<<EOF>>'
            else:
                pattern_name = f'{{{fullname}}}'
                if trailing is not None:
                    pattern_name += '/'+trailing
            p + f'{group}{pattern_name}\t {{{code}}}'

    p + "%%"

    for c in all_conditions:
        p + f'const int {args.namespace}::Tokenizer::{c} = CONDITION_{c};'

def _generate_parser(cls, args):
    p = Printer(args.parser)
    p + '''// Copyright (C) 2023 pom@vro.life
// SPDX-License-Identifier: MIT OR LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only'''
    p + '// generated code'
    p + f'#ifndef __{args.namespace}_parser_hpp__'
    p + f'#define __{args.namespace}_parser_hpp__'
    p + f'#include "{args.namespace}_tokenizer.hpp"'
    p + ''
    p + f'namespace {args.namespace} {{'

    state_list = list(cls.__state_list__)
    state_list.sort(key=lambda s: str(s.bind_rule) + str(s.bind_index))

    states_ids = {}
    for idx, state in enumerate(state_list):
        states_ids[state] = idx

    p < """
template<typename Context>
class Parser {
public:
"""
    p < f'typename __START__::ResultType parse(Context& ctx, Tokenizer& tokenizer) {{'
    p + 'typedef Tokenizer::ValueType ValueType;'
    p + 'typedef Tokenizer::TokenValueType TokenValueType;'
    p + f'std::stack<int> state_stack{{}};'
    p + f'state_stack.push({states_ids[cls.__state_tree__]});'
    p + f'playlang::TokenReader<Tokenizer> token_reader{{tokenizer}};'  # nopep8
    p + 'TokenValueType* lookahead = token_reader.peek();'

    p < 'while(!token_reader.done()) {'

    p < 'switch(state_stack.top()) {'
    for state in state_list:
        p < f'case {states_ids[state]}:'

        p < 'switch(lookahead->token()) {'

        if len(state.branchs) > 0:
            for ts, st in state.branchs.items():
                p + f'case TID_{ts.fullname}:'
                p << f'state_stack.push({states_ids[st]});'
                p + 'if (lookahead->token() < 20000) { token_reader.read(); }'
                p + 'lookahead = token_reader.peek();'
                p >> 'break;'

        p < 'default:'

        if state.reduce_rule is not None:
            fullname = state.reduce_rule.symbol.fullname
            targs = [
                state.reduce_rule.symbol.name,
                'Context'
            ]
            targs.extend([x.name for x in state.reduce_rule])
            p + f'token_reader.produce<{", ".join(targs)}>(ctx, TID_{fullname});';
            p + f'for(int i = 0 ; i < {len(state.reduce_rule)}; ++i) {{ state_stack.pop(); }}'
            p + 'lookahead = &token_reader.top();'
        else:
            p + 'if (lookahead->token() < 20000 && lookahead->token() > 10000)'
            p < '{'
            p + '// ignorable'
            p + 'token_reader.discard();'
            p + 'lookahead = token_reader.peek();'
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
            # p + 'if (lookahead->_location.valid()) { oss << lookahead->location().to_string() << " => "; }'  # nopep8
            p + f'oss << "unexpected token " << get_token_name(lookahead->token()) << "{message}";'
            p + 'throw playlang::SyntaxError(oss.str());'

        p >> 'break;'
        p > '}'
        p + 'break;'
        p > ''

    p > '}'
    p > '}'  # while
    p + 'return std::move(token_reader.pop().value().as<__START__>().value());'
    p > '}'  # function

    p > '};'
    p > f'}} // namespace {args.namespace}'
    p + '#endif'

def _open_file(fn):
    if fn == "-":
        return sys.stdout
    return open(fn, "w+")

def generate(cls, argv=None): 
    argp = argparse.ArgumentParser()
    argp.add_argument('--namespace', required=True, help='c++ namespace')
    argp.add_argument('--classname', type=str, default='', help='c++ namespace')
    argp.add_argument('--include', required=True, help='A common header file to include in all generated c++ files')
    argp.add_argument('--parser', required=True, help='output file name of parser')
    argp.add_argument('--flex', required=False, help='output file name of flex file. see https://github.com/westes/flex.git')
    argp.add_argument('--tokenizer', required=True, help='output file name of tokenizer')
    argp.add_argument('--statefull-tokenizer', type=str, default='', help='state class name. generated tokenizer will inherit this class')
    argp.add_argument('--custom-tokenizer', type=bool, default=False, help='use custom lexer. we use flex lexer by default')
    args = argp.parse_args(argv)
    
    if len(args.classname) > 0 and args.classname != cls.__name__:
        return

    args.parser = _open_file(args.parser)
    _generate_parser(cls, args)

    if not args.custom_tokenizer:
        args.flex = _open_file(args.flex)
        _generate_flex(cls, args)

    args.tokenizer = _open_file(args.tokenizer)
    _generate_tokenizer(cls, args)

    if args.parser is not sys.stdout:
        args.parser.close()
    if args.flex is not sys.stdout:
        args.flex.close()
    if args.tokenizer is not sys.stdout:
        args.tokenizer.close()

if __name__ == '__main__':
    import pathlib
    path = pathlib.Path(__file__)
    print(path.parent / 'cpp')
