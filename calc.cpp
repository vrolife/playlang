#include <cassert>
#include <sstream>

#include "calc_parser.hpp"
#include "calc_typedef.hpp"

using namespace calc;

int main(int argc, const char* argv[])
{
    std::istringstream ss{"3*(1+1)"};
    assert(not ss.eof());

    Tokenizer tokenizer{"memory", ss, std::cout};
    Parser parser{};
    auto val = parser.parse(tokenizer);
    std::cout << val << std::endl;
}
