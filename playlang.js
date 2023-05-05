// Copyright (C) 2023 pom@vro.life
// SPDX-License-Identifier: MIT OR LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only
export class TokenReader {
    constructor(tokenizer, start, eof) {
        this._tokenizer = tokenizer
        this._start = start
        this._eof = eof
        this._stack = []
        this._next_token = undefined
    }
    
    _read() {
        const {done, value} = this._tokenizer.next()
        if (done) {
            return [this._eof, undefined, undefined]
        }
        return value
    }
    
    done() { return this._stack.length == 1 && this._stack[this._stack.length-1][0] === this._start; }
    top() { return this._stack[this._stack.length - 1]; }
    peek() {
        if (this._next_token === undefined) {
            this._next_token = this._read()
        }
        return this._next_token
    }
    
    discard() { this._next_token = undefined; }
    
    read() {
        var t = this._next_token
        if (t === undefined) {
            t = this._read()
        } else {
            this._next_token = undefined
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

export class Location {
    constructor(filename, line_num, column) {
        this._filename = filename
        this._line_num = line_num
        this._column = column
    }

    get filename() {
        return this._filename
    }

    get line() {
        return this._line_num
    }

    get column() {
        return this._column
    }

    lines(n) {
        this._line_num += n
        this._column = 0
        return undefined
    }

    step(n) {
        this._column += n
        return undefined
    }

    copy() {
        return new Location(this._line_num, this._column, this._filename)
    }
}

export class Context {
    constructor(name, regexp, value, location, enter, leave) {
        this.name = name
        this._regexp = regexp
        this._value = value
        this.text = undefined
        this._location = location

        this.enter = (name, value) => { enter(name, value); return this; }
        this.leave = () => { leave(); return this; }
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
        return this
    }

    lines(n) {
        this._location.lines(n)
        return this
    }
}

export class TrailingJunk extends Error {}
export class SyntaxError extends Error {}

export function create_scanner(actions, regexps, capture) {
    return function* (content, filename) {
        if (filename === undefined) {
            filename = '<memory>'
        }
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
    
        stack.push(new Context('__default__', regexps['__default__'], undefined, location, enter, leave))
    
        while (true) {
            var ctx = stack[stack.length - 1]
    
            if (leave_flag) {
                leave_flag = false
                if (ctx.name in capture) {
                    const [tok, discard, action] = capture[ctx.name]
                    const value = action(ctx)
                    if (!discard) {
                        yield [tok, value, location]
                    }
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
                        yield [tok, value, location]
                    }
                    break
                }
            }
        }
    
        if (pos !== content.length){
            throw new TrailingJunk(location)
        }
    }
}
