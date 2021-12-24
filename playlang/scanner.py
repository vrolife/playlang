import re
from playlang.objects import Terminal
from playlang.api import Location, ScanInfo, TokenValue


class DiscardError(Exception):
    pass


class ContextError(Exception):
    pass


class Scanner:
    def __init__(self, clazz, default_action):
        self._regexps = {}
        self._default_action = default_action
        self._actions = {}
        self._capture = {}

        if isinstance(clazz, ScanInfo):
            scan_info = clazz
        else:
            scan_info = clazz.__scan_info__

        for name, token_info in scan_info.tokens.items():
            pattern, capture = map(token_info.get, ('pattern', 'capture'))

            if capture is not None:
                self._capture[capture] = self._convert(name, token_info)
                continue

            if pattern is None:
                raise TypeError(f'token "{name}" missing pattern')

            if not isinstance(pattern, (str, re.Pattern)):
                raise TypeError(
                    f'patter must be "str" or "re.Pattern": {name}')

            self._actions[name] = self._convert(name, token_info)

        for context, tokens in scan_info.contexts.items():
            pairs = []
            for tok in tokens:
                name = tok
                if isinstance(tok, Terminal):
                    name = tok.name
                token_info = scan_info.tokens.get(name, {})
                pairs.append((name, token_info.get('pattern')))

            self._regexps[context] = re.compile(
                '|'.join([f'(?P<%s>%s)' % pair for pair in pairs]))

    def _convert(self, name, token_info: dict):
        if name in self._actions:
            raise TypeError(f'duplicate token {name}')

        action, discard, token = map(
            token_info.get, ('action', 'discard', 'token'))

        def action_wrapper(context):
            value = None

            if isinstance(action, type):
                value = action(context.text)
                self._default_action(context)

            elif callable(action):
                value = action(context)

            if action is None:
                value = context.text
                self._default_action(context)

            if value is None or discard:
                raise DiscardError()

            return TokenValue(token, value, context.location.copy())

        return action_wrapper

    def __call__(self, string, filename='<memory>', raise_eof=True):
        location = Location(filename=filename)
        stack = []
        leave = False

        this = self

        class Context:
            def __init__(self, name, regexp, value):
                self.name = name
                self._regexp = regexp
                self._value = value
                self.text = None

            def __repr__(self):
                return self.name

            def step(self, n=None):
                nonlocal location
                if n is None:
                    location.step(len(self.text))
                else:
                    location.step(n)

            def lines(self, n):
                location.lines(n)

            @property
            def value(self):
                return self._value

            @property
            def location(self):
                return location

            def enter(self, name, value=None):
                nonlocal stack
                stack.append(Context(name, this._regexps[name], value))

            def leave(self):
                nonlocal leave
                if stack.__len__() == 1:
                    raise Exception('leave top context are not allowed')
                leave = True

        stack.append(Context('__default__', self._regexps['__default__'], None))

        pos = 0
        while True:
            ctx = stack[-1]
            try:
                if leave:
                    leave = False
                    yield self._capture[ctx.name](ctx)
                    stack.pop()
                    ctx = stack[-1]

                m = ctx._regexp.match(string, pos)
                if m is None:
                    break
                pos = m.end(m.lastgroup)
                ctx.text = m.group()
                yield self._actions[m.lastgroup](ctx)

            except DiscardError:
                continue

        if raise_eof:
            raise EOFError(location)
