# Copyright (C) 2023 pom@vro.life
# SPDX-License-Identifier: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only
import re
from typing import List, Dict
from playlang.classes import Terminal, Location, TokenValue, StaticField, Scanner


class TrailingJunk(Exception):
    pass


class DiscardError(Exception):
    pass


class ContextError(Exception):
    pass


class Tokenizer:
    def __init__(self, clazz, default_action):
        self.regexps = {}
        self._eof_tokens = {}
        self._default_action = default_action
        self._actions = {}
        self._capture = {}

        if isinstance(clazz, dict):
            scanners = clazz
        else:
            scanners = clazz.__scanners__

        scanners: Dict[str, Scanner]

        for contition, scanner in scanners.items():
            self._eof_tokens[contition] = scanner.eof_token

            for token in scanner.tokens:
                if token.capture:
                    self._capture[contition] = self._convert(token)
                    continue

                if token.is_eof:
                    self._actions[token.fullname] = self._convert(token)
                    continue

                if token.pattern is None:
                    raise TypeError(
                        f'token "{token.fullname}" missing pattern')

                if not isinstance(token.pattern, (str, re.Pattern)):
                    raise TypeError(
                        f'pattern must be "str" or "re.Pattern": {token.fullname}')

                if token.fullname in self._actions:
                    continue

                self._actions[token.fullname] = self._convert(token)

        for contition, scanner in scanners.items():
            patterns = []
            for token in scanner.tokens:
                pattern, trailing = map(token.data.get, ('pattern', 'trailing'))

                if trailing is None:
                    trailing = ""
                else:
                    trailing = f'(?={trailing})'

                patterns.append(f'(?P<{token.fullname}>{pattern}){trailing}')

            self.regexps[contition] = re.compile('|'.join(patterns))

    def _convert(self, token: Terminal):
        action, discard = map(token.data.get, ('action', 'discard'))

        def action_wrapper(context):
            value = None
            loc = context.location.copy()

            if isinstance(action, type):
                value = action(context.text)
                self._default_action(context)

            elif callable(action):
                value = action(context)

            if action is None:
                value = context.text
                self._default_action(context)

            if discard:
                raise DiscardError()

            return TokenValue(token, value, loc)

        return action_wrapper

    def __call__(self, string, filename='<memory>', ignore_tailing=False, eof_stop=False):
        location = Location(filename=filename)
        stack = []
        leave = False

        this = self

        class Context:
            def __init__(self, name, regexp, value, end_of_file):
                self.name = name
                self._regexp = regexp
                self._value = value
                self._end_of_file = end_of_file
                self.text = None

            def __repr__(self):
                return self.name

            def step(self, n=None):
                nonlocal location
                if n is None:
                    location.step(len(self.text))
                else:
                    location.step(n)
                return self

            def lines(self, n):
                location.lines(n)
                return self

            @property
            def value(self):
                return self._value

            @property
            def location(self):
                return location

            def enter(self, name, value=None):
                nonlocal stack
                stack.append(Context(name, this.regexps[name], value, this._eof_tokens[name]))
                return self

            def leave(self):
                nonlocal leave
                if stack.__len__() == 1:
                    raise Exception('leave top context are not allowed')
                leave = True
                return self

        stack.append(
            Context('__default__', self.regexps['__default__'], None, self._eof_tokens['__default__']))

        pos = 0
        while True:
            ctx = stack[-1]
            try:
                if leave:
                    leave = False
                    if ctx.name in self._capture:
                        yield self._capture[ctx.name](ctx)
                    stack.pop()
                    ctx = stack[-1]

                # is EOF
                if pos == len(string):
                    ctx.text = '__EOF__'
                    yield self._actions[ctx._end_of_file.fullname](ctx)
                    if eof_stop:
                        break
                    continue

                m = ctx._regexp.match(string, pos)
                if m is None:
                    break
                pos = m.end(m.lastgroup)
                ctx.text = m.group()
                yield self._actions[m.lastgroup](ctx)

            except DiscardError:
                continue

        if pos != len(string) and not ignore_tailing:
            raise TrailingJunk(location)


class StaticTokenizer(StaticField):
    def __init__(self, default_action=None):
        self._default_action = default_action

    def __call__(self, *args, **kwargs):
        pass

    def create(self, parser):
        return Tokenizer(parser, default_action=self._default_action)
