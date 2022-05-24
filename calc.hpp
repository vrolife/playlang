#ifndef __calc_hpp__
#define __calc_hpp__

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
CALC_VOID_TOKEN(QUOTE);
CALC_VOID_TOKEN(STRING_QUOTE);
CALC_VOID_TOKEN(WHITE);

struct NUMBER : public Token<int> {
    NUMBER(const std::string& s) 
    :Token<int>(std::stoi(s)) 
    { 
        
    }
};

struct STRING_CHAR : public Token<char> {
    STRING_CHAR(const std::string& s) 
    :Token<char>(s.at(0)) 
    { }
};

struct STRING_ESCAPE : public Token<char> {
    STRING_ESCAPE(const std::string& s) 
    :Token<char>(s.at(0)) 
    { }
};

struct NAME : public Token<std::string> {
    NAME(const std::string& s)
    :Token<std::string>(s) 
    { }
};

struct STRING : public Token<std::string> {
    STRING(const std::string& s)
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

struct EXPR : public Symbol<int> {
    EXPR(const NUMBER& num):Symbol<int>(num) { };

    template<typename OPR>
    EXPR(EXPR& l, OPR& opr, EXPR& r) : Symbol<int>(opr(l, r)) { };

    EXPR(LPAR& l, EXPR& expr, RPAR& r) : Symbol<int>(expr.value()) { };
    EXPR(MINUS&, EXPR& expr) : Symbol<int>(-expr.value()) { };

    EXPR(NAME& name) : Symbol<int>(0) {
        throw PlaylangError("");
    };

    EXPR(STRING& str) : Symbol<int>(0) {
        throw PlaylangError("");
    };

    EXPR(NAME& name, EQUALS&, EXPR&) : Symbol<int>(0) {
        throw PlaylangError("");
    };
};

}

#endif
