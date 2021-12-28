import os
import sys
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
        with open(os.path.join(folder, 'parser.mjs'), 'w') as f:
            JavaScript.generate(compiler, f)
        with open(os.path.join(folder, 'tests.mjs'), 'w') as f:
            f.write(source)
        return 0

    with tempfile.TemporaryDirectory() as folder:
        with open(os.path.join(folder, 'parser.mjs'), 'w') as f:
            JavaScript.generate(compiler, f)
        with open(os.path.join(folder, 'tests.mjs'), 'w') as f:
            f.write(source)

        return os.system(f'cd "{folder}" && node tests.mjs')


class TestJavaScript(unittest.TestCase):
    def test_calc(self):
        status = test(ParserCalc, """
        import { scan, parse } from './parser.mjs'

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
                throw Error(`Assertion failed: \`${code}\` => ${value} != ${other}`)
            }
        }

        try {
            parse(scan('1x'), context)
        } catch(e) {
            assert(`"${e.message}"`, '<memory>0:0 => unexpected token Name(x), expecting one of [End-Of-File PLUS MINUS TIMES DIVIDE]')
        }

        assert(`parse(scan('y="123"'), context)`, '123')
        assert(`parse(scan('a=b=3'), context)`, 3)
        assert(`parse(scan('2+3+4'), context)`, 9)
        assert(`parse(scan('2+3*4'), context)`, 14)
        assert(`parse(scan('2+(3+4)'), context)`, 9)
        assert(`parse(scan('-2*3'), context)`, -6)
        assert(`parse(scan('x=1+2*-3'), context)`, -5)
        assert(`parse(scan('2+3 *4+5'), context)`, 19)
        assert(`parse(scan('x*4'), context)`, 12)
        """)
        self.assertTrue(status == 0)

    def test_list_template(self):
        status = test(ParserListWithTemplate, """
        import { scan, parse } from './parser.mjs'

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
        for (const v of parse(scan('1${.hello}2')) ) {
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

