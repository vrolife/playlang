import os
import tempfile
import shutil
import unittest
from playlang.javascript import JavaScript
from test_py import ParserCalc, ParserListWithTemplate


def test(cls, source):
    compiler = cls()

    export_dir = os.getenv('EXPORT_DIR')

    if export_dir is not None:
        folder = os.path.join(export_dir, cls.__name__)
        os.makedirs(folder, exist_ok=True)

        shutil.copy('playlang.js', folder)

        with open(os.path.join(folder, 'parser.js'), 'w') as f:
            JavaScript.generate(compiler, f, cls.__name__.lower() + '_')
            
        
        with open(os.path.join(folder, 'tests.js'), 'w') as f:
            f.write(source)
            
        with open(os.path.join(folder, 'package.json'), 'w') as f:
            f.write('{"type":"module"}')

        return 0

    with tempfile.TemporaryDirectory() as folder:
        shutil.copy('playlang.js', folder)

        with open(os.path.join(folder, 'parser.js'), 'w') as f:
            JavaScript.generate(compiler, f, cls.__name__.lower() + '_')

        with open(os.path.join(folder, 'tests.js'), 'w') as f:
            f.write(source)

        with open(os.path.join(folder, 'package.json'), 'w') as f:
            f.write('{"type":"module"}')

        return os.system(f'cd "{folder}" && node --experimental-vm-modules tests.js')


class TestJavaScript(unittest.TestCase):
    def test_calc(self):
        status = test(ParserCalc, """
import { parsercalc_scan, parsercalc_parse } from './parser.js'

const context = {
    x: 3,
    expr_name(name) {
        return this[name]
    },
    expr_expr_opr_expr(expr1, opr, expr2) {
        return eval(`${expr1}${opr}${expr2}`)
    },
    expr_name_eq_expr(name, eq, expr) {
        return expr
    },
    expr_minus_expr(_, expr) {
        return -expr
    }
}

function assert(code, other) {
    const value = eval(code)
    if (value !== other) {
        throw Error(`Assertion failed: \\`${code}\\` => ${value} != ${other}`)
    }
}

try {
    parsercalc_parse(parsercalc_scan('1x'), context)
} catch(e) {
    assert(`"${e.message}"`, '<memory>0:0 => unexpected token Name(x), expecting one of [End-Of-File PLUS MINUS TIMES DIVIDE]')
}

assert(`parsercalc_parse(parsercalc_scan('y="123"'), context)`, '123')
assert(`parsercalc_parse(parsercalc_scan('a=b=3'), context)`, 3)
assert(`parsercalc_parse(parsercalc_scan('2+3+4'), context)`, 9)
assert(`parsercalc_parse(parsercalc_scan('2+3*4'), context)`, 14)
assert(`parsercalc_parse(parsercalc_scan('2+(3+4)'), context)`, 9)
assert(`parsercalc_parse(parsercalc_scan('-2*3'), context)`, -6)
assert(`parsercalc_parse(parsercalc_scan('x=1+2*-3'), context)`, -5)
assert(`parsercalc_parse(parsercalc_scan('2+3 *4+5'), context)`, 19)
assert(`parsercalc_parse(parsercalc_scan('x*4'), context)`, 12)
""")
        self.assertTrue(status == 0)

    def test_list_template(self):
        status = test(ParserListWithTemplate, """
import { parserlistwithtemplate_scan, parserlistwithtemplate_parse } from './parser.js'

class TestContext {
    constructor(instances) {
        this._instances = instances
    }
    get_prev_instance() {
        return this._instances['prev']
    }

    get_instance(name) {
        return this._instances[name]
    }
}

const ctx = new TestContext({
    prev: {
        hello: 'world!'
    }
})

const lst = []
for (const v of parserlistwithtemplate_parse(parserlistwithtemplate_scan('1${.hello}2')) ) {
    if (typeof v === 'function') {
        lst.push(v(ctx))
    } else {
        lst.push(v)
    }
}

if (lst.join('') !== '1world!2') {
    throw new Error(lst)
}

""")
        self.assertTrue(status == 0)
