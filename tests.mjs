import { scan, parse } from './parser.mjs'

const context = {
    x: 3,
    expr_number(num) {
        return Number(num)
    },
    expr_name(name) {
        return this[name]
    },
    expr_expr_opr_expr(expr1, opr, expr2) {
        return eval(`${expr1}${opr}${expr2}`)
    },
    expr_name_eq_expr(name, opr, expr) {
        return expr
    },
    expr_lpar_expr_rpar(l, expr, r) {
        return expr
    },
    expr_minus_expr(_, expr) {
        return -expr
    }
}

function assert(code) {
    if (!eval(code)) {
        throw Error(`Assertion failed: ${code}`)
    }
}

assert(`parse(scan('a=b=3'), context) == 3`)
assert(`parse(scan('2+3+4'), context) == 9`)
assert(`parse(scan('2+3*4'), context) == 14`)
assert(`parse(scan('2+(3+4)'), context) == 9`)
assert(`parse(scan('-2*3'), context) == -6`)
assert(`parse(scan('x=1+2*-3'), context) == -5`)
assert(`parse(scan('2+3 *4+5'), context) == 19`)
assert(`parse(scan('x*4'), context) == 12`)
