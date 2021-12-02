import re
from playlang.objects import Location, Token, TokenValue


class DiscardError(Exception):
    pass


class Tokenizer:
    def __init__(self, tokens, default_action=None):
        self._default_action = default_action
        self._makers = {}
        pairs = []

        for item in tokens:
            pairs.append(self._convert(*item))

        self._regex = re.compile(
            '|'.join([f'(?P<%s>%s)' % pair for pair in pairs]))

    def _convert(self, token, regex, action=None):
        if isinstance(token, str):
            name = token
            if action is not None and (not callable(action) or isinstance(action, type)):
                raise TypeError(f'{name}: the third item must be a function')
        elif isinstance(token, Token):
            name = token.name
            if action is not None and not callable(action):
                raise TypeError(
                    f'{name}: the third item must be a class or function')
        else:
            raise TypeError('the first item must be a token or unique string')

        if not isinstance(regex, str):
            raise TypeError(f'{name}: the second item must be a string')

        if name in self._makers:
            raise TypeError(f'duplicate token name {name}')

        def make_token(loc, text):
            value = None
            if action is None:
                if self._default_action is not None:
                    value = self._default_action(loc, text)

            elif isinstance(action, type):
                value = action(text)
                if self._default_action is not None:
                    self._default_action(loc, text)

            elif callable(action):
                value = action(loc, text)
            else:
                raise TypeError(action)

            if isinstance(token, str):
                raise DiscardError(loc, text)

            return TokenValue(token, value, loc.copy())

        self._makers[name] = make_token
        return name, regex

    def __call__(self, string, filename='<memory>', raise_eof=True):
        location = Location(filename=filename)
        for m in self._regex.finditer(string):
            try:
                yield self._makers[m.lastgroup](location, m.group())
            except DiscardError:
                continue

        if raise_eof:
            raise EOFError(location)
