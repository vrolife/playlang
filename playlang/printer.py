# Copyright (C) 2023 pom@vro.life
# SPDX-License-Identifier: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only

class LineAppend:

    def __init__(self, file):
        self._file = file

    def __del__(self):
        self._file.write('\n')

    def __add__(self, text):
        self._file.write(text)
        return self


class Printer:

    def __init__(self, file):
        self._indent = 0
        self._file = file

    def __call__(self):
        return LineAppend(self._file)

    def __lt__(self, line):
        self + line
        self._indent += 4
        return None

    def __add__(self, line):
        self._file.write(' ' * self._indent)
        self._file.write(line)
        return LineAppend(self._file)

    def __or__(self, line):
        self._file.write(line)
        return LineAppend(self._file)

    def __gt__(self, line):
        self._indent -= 4
        self + line
        return None

    def __lshift__(self, line):
        self._indent += 4
        self + line

    def __rshift__(self, line):
        self + line
        self._indent -= 4

    def array(self, items, single_line=False):
        if single_line:
            self + ', '.join(items)
        else:
            for item in items:
                self + item + ','

