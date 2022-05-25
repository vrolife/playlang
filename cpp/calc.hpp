#ifndef __calc_hpp__
#define __calc_hpp__

#include <unordered_map>

#include "playlang.hpp"

namespace calc {
using namespace playlang;

#define CALC_VOID_TOKEN(n) \
struct n : public Token<void> { \
    n(const std::string& s) { } \
};

CALC_VOID_TOKEN(EQUALS);
CALC_VOID_TOKEN(LPAR);
CALC_VOID_TOKEN(RPAR);
CALC_VOID_TOKEN(NEWLINE);
CALC_VOID_TOKEN(WHITE);

struct STRING : public Token<std::string> {
    STRING(): Token<std::string>("") { }
};

struct QUOTE : public Token<void, true> {
    template<typename Tokenizer>
    QUOTE(Tokenizer& tok) 
    :Token<void, true>() 
    { 
        tok.enter(Tokenizer::string, typename Tokenizer::ValueType{STRING{}});
    }
};

struct STRING_CHAR : public Token<void, true> {
    template<typename Tokenizer>
    STRING_CHAR(Tokenizer& tok) 
    :Token<void, true>() 
    {
        tok.value().template as<STRING>().value().append(tok.text());
    }
};

struct STRING_ESCAPE : public Token<char> {
    STRING_ESCAPE(const std::string& s) 
    :Token<char>(s.at(0)) 
    { }
};

struct STRING_QUOTE : public Token<void, true> {
    template<typename Tokenizer>
    STRING_QUOTE(Tokenizer& tok) 
    :Token<void, true>() 
    { 
        tok.leave();
    }
};

struct NUMBER : public Token<int> {
    NUMBER(const std::string& s) 
    :Token<int>(std::stoi(s)) 
    { 
        
    }
};

struct NAME : public Token<std::string> {
    NAME(const std::string& s)
    :Token<std::string>(s) 
    { }
};

struct MISMATCH : public Token<void> {
    MISMATCH(const std::string& s) {
        throw playlang::MismatchError(s);
    }
};

struct STRING_MISMATCH : public Token<void> {
    STRING_MISMATCH(const std::string& s) {
        throw playlang::MismatchError(s);
    }
};

struct PLUS : public Token<void> {
    PLUS(const std::string& s) { }
    int operator ()(int l, int r) {
        return l + r;
    }
};

struct MINUS : public Token<void> {
    MINUS(const std::string& s) { }
    int operator ()(int l, int r) {
        return l + r;
    }
};

struct TIMES : public Token<void> {
    TIMES(const std::string& s) { }
    int operator ()(int l, int r) {
        return l * r;
    }
};

struct DIVIDE : public Token<void> {
    DIVIDE(const std::string& s) { }
    int operator ()(int l, int r) {
        return l * r;
    }
};

struct ParserContext
{
    std::unordered_map<std::string, int> _variables{};
};

struct EXPR : public Symbol<int, true> {
    EXPR(ParserContext&, const NUMBER& num):Symbol<int, true>(num) { };

    template<typename OPR>
    EXPR(ParserContext&, EXPR& l, OPR& opr, EXPR& r) : Symbol<int, true>(opr(l, r)) { };

    EXPR(ParserContext&, LPAR& l, EXPR& expr, RPAR& r) : Symbol<int, true>(expr.value()) { };
    EXPR(ParserContext&, MINUS&, EXPR& expr) : Symbol<int, true>(-expr.value()) { };

    EXPR(ParserContext& ctx, NAME& name) : Symbol<int, true>(0) {
        auto iter = ctx._variables.find(name.value());
        if (iter == ctx._variables.end()) {
            throw std::invalid_argument(name.value() + " not found");
        }
        value(iter->second);
    };

    EXPR(ParserContext& ctx, STRING& str) : Symbol<int, true>(0) {
        value(std::stoi(str.value().c_str() + 4)); // skip "okok"
    };

    EXPR(ParserContext& ctx, NAME& name, EQUALS&, EXPR& expr) : Symbol<int, true>(expr.value()) {
        ctx._variables.insert({name, value()});
    };
};

}

#endif
