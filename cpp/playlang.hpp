#ifndef __playlang_hpp__
#define __playlang_hpp__

#include <utility>
#include <tuple>
#include <array>
#include <stack>
#include <string>
#include <sstream>

#ifndef yyFlexLexerOnce
#include <FlexLexer.h>
#endif

namespace playlang {
    
namespace detail {

template<typename T, typename... Types>
struct union_size
{
    constexpr static size_t size = (sizeof(T) > union_size<Types...>::size) ? sizeof(T) : union_size<Types...>::size;
};

template<typename T>
struct union_size<T>
{
    constexpr static size_t size = sizeof(T);
};

template<typename T1, int Index, typename T2, typename... Types>
struct union_index
{
   constexpr static int index = std::is_same<T1, T2>::value ? Index : union_index<T1, Index + 1, Types...>::index;
};

template<typename T1, int Index, typename T2>
struct union_index<T1, Index, T2>
{
   constexpr static int index = std::is_same<T1, T2>::value ? Index : -1;
};

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

}

template<typename... Types>
class alignas(8) Variant
{
   char _memory[detail::union_size<Types...>::size]{};
   int _type{-1};

   template<typename T, typename... TS>
   void _free() {
      auto t = detail::union_index<T, 0, Types...>::index;
      if (t == _type) {
         reinterpret_cast<T*>(&_memory[0])->~T();
         return;
      }
      return _free<TS...>();
   }

   template<typename... TS>
   typename std::enable_if<sizeof...(TS) == 0>::
   type _free() { }

   template<typename T, typename... TS>
   void _copy(const Variant& other) {
      auto t = detail::union_index<T, 0, Types...>::index;
      if (t == other._type) {
         new(_memory)T(*reinterpret_cast<T*>(&other._memory[0]));
         _type = other._type;
         return;
      }
      return _copy<TS...>(other);
   }

   template<typename... TS>
   typename std::enable_if<sizeof...(TS) == 0>::
   type _copy(const Variant& other) { }

   template<typename T, typename... TS>
   void _move(Variant&& other) {
      auto t = detail::union_index<T, 0, Types...>::index;
      if (t == other._type) {
         new(_memory)T(std::move(*reinterpret_cast<T*>(&other._memory[0])));
         _type = other._type;
         other._type = -1;
         return;
      }
      return _move<TS...>(std::move(other));
   }

   template<typename... TS>
   typename std::enable_if<sizeof...(TS) == 0>::
   type _move(Variant&& other) { }

   template<typename T, typename... TS>
   bool _eq(const Variant& other) {
      auto t = detail::union_index<T, 0, Types...>::index;
      if (t == other._type) {
         return this->as<T>() == other.as<T>();
      }
      return _eq<TS...>(other);
   }

   template<typename... TS>
   typename std::enable_if<sizeof...(TS) == 0, bool>::
   type _eq(const Variant& other) { return false; }

public:
   Variant() = default;

   template<typename T>
   explicit Variant(T&& value) {
     emplace<T>(std::forward<T>(value));
   }

   Variant(const Variant& other) {
      if (other.empty()) {
         _type = -1;
         return;
      }
      _copy<Types...>(other);
   }

   Variant(Variant&& other)  noexcept {
      if (other.empty()) {
         _type = -1;
         return;
      }
      _move<Types...>(std::move(other));
   }

   ~Variant() { reset(); }

   Variant& operator =(const Variant& other) {
      reset();
      if (not other.empty()) {
         _copy<Types...>(other);
      }
      return *this;
   }

   Variant& operator =(Variant&& other)  noexcept {
      reset();
      if (not other.empty()) {
         _move<Types...>(std::move(other));
      }
      return *this;
   }

   bool operator ==(const Variant& other) {
      return _type == other._type and (_type == -1 or _eq<Types...>(other));
   }

   bool operator !=(const Variant& other) {
      return !(*this == other);
   }

   template<typename T, typename... Args>
   T& emplace(Args&&... args) {
      auto t = detail::union_index<T, 0, Types...>::index;
      if (t == -1) {
         throw std::bad_cast();
      }
      this->reset();
      _type = t;
      new(_memory)T(std::forward<Args>(args)...);
      return *reinterpret_cast<T*>(&_memory[0]);
   }

   void reset() {
      if (_type != -1) {
         _free<Types...>();
         _type = -1;
      }
   }

    bool empty() const {
        return _type == -1;
    }

   template<typename T>
   T& as() {
      auto t = detail::union_index<T, 0, Types...>::index;
      if (t != _type) {
         throw std::bad_cast();
      }
      return *reinterpret_cast<T*>(&_memory[0]);
   }

   template<typename T>
   const T& as() const {
      auto t = detail::union_index<T, 0, Types...>::index;
      if (t != _type) {
         throw std::bad_cast();
      }
      return *reinterpret_cast<const T*>(&_memory[0]);
   }
};

struct Location {
    int _line_number;
    int _column;

    explicit Location(int line_number = 0, int column = 0)
    : _line_number(line_number), _column(column)
    { }

    ~Location() = default;

    Location(const Location&) = default;
    Location& operator =(const Location&) = default;
    Location(Location&&) noexcept = default;
    Location& operator =(Location&&) noexcept = default;

    void lines(int n) {
        this->_line_number += n;
        this->_column = 0;
    }

    void step() {
        this->_column += 1;
    }

    void step(int n) {
        this->_column += n;
    }
};

template<typename T, bool Context=false>
class Token {
    T _value{};
public:
    constexpr static bool Contextful = Context;
    typedef T ValueType;
    explicit Token(T&& val):_value(std::move(val)) { }
    explicit Token(const T& val):_value(val) { }

    operator T&() { return _value; }
    operator const T&() const { return _value; }

    template<typename V>
    void value(V&& value) {
        _value = std::forward<V>(value);
    }
    T& value() { return _value; }
    const T& value() const { return _value; }
    T release() {
        auto tmp = std::move(_value);
        return std::move(tmp);
    }
};

template<bool Context>
class Token<void, Context> {
public:
    constexpr static bool Contextful = Context;
    typedef void ValueType;
};

template<typename T, bool Context=false>
using Symbol = Token<T, Context>;

template<typename Tokenizer>
class TokenReader
{
    typedef typename Tokenizer::TokenValueType TokenValueType;
    typedef typename Tokenizer::ValueType ValueType;

    Tokenizer& _tokenizer;

    std::stack<TokenValueType> _stack{};
    TokenValueType _next_token{};

    TokenValueType _read() {
        return _tokenizer.read();
    }

public:
    explicit TokenReader(Tokenizer& tokenizer)
    : _tokenizer(tokenizer)
    {
        
    }

    bool done() {
        return _stack.size() == 1 and _stack.top().token() == Tokenizer::TokenID_START;
    }
    
    TokenValueType& top() { return _stack.top(); }

    TokenValueType* peek() {
        if (_next_token.empty()) {
            _next_token = this->_read();
        }
        return &_next_token;
    }

    void discard() {
        _next_token = {};
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

    void commit(TokenValueType&& tv) {
        _stack.emplace(std::move(tv));
    }

    TokenValueType pop() {
        auto tv = std::move(_stack.top());
        _stack.pop();
        return std::move(tv);
    }

    void push(TokenValueType&& tv) {
        _stack.emplace(std::move(tv));
    }

    template<typename T, typename Context, typename... C>
    void produce(Context& ctx, int token) {
        constexpr static size_t N = sizeof...(C);
        std::array<ValueType, N> args{};
        for (size_t i = 0 ; i < N; ++i) {
            args[N - i -1] = std::move(pop().value());
        }
        typedef std::tuple<C...> Tuple;
        push({_tokenizer.location(), ValueType{detail::build<T, Context, Tuple>(ctx, args)}, token});
    }
};

template<typename TokenValue>
class TokenizerBase : protected yyFlexLexer
{
public:
    typedef TokenValue TokenValueType;
    typedef typename TokenValue::ValueType ValueType;

    TokenizerBase(const std::string& filename, std::istream& in, std::ostream& out)
    : yyFlexLexer(in, out), _tok_filename(filename) { init(); }

    explicit TokenizerBase(const std::string& filename, std::istream* in = 0, std::ostream* out = 0)
    : yyFlexLexer(in, out), _tok_filename(filename) { init(); }

    Location& location() {
        return _tok_location;
    }

    void step(int n = 1) {
        _tok_location.step(n);
    }

    void lines(int n = 1) {
        _tok_location.lines(n);
    }

    void leave() {
        this->yy_pop_state();
        _tok_leave_flag = true;
    }

    void enter(int ctx_id, ValueType&& value) 
    {
        _tok_stack.emplace(ctx_id, std::move(value));
        this->yy_push_state(ctx_id);
    }

    void enter(int ctx_id) 
    {
        _tok_stack.emplace(ctx_id, ValueType{});
        this->yy_push_state(ctx_id);
    }

    const char* text() const { return YYText(); }
    size_t text_length() const { return YYLeng(); }

    operator std::string() const {
        return {text(), text_length()};
    }

    TokenValue read() {
        while (true) {
            if (_tok_leave_flag) {
                _tok_leave_flag = false;
                
                auto& val = _tok_stack.top();
                auto tv = capture(val.first, val.second);

                _tok_stack.pop();
                assert(_tok_stack.size() > 0);

                if (not tv.first) { // not discard
                    return std::move(tv.second);
                }
            }

            auto tv = read_one();
            if (not tv.first) { // not discard
                return std::move(tv.second);
            }
        }
    }

    ValueType& value() {
        return _tok_stack.top().second;
    }

protected:
    std::stack<std::pair<int, ValueType>> _tok_stack{};
    bool _tok_leave_flag{false};
    std::string _tok_filename{};
    Location _tok_location;

    void init() {
        _tok_stack.emplace(0, ValueType{});
    }
    virtual std::pair<bool, TokenValue> read_one() = 0;
    virtual std::pair<bool, TokenValue> capture(int ctx, ValueType&) = 0;
};

template<typename T>
class TokenValue {
public:
    typedef T ValueType;

private:
    Location _location{};
    ValueType _value{};
    int _token{};

public:
    TokenValue() = default;
    ~TokenValue() = default;
    TokenValue(const Location& loc, ValueType&& value, int token)
    : _location(loc), _value(std::move(value)), _token(token)
    { }

    TokenValue(const TokenValue&) = default;
    TokenValue(TokenValue&&) noexcept = default;
    TokenValue& operator =(const TokenValue&) = default;
    TokenValue& operator =(TokenValue&&) noexcept = default;

    bool valid() {
        return not _value.empty();
    }

    bool empty() {
        return _value.empty();
    }
    
    ValueType& value() { return _value; }
    const Location& location() const { return _location; }
    int token() const { return _token; }
};

class PlaylangError : public std::logic_error
{
public:
    using std::logic_error::logic_error;
};

class MismatchError : public PlaylangError
{
public:
    using PlaylangError::PlaylangError;
};

class SyntaxError : public PlaylangError
{
public:
    using PlaylangError::PlaylangError;
};

} // playlang

#endif
