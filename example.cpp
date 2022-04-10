
class MyTokenizer : CalcScanner
{
public:
    long NUMBER(ScannerContext& ctx) {
        return std::stol(ctx.text());
    }
};

typedef CalcScanner<MyTokenizer> Tokenizer;

class MyParser
{
public:
    long EXPR(long number, const std::string& plus, long number)
    {
        return number + number;
    }

    void parse_string(const std::string& content) {
        Tokenizer tokenizer{};
        parse(tokenizer);
    }
};

typedef CalcParser<MyParser> Parser;

int main()
{
    Parser parser{};
    parser.parse_string("1+1");
}
