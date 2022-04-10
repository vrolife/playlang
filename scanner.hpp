#ifndef __scanner_hpp__
#define __scanner_hpp__

namespace PLAYLANG_PARSER_NAMESPACE {

struct Location {
    int _line_number;
    int _column;

    Location() : _line_number(0), _column(0) { }
    Location(const Location&) = default;

    void lines(int n) {
        this->_line_number += n;
        this->_column = 0;
    }

    void step() {
        this->_column += 1;
    }
};

class ScannerContext
{
    std::string _name;
    std::regex _regexp;
    Location _location;
    std::string _text;

public:
    ScannerContext(const std::string& name, )
    std::string& text() {
        return _text;
    }

    void step() {
        _location.step(_text.size());
    }

    void step(int n) {
        _location.step(n);
    }

    void lines(int n) {
        _location.lines(n);
    }
};

}

#endif
