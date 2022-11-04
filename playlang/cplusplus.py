# pylint: disable=pointless-statement,expression-not-assigned,line-too-long

import re
import sys
import io
import argparse
from playlang.classes import SymbolInfo, TokenInfo, Symbol
from playlang.printer import Printer


def _generate_typedef(cls, args):
    scan_info = cls.__scanners__  # type: dict
    p = Printer(args.typedef)
    p + '// generated code'
    p + f'#ifndef __{args.namespace}_typedef_hpp__'
    p + f'#define __{args.namespace}_typedef_hpp__'
    p + f'#include "playlang.hpp"'
    p + f'#include "{args.include}"'
    p + f'\nnamespace {args.namespace} {{\n'

    show_name = {}

    # generate ids

    next_tid = 1

    p + f'#define TID___EOF__ {next_tid}'  # nopep8
    show_name[next_tid] = cls.__eof_token__.show_name
    next_tid += 1

    captures = []

    all_contexts = list()
    all_tokens = set()
    for context, tokens in scan_info.items():
        if context != '__default__':
            all_contexts.append(f"    static const int {context};\n")

        for token in tokens:
            discard, fullname = map(
                token.data.get, ('discard', 'fullname'))
            all_tokens.add(token)
            if token.capture:
                captures.append(f'        if ({context} == ctx) {{ return {{ {str(discard).lower()}, TokenValue{{ this->location(), std::move(val), TID_{fullname} }} }}; }}')

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
    types.append('__EOF__')
    type_lines = [f'\n/* {i} */ \t{n}' for i,n in enumerate(types)]

    p + f"""
struct __EOF__ : public playlang::Token<void> {{
    template<typename C>
    explicit __EOF__(C& ctx) {{}};
    __EOF__() = default;
}};

struct __START__ : public playlang::Symbol<typename {cls.__start_symbol__.name}::ValueType> {{
    typedef typename {cls.__start_symbol__.name}::ValueType ResultType;
    __START__({cls.__start_symbol__.name}& s, __EOF__& _) 
    : playlang::Symbol<typename {cls.__start_symbol__.name}::ValueType>(std::move(s.value()))
    {{ }}
}};

typedef playlang::Variant<{", ".join(type_lines)}
> VariantValueType;
typedef playlang::TokenValue<VariantValueType> TokenValue;

class Tokenizer : public playlang::TokenizerBase<TokenValue>
{f', public {args.statefull_tokenizer}' if args.statefull_tokenizer else ''}
{{
    friend class playlang::TokenReader<Tokenizer>;
public:
    typedef TokenValue TokenValueType;
    typedef typename TokenValue::ValueType ValueType;

    constexpr static int TokenID_EOF = TID___EOF__;
    constexpr static int TokenID_START = TID___START__;
    typedef struct __EOF__ EOF_Type;
    typedef struct __START__ START_Type;

{"".join(all_contexts)}
    using playlang::TokenizerBase<TokenValue>::TokenizerBase;

protected:
    std::pair<bool, TokenValue> read_one() override;

    std::pair<bool, TokenValue> capture(int ctx, ValueType& val) override {{
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
    p + '/* generated code */'
    p + f"""
%{{
#include "playlang.hpp"
#include "{args.namespace}_typedef.hpp"

using namespace playlang;

#undef YY_DECL
#define YY_DECL std::pair<bool, {args.namespace}::TokenValue> {args.namespace}::Tokenizer::read_one()
#define YY_USER_ACTION  this->step(yyleng);
%}}

%option c++ noyywrap
"""
    all_contexts = []
    patterns = []
    for context, tokens in scan_info.items():
        if context != '__default__':
            p + f'%x CONTEXT_ID_{context}'
            all_contexts.append(context)

        for token in tokens:
            pattern, discard, fullname = map(
                token.data.get, ('pattern', 'discard', 'fullname'))
            if fullname in patterns:
                continue
            patterns.append(fullname)
            if token.capture:
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
    for context, tokens in scan_info.items():
        group = ''
        if context != '__default__':
            group = f'<CONTEXT_ID_{context}>'
        for token in tokens:
            if token.capture:
                continue
            pattern, discard, fullname = map(
                token.data.get, ('pattern', 'discard', 'fullname'))
            code = f'return {{ {str(discard).lower()}, {args.namespace}::TokenValue{{this->location(), VariantValueType{{{token.name}{{*this}}}}, TID_{fullname}}} }};'
            p + f'{group}{{{fullname}}}\t {code}'
    p + f'<<EOF>> return {{ false, {args.namespace}::TokenValue{{this->location(), VariantValueType{{ __EOF__{{*this}} }}, TID___EOF__}} }};'

    p + "%%"

    for c in all_contexts:
        p + f'const int {args.namespace}::Tokenizer::{c} = CONTEXT_ID_{c};'

def _generate_parser(cls, args):
    p = Printer(args.parser)
    p + '// generated code'
    p + f'#ifndef __{args.namespace}_parser_hpp__'
    p + f'#define __{args.namespace}_parser_hpp__'
    p + f'#include "playlang.hpp"'
    p + f'#include "{args.namespace}_typedef.hpp"'
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
            p + f'oss << "unexpected token " << lookahead->token() << "{message}";'
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
    argp.add_argument('--include', required=True, help='header to be include in all generated c++ files')
    argp.add_argument('--namespace', required=True, help='c++ namespace')
    argp.add_argument('--parser', required=True, help='output file name for parser')
    argp.add_argument('--flex', required=True, help='output file name for flex. see https://github.com/westes/flex.git')
    argp.add_argument('--typedef', required=True, help='output file name for type definition')
    argp.add_argument('--statefull-tokenizer', type=str, default='', help='class name. generated tokenizer will inherit this class')
    args = argp.parse_args(argv)

    args.parser = _open_file(args.parser)
    args.flex = _open_file(args.flex)
    args.typedef = _open_file(args.typedef)

    _generate_parser(cls, args)
    _generate_flex(cls, args)
    _generate_typedef(cls, args)

    if args.parser is not sys.stdout:
        args.parser.close()
    if args.flex is not sys.stdout:
        args.flex.close()
    if args.typedef is not sys.stdout:
        args.typedef.close()
