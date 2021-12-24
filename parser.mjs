// generated code

class TokenReader {
    constructor(tokenizer, start, eof) {
        this._tokenizer = tokenizer
        this._start = start
        this._eof = eof
        this._stack = []
        this._next_token = null
    }
    
    _read() {
        try {
            const {done, value} = this._tokenizer.next()
            if (done) {
                return [this._eof, null]
            }
            return value
        } catch(error) {
            return [this._eof, null]
        }
    }
    
    done() { return this._stack.length == 1 && this._stack[this._stack.length-1][0] === this._start; }
    top() { return this._stack[this._stack.length - 1]; }
    peek() {
        if (this._next_token === null) {
            this._next_token = this._read()
        }
        return this._next_token
    }
    
    discard() { this._next_token = null; }
    
    read() {
        var t = this._next_token
        if (t === null) {
            t = this._read()
        } else {
            this._next_token = null
        }
        this._stack.push(t)
    }
    
    consume(n) {
        if (n == 0) {
            return []
        }
        return this._stack.splice(this._stack.length - n, n)
    }
    
    commit(tv) {
        this._stack.push(tv)
    }
    
    pop() {
        return this._stack.pop()
    }
    
    push(tv) {
        this._stack.push(tv)
    }
}

class Location {
    constructor(filename, line_num, column) {
        this._filename = filename
        this._line_num = line_num
        this._column = column
    }

    lines(n) {
        this._line_num += n
        this._column = 0
        return null
    }

    step(n) {
        this._column += n
        return null
    }

    copy() {
        return new Location(this._line_num, this._column, this._filename)
    }
}

class Context {
    constructor(name, regexp, value, location, enter, leave) {
        this.name = name
        this._regexp = regexp
        this._value = value
        this.text = null
        this._location = location

        this.enter = enter
        this.leave = leave
    }

    get value() {
        return this._value
    }

    get location() {
        return this._location
    }

    step(n) {
        if(n === undefined) {
            location.step(this.text.length)
        } else {
            location.step(n)
        }
    }

    lines(n) {
        this._location.lines(n)
    }
}

const NUMBER = 1
const NAME = 2
const NEWLINE = 3
const WHITE = 4
const MISMATCH = 5
const QUOTE = 6
const STRING_QUOTE = 7
const STRING_ESCAPE = 8
const SRTING_CHAR = 9
const STRING = 10
const EQUALS = 11
const PLUS = 12
const MINUS = 13
const TIMES = 14
const DIVIDE = 15
const LPAR = 16
const RPAR = 17
const UMINUS = 18
const __EOF__ = 19
const __START__ = -1
const EXPR = -2

const capture = {
    "string": [STRING, 0, (ctx) => { return ctx.value.join("") }],
}

const actions = {
    "__default__": {
        1:[NUMBER, 0, (ctx) => { return parseInt(ctx.text) }],
        2:[NAME, 0, (ctx) => { return ctx.text }],
        3:[EQUALS, 0, (ctx) => { return ctx.text }],
        4:[PLUS, 0, (ctx) => { return ctx.text }],
        5:[MINUS, 0, (ctx) => { return ctx.text }],
        6:[TIMES, 0, (ctx) => { return ctx.text }],
        7:[DIVIDE, 0, (ctx) => { return ctx.text }],
        8:[LPAR, 0, (ctx) => { return ctx.text }],
        9:[RPAR, 0, (ctx) => { return ctx.text }],
        10:[QUOTE, 1, (ctx) => { ctx.enter("string", []) }],
        11:[NEWLINE, 1, (ctx) => { return ctx.text }],
        12:[WHITE, 1, (ctx) => { return ctx.text }],
        13:[MISMATCH, 1, (ctx) => { throw Error("missmatch") }],
    },
    "string": {
        1:[STRING_QUOTE, 1, (ctx) => { ctx.leave() }],
        2:[STRING_ESCAPE, 1, (ctx) => { ctx.value.push(ctx.text[1]) }],
        3:[SRTING_CHAR, 1, (ctx) => { ctx.value.push(ctx.text) }],
        4:[MISMATCH, 1, (ctx) => { throw Error("missmatch") }],
    },
} // actions

const regexps = {
    "__default__": /(\d+)|([a-zA-Z_]+\w*)|(=)|(\+)|(-)|(\*)|(\/)|(\()|(\))|(")|(\n+)|(\s+)|(.)/g,
    "string": /(")|(\\")|(.)|(.)/g,
}

export function* scan(content, filename) {
    const location = new Location(filename, 0, 0)
    const stack = []
    var leave_flag = false
    var pos = 0

    const leave = () => {
        leave_flag = true
    }

    const enter = (name, value) => {
        stack.push(new Context(name, regexps[name], value, location, enter, leave))
    }

    stack.push(new Context('__default__', regexps['__default__'], null, location, enter, leave))

    while (true) {
        var ctx = stack[stack.length - 1]

        if (leave_flag) {
            leave_flag = false
            const [tok, discard, action] = capture[ctx.name]
            const value = action(ctx)
            if (!discard) {
                yield [tok, value]
            }
            stack.pop()
            ctx = stack[stack.length - 1]
        }

        ctx._regexp.lastIndex = pos
        const m = ctx._regexp.exec(content)
        if (m === null) {
            break
        }
        pos = ctx._regexp.lastIndex

        const action_map = actions[ctx.name]

        for (const [idx, token_info] of Object.entries(action_map)) {
            if (m[idx] !== undefined) {
                ctx.text = m[idx]
                const [tok, discard, action] = token_info
                const value = action(ctx)
                if (!discard) {
                    yield [tok, value]
                }
                break
            }
        }
    }

    yield [__EOF__, null]
}

export function parse(tokenizer, context) {
    const state_stack = [9]
    const token_reader = new TokenReader(tokenizer, __START__, __EOF__)
    var lookahead = token_reader.peek()
    while(!token_reader.done()) {
        switch(state_stack[state_stack.length - 1]) {
            case 0:
                switch(lookahead[0]) {
                    case TIMES:
                        state_stack.push(1)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case DIVIDE:
                        state_stack.push(3)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    default:
                        if (lookahead[0] > 0 && lookahead[0]> 100000)
                        {
                            token_reader.discard()
                            lookahead = token_reader.peek()
                            break
                        }
                        const args = []
                        for (const tv of token_reader.consume(3)) { args.push(tv[1]) }
                        const value = context["expr_expr_opr_expr"].apply(context, args)
                        token_reader.commit([EXPR, value])
                        state_stack.splice(state_stack.length - 3, 3)
                        lookahead = token_reader.top()
                        break
                }
                break
            
            case 1:
                switch(lookahead[0]) {
                    case EXPR:
                        state_stack.push(2)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case NAME:
                        state_stack.push(14)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case LPAR:
                        state_stack.push(5)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case MINUS:
                        state_stack.push(10)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case STRING:
                        state_stack.push(13)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case NUMBER:
                        state_stack.push(15)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    default:
                        if (lookahead[0] > 0 && lookahead[0]> 100000)
                        {
                            token_reader.discard()
                            lookahead = token_reader.peek()
                            break
                        }
                        throw Error(`unexpected token ${lookahead[0]}`)
                        break
                }
                break
            
            case 2:
                switch(lookahead[0]) {
                    default:
                        if (lookahead[0] > 0 && lookahead[0]> 100000)
                        {
                            token_reader.discard()
                            lookahead = token_reader.peek()
                            break
                        }
                        const args = []
                        for (const tv of token_reader.consume(3)) { args.push(tv[1]) }
                        const value = context["expr_expr_opr_expr"].apply(context, args)
                        token_reader.commit([EXPR, value])
                        state_stack.splice(state_stack.length - 3, 3)
                        lookahead = token_reader.top()
                        break
                }
                break
            
            case 3:
                switch(lookahead[0]) {
                    case EXPR:
                        state_stack.push(4)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case NAME:
                        state_stack.push(14)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case LPAR:
                        state_stack.push(5)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case MINUS:
                        state_stack.push(10)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case STRING:
                        state_stack.push(13)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case NUMBER:
                        state_stack.push(15)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    default:
                        if (lookahead[0] > 0 && lookahead[0]> 100000)
                        {
                            token_reader.discard()
                            lookahead = token_reader.peek()
                            break
                        }
                        throw Error(`unexpected token ${lookahead[0]}`)
                        break
                }
                break
            
            case 4:
                switch(lookahead[0]) {
                    default:
                        if (lookahead[0] > 0 && lookahead[0]> 100000)
                        {
                            token_reader.discard()
                            lookahead = token_reader.peek()
                            break
                        }
                        const args = []
                        for (const tv of token_reader.consume(3)) { args.push(tv[1]) }
                        const value = context["expr_expr_opr_expr"].apply(context, args)
                        token_reader.commit([EXPR, value])
                        state_stack.splice(state_stack.length - 3, 3)
                        lookahead = token_reader.top()
                        break
                }
                break
            
            case 5:
                switch(lookahead[0]) {
                    case EXPR:
                        state_stack.push(7)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case NAME:
                        state_stack.push(14)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case LPAR:
                        state_stack.push(5)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case MINUS:
                        state_stack.push(10)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case STRING:
                        state_stack.push(13)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case NUMBER:
                        state_stack.push(15)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    default:
                        if (lookahead[0] > 0 && lookahead[0]> 100000)
                        {
                            token_reader.discard()
                            lookahead = token_reader.peek()
                            break
                        }
                        throw Error(`unexpected token ${lookahead[0]}`)
                        break
                }
                break
            
            case 6:
                switch(lookahead[0]) {
                    default:
                        if (lookahead[0] > 0 && lookahead[0]> 100000)
                        {
                            token_reader.discard()
                            lookahead = token_reader.peek()
                            break
                        }
                        const args = []
                        for (const tv of token_reader.consume(2)) { args.push(tv[1]) }
                        const value = args[0]
                        token_reader.commit([__START__, value])
                        state_stack.splice(state_stack.length - 2, 2)
                        lookahead = token_reader.top()
                        break
                }
                break
            
            case 7:
                switch(lookahead[0]) {
                    case RPAR:
                        state_stack.push(8)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case PLUS:
                        state_stack.push(18)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case MINUS:
                        state_stack.push(20)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case TIMES:
                        state_stack.push(1)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case DIVIDE:
                        state_stack.push(3)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    default:
                        if (lookahead[0] > 0 && lookahead[0]> 100000)
                        {
                            token_reader.discard()
                            lookahead = token_reader.peek()
                            break
                        }
                        throw Error(`unexpected token ${lookahead[0]}`)
                        break
                }
                break
            
            case 8:
                switch(lookahead[0]) {
                    default:
                        if (lookahead[0] > 0 && lookahead[0]> 100000)
                        {
                            token_reader.discard()
                            lookahead = token_reader.peek()
                            break
                        }
                        const args = []
                        for (const tv of token_reader.consume(3)) { args.push(tv[1]) }
                        const value = context["expr_lpar_expr_rpar"].apply(context, args)
                        token_reader.commit([EXPR, value])
                        state_stack.splice(state_stack.length - 3, 3)
                        lookahead = token_reader.top()
                        break
                }
                break
            
            case 9:
                switch(lookahead[0]) {
                    case EXPR:
                        state_stack.push(11)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case NAME:
                        state_stack.push(14)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case LPAR:
                        state_stack.push(5)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case MINUS:
                        state_stack.push(10)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case STRING:
                        state_stack.push(13)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case NUMBER:
                        state_stack.push(15)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    default:
                        if (lookahead[0] > 0 && lookahead[0]> 100000)
                        {
                            token_reader.discard()
                            lookahead = token_reader.peek()
                            break
                        }
                        throw Error(`unexpected token ${lookahead[0]}`)
                        break
                }
                break
            
            case 10:
                switch(lookahead[0]) {
                    case EXPR:
                        state_stack.push(12)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case NAME:
                        state_stack.push(14)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case LPAR:
                        state_stack.push(5)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case MINUS:
                        state_stack.push(10)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case STRING:
                        state_stack.push(13)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case NUMBER:
                        state_stack.push(15)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    default:
                        if (lookahead[0] > 0 && lookahead[0]> 100000)
                        {
                            token_reader.discard()
                            lookahead = token_reader.peek()
                            break
                        }
                        throw Error(`unexpected token ${lookahead[0]}`)
                        break
                }
                break
            
            case 11:
                switch(lookahead[0]) {
                    case __EOF__:
                        state_stack.push(6)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case PLUS:
                        state_stack.push(18)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case MINUS:
                        state_stack.push(20)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case TIMES:
                        state_stack.push(1)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case DIVIDE:
                        state_stack.push(3)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    default:
                        if (lookahead[0] > 0 && lookahead[0]> 100000)
                        {
                            token_reader.discard()
                            lookahead = token_reader.peek()
                            break
                        }
                        throw Error(`unexpected token ${lookahead[0]}`)
                        break
                }
                break
            
            case 12:
                switch(lookahead[0]) {
                    default:
                        if (lookahead[0] > 0 && lookahead[0]> 100000)
                        {
                            token_reader.discard()
                            lookahead = token_reader.peek()
                            break
                        }
                        const args = []
                        for (const tv of token_reader.consume(2)) { args.push(tv[1]) }
                        const value = context["expr_minus_expr"].apply(context, args)
                        token_reader.commit([EXPR, value])
                        state_stack.splice(state_stack.length - 2, 2)
                        lookahead = token_reader.top()
                        break
                }
                break
            
            case 13:
                switch(lookahead[0]) {
                    default:
                        if (lookahead[0] > 0 && lookahead[0]> 100000)
                        {
                            token_reader.discard()
                            lookahead = token_reader.peek()
                            break
                        }
                        const args = []
                        for (const tv of token_reader.consume(1)) { args.push(tv[1]) }
                        const value = context["expr_string"].apply(context, args)
                        token_reader.commit([EXPR, value])
                        state_stack.splice(state_stack.length - 1, 1)
                        lookahead = token_reader.top()
                        break
                }
                break
            
            case 14:
                switch(lookahead[0]) {
                    case EQUALS:
                        state_stack.push(16)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    default:
                        if (lookahead[0] > 0 && lookahead[0]> 100000)
                        {
                            token_reader.discard()
                            lookahead = token_reader.peek()
                            break
                        }
                        const args = []
                        for (const tv of token_reader.consume(1)) { args.push(tv[1]) }
                        const value = context["expr_name"].apply(context, args)
                        token_reader.commit([EXPR, value])
                        state_stack.splice(state_stack.length - 1, 1)
                        lookahead = token_reader.top()
                        break
                }
                break
            
            case 15:
                switch(lookahead[0]) {
                    default:
                        if (lookahead[0] > 0 && lookahead[0]> 100000)
                        {
                            token_reader.discard()
                            lookahead = token_reader.peek()
                            break
                        }
                        const args = []
                        for (const tv of token_reader.consume(1)) { args.push(tv[1]) }
                        const value = context["expr_number"].apply(context, args)
                        token_reader.commit([EXPR, value])
                        state_stack.splice(state_stack.length - 1, 1)
                        lookahead = token_reader.top()
                        break
                }
                break
            
            case 16:
                switch(lookahead[0]) {
                    case EXPR:
                        state_stack.push(17)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case NAME:
                        state_stack.push(14)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case LPAR:
                        state_stack.push(5)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case MINUS:
                        state_stack.push(10)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case STRING:
                        state_stack.push(13)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case NUMBER:
                        state_stack.push(15)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    default:
                        if (lookahead[0] > 0 && lookahead[0]> 100000)
                        {
                            token_reader.discard()
                            lookahead = token_reader.peek()
                            break
                        }
                        throw Error(`unexpected token ${lookahead[0]}`)
                        break
                }
                break
            
            case 17:
                switch(lookahead[0]) {
                    case PLUS:
                        state_stack.push(18)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case MINUS:
                        state_stack.push(20)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case TIMES:
                        state_stack.push(1)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case DIVIDE:
                        state_stack.push(3)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    default:
                        if (lookahead[0] > 0 && lookahead[0]> 100000)
                        {
                            token_reader.discard()
                            lookahead = token_reader.peek()
                            break
                        }
                        const args = []
                        for (const tv of token_reader.consume(3)) { args.push(tv[1]) }
                        const value = context["expr_name_eq_expr"].apply(context, args)
                        token_reader.commit([EXPR, value])
                        state_stack.splice(state_stack.length - 3, 3)
                        lookahead = token_reader.top()
                        break
                }
                break
            
            case 18:
                switch(lookahead[0]) {
                    case EXPR:
                        state_stack.push(19)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case NAME:
                        state_stack.push(14)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case LPAR:
                        state_stack.push(5)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case MINUS:
                        state_stack.push(10)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case STRING:
                        state_stack.push(13)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case NUMBER:
                        state_stack.push(15)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    default:
                        if (lookahead[0] > 0 && lookahead[0]> 100000)
                        {
                            token_reader.discard()
                            lookahead = token_reader.peek()
                            break
                        }
                        throw Error(`unexpected token ${lookahead[0]}`)
                        break
                }
                break
            
            case 19:
                switch(lookahead[0]) {
                    case TIMES:
                        state_stack.push(1)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case DIVIDE:
                        state_stack.push(3)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    default:
                        if (lookahead[0] > 0 && lookahead[0]> 100000)
                        {
                            token_reader.discard()
                            lookahead = token_reader.peek()
                            break
                        }
                        const args = []
                        for (const tv of token_reader.consume(3)) { args.push(tv[1]) }
                        const value = context["expr_expr_opr_expr"].apply(context, args)
                        token_reader.commit([EXPR, value])
                        state_stack.splice(state_stack.length - 3, 3)
                        lookahead = token_reader.top()
                        break
                }
                break
            
            case 20:
                switch(lookahead[0]) {
                    case EXPR:
                        state_stack.push(0)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case NAME:
                        state_stack.push(14)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case LPAR:
                        state_stack.push(5)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case MINUS:
                        state_stack.push(10)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case STRING:
                        state_stack.push(13)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    case NUMBER:
                        state_stack.push(15)
                        if (lookahead[0] > 0) token_reader.read()
                        lookahead = token_reader.peek()
                        break
                    default:
                        if (lookahead[0] > 0 && lookahead[0]> 100000)
                        {
                            token_reader.discard()
                            lookahead = token_reader.peek()
                            break
                        }
                        throw Error(`unexpected token ${lookahead[0]}`)
                        break
                }
                break
            
        }
    }
    return token_reader.pop()[1]
}
