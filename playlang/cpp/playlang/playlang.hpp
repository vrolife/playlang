#ifndef __playlang_playlang_hpp__
#define __playlang_playlang_hpp__

#include <array>
#include <sstream>
#include <stack>
#include <string>
#include <tuple>
#include <utility>

#include "playlang/variant.hpp"

namespace playlang {
namespace detail {

template<size_t... I>
struct seq
{ };

template<size_t... I>
struct make_seq;

template<size_t N, size_t... I>
struct make_seq<N, N-1, I...>
{
   typedef seq<I..., N-1> type;
};

template<size_t... I>
struct make_seq<0, 0, I...>
{
   typedef seq<I...> type;
};

template<size_t N, size_t I0, size_t... I>
struct make_seq<N, I0, I...> : make_seq<N, I0 + 1, I..., I0>
{ };

template<typename T, typename Context, typename Tuple, typename Array, size_t... Index>
typename std::enable_if<not T::Contextful, T>::
type build_with_args(Context& ctx, Array&& a, seq<Index...>)
{
    return T{a[Index].template as<typename std::tuple_element<Index,Tuple>::type>()...};
}

template<typename T, typename Context, typename Tuple, typename Array, size_t... Index>
typename std::enable_if<T::Contextful, T>::
type build_with_args(Context& ctx, Array&& a, seq<Index...>)
{
    return T{ctx, a[Index].template as<typename std::tuple_element<Index,Tuple>::type>()...};
}

template<typename T, typename Context, typename Tuple, typename Array>
T build(Context& ctx, Array&& a) {
   constexpr static size_t N = std::tuple_size<typename std::decay<Array>::type>::value;
   return build_with_args<T, Context, Tuple>(
       ctx,
       std::forward<Array>(a), 
       typename make_seq<N, 0>::type{});
}

} // namespace detail

struct Location {
    int _line_number;
    int _column;

    explicit Location(int line_number = 0, int column = 0)
        : _line_number(line_number)
        , _column(column)
    {
    }

    ~Location() = default;

    Location(const Location&) = default;
    Location& operator=(const Location&) = default;
    Location(Location&&) noexcept = default;
    Location& operator=(Location&&) noexcept = default;

    void lines(int n)
    {
        this->_line_number += n;
        this->_column = 0;
    }

    void step() { this->_column += 1; }

    void step(int n) { this->_column += n; }
};

template <typename T, bool Context = false>
class Token {
    T _value {};

public:
    constexpr static bool Contextful = Context;
    typedef T ValueType;

    explicit Token(T&& val)
        : _value(std::move(val))
    {
    }

    explicit Token(const T& val)
        : _value(val)
    {
    }

    operator T&() { return _value; }
    operator const T&() const { return _value; }

    template <typename V>
    void value(V&& value)
    {
        _value = std::forward<V>(value);
    }
    T& value() { return _value; }
    const T& value() const { return _value; }
    T release()
    {
        auto tmp = std::move(_value);
        return std::move(tmp);
    }
};

template <bool Context>
class Token<void, Context> {
public:
    constexpr static bool Contextful = Context;
    typedef void ValueType;
};

template <typename T, bool Context = false>
using Symbol = Token<T, Context>;

template <typename Tokenizer>
class TokenReader {
    typedef typename Tokenizer::TokenValueType TokenValueType;
    typedef typename Tokenizer::ValueType ValueType;

    Tokenizer& _tokenizer;

    std::stack<TokenValueType> _stack {};
    TokenValueType _next_token {};

    TokenValueType _read() { return _tokenizer.read(); }

public:
    explicit TokenReader(Tokenizer& tokenizer)
        : _tokenizer(tokenizer)
    {
    }

    bool done()
    {
        return _stack.size() == 1 and _stack.top().token() == Tokenizer::TokenID_START;
    }

    TokenValueType& top() { return _stack.top(); }

    TokenValueType* peek()
    {
        if (_next_token.empty()) {
            _next_token = this->_read();
        }
        return &_next_token;
    }

    void discard() { _next_token = {}; }

    void read()
    {
        auto t = std::move(_next_token);
        if (t.empty()) {
            t = _read();
        }
        _stack.emplace(std::move(t));
    }

    template <typename V>
    void consume(size_t n, V& output)
    {
        if (n == 0) {
            return;
        }
        while (n) {
            output.emplace_back(std::move(_stack.top()));
            _stack.pop();
        }
    }

    void commit(TokenValueType&& tv) { _stack.emplace(std::move(tv)); }

    TokenValueType pop()
    {
        auto tv = std::move(_stack.top());
        _stack.pop();
        return std::move(tv);
    }

    void push(TokenValueType&& tv) { _stack.emplace(std::move(tv)); }

    template <typename T, typename Context, typename... C>
    void produce(Context& ctx, int token)
    {
        constexpr static size_t N = sizeof...(C);
        std::array<ValueType, N> args {};
        for (size_t i = 0; i < N; ++i) {
            args[N - i - 1] = std::move(pop().value());
        }
        typedef std::tuple<C...> Tuple;
        push({ _tokenizer.location(),
            ValueType { detail::build<T, Context, Tuple>(ctx, args) }, token });
    }
};

template <typename T>
class TokenValue {
public:
    typedef T ValueType;

private:
    Location _location {};
    ValueType _value {};
    int _token {};

public:
    TokenValue() = default;
    ~TokenValue() = default;
    TokenValue(const Location& loc, ValueType&& value, int token)
        : _location(loc)
        , _value(std::move(value))
        , _token(token)
    {
    }

    TokenValue(const TokenValue&) = default;
    TokenValue(TokenValue&&) noexcept = default;
    TokenValue& operator=(const TokenValue&) = default;
    TokenValue& operator=(TokenValue&&) noexcept = default;

    bool valid() { return not _value.empty(); }

    bool empty() { return _value.empty(); }

    ValueType& value() { return _value; }
    const Location& location() const { return _location; }
    int token() const { return _token; }
};

class PlaylangError : public std::logic_error {
public:
    using std::logic_error::logic_error;
};

class MismatchError : public PlaylangError {
public:
    using PlaylangError::PlaylangError;
};

class SyntaxError : public PlaylangError {
public:
    using PlaylangError::PlaylangError;
};

} // namespace playlang

#endif
