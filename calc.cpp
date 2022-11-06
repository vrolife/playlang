#include <cassert>
#include <sstream>

#ifdef PLAYLANG_LEXER_FLEX
#include "calc_parser.hpp"
#include "calc_typedef.hpp"
#endif

using namespace calc;

static ParserContext ctx{};

int exec(const std::string& expr)
{
    std::istringstream ss{expr};
    Tokenizer tokenizer{"memory", ss, std::cout};
    Parser<ParserContext> parser{};
    return parser.parse(ctx, tokenizer);
}

int main(int argc, const char* argv[])
{
    assert(exec("y=\"okok123\"") == 123);
    assert(exec("a=b=3") == 3);
    assert(exec("2+3+4") == 9);
    assert(exec("2+3*4") == 14);
    assert(exec("2+(3+4)") == 9);
    assert(exec("-2*3") == -6);
    assert(exec("x=1+2*-3") == -5);
    assert(exec("2+3 *4+5") == 19);
    assert(exec("x*4") == -20);
    return 0;
}
