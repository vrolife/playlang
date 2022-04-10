#ifndef __playlang_hpp__
#define __playlang_hpp__

#include <regex>

#include PLAYLANG_PARSER_HEADER

namespace PLAYLANG_PARSER_NAMESPACE {

auto token_NUMBER(ContextScan& ctx) {

}

#define TOKEN_LIST(F) \
    F(NUMBER) \
    F(NAME)

#define TYPE_OF_TOKEN(n) std::result_of<decltype(token_##n)>::type
#define VALUE_UNION_MEMBER(n) TYPE_OF_TOKEN(n) _##n;
#define VALUE_GET_VALUE(n) inline auto get_##n() { return _u._##n; }
#define VALUE_ENUM_MEMBER(n) ValueType##n,
#define VALUE_MOVE_CONSTRUCTOR(n) case ValueType##n: _u._##n = std::move(other._##n);break;
#define VALUE_COPY_CONSTRUCTOR(n) case ValueType##n: _u._##n = other._u._##n;break;
#define VALUE_CONSTRUCTOR(n) Value(TYPE_OF_TOKEN(n)&& val) : _type(ValueType##n) { _u._#n = std::move(val); }

struct Value
{
    enum ValueType {
        ValueTypePlaylangUnknownValue,
        TOKEN_LIST(VALUE_ENUM_MEMBER)
    };
    union {
        int _playlang_unknown_value{0};
        TOKEN_LIST(VALUE_UNION_MEMBER)
    } _u;

    ValueType _type{ValueTypePlaylangUnknownValue};

    Value() = default;
    TOKEN_LIST(VALUE_CONSTRUCTOR)
    Value(Value&& other) {
        _type = other._type;
        switch(_type) {
            TOKEN_LIST(VALUE_COPY_CONSTRUCTOR)
        }
        other._type = ValueTypePlaylangUnknownValue;
    }

    Value(const Value& other) {
        _type = other._type;
        switch(_type) {
            TOKEN_LIST(VALUE_COPY_CONSTRUCTOR)
        }
    }

    Value& operator =(Value&& other) {
        _type = other._type;
        switch(_type) {
            TOKEN_LIST(VALUE_MOVE_CONSTRUCTOR)
        }
        other._type = ValueTypePlaylangUnknownValue;
        return *this;
    }

    Value& operator =(const Value& other) {
        _type = other._type;
        switch(_type) {
            TOKEN_LIST(VALUE_COPY_CONSTRUCTOR)
        }
        return *this;
    }

    bool empty() const { return _type == ValueTypePlaylangUnknownValue; }
};

struct TokenValue {
    int _token{0};
    bool _discard{false};
    Value _value{};

    template<typename V>
    TokenValue(int token, V&& value)
    : _token(token), _value(std::forward<V>(value))
    {

    }

    template<typename V>
    TokenValue(int token, bool discard, V&& value)
    : _token(token), _discard(discard), _value(std::forward<V>(value))
    {

    }

    TokenValue() = default;
    TokenValue(TokenValue&& other) {
        _token = other._token;
        _discard = other._discard;
        _value = std::move(other._value);
        other._token = 0;
        other._discard = false;
    }
    TokenValue(const TokenValue&) = default;
    TokenValue& operator = (TokenValue&&) {
        _token = other._token;
        _discard = other._discard;
        _value = std::move(other._value);
        other._token = 0;
        other._discard = false;
        return *this;
    }
    TokenValue& operator = (const TokenValue&) = default;

    bool empty() const { return _token == 0; }
};

class Tokenizer
{
    std::vector<ContextScan> _stack;
public:

    TokenValue next() {

    }
};

class TokenReader
{
    Tokenizer _tokenizer;
    int _start;
    int _eof;

    std::stack<TokenValue> _stack;
    TokenValue _next_token;

    std::pair<int, Value> _read() {
        auto tmp = _tokenizer++;
        if (tmp->first == _eof) {
            return {_eof, {}};
        }
        return std::move(*tmp);
    }

public:
    TokenReader(Tokenizer&& tokenizer, int start, int eof)
    : _tokenizer(std::move(tokenizer)), _start(start), _eof(eof)
    {
        
    }

    bool done() {
        return _stack.size() == 1 and _stack.back().first == _start;
    }
    
    TokenValue& top() { return _stack.top(); }

    TokenValue& peek() {
        if (_next_token.empty()) {
            _next_token = this._read();
        }
        return _next_token;
    }

    void discard() {
        _next_token = {0, {}};
    }

    void read() {
        auto t = std::move(_next_token);
        if (t.empty()) {
            t = _read();
        }
        _stack.emplace(std::move(t));
    }

    template<typename V>
    void consume(size_t n, V& output) {
        if (n == 0) {
            return;
        }
        while (n) {
            output.emplace_back(std::move(_stack.top()));
            _stack.pop();
        }
    }

    void commit(TokenValue&& tv) {
        _stack.emplace(std::move(tv));
    }

    TokenValue pop() {
        auto tv = std::move(_stack.top());
        _stack.pop();
        return tv;
    }

    void push(TokenValue&& tv) {
        _stack.emplace(std::move(tv));
    }
};

}

#endif
