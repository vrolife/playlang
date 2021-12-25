import os, sys
import tempfile
import shutil
import unittest
from playlang.javascript import JavaScript
from tests import ParserCalc

class TestJavaScript(unittest.TestCase):
    def test_javasript(self):
        print('js')
        compiler = ParserCalc()
        with tempfile.TemporaryDirectory() as dir:
            with open(os.path.join(dir, 'parser.mjs'), 'w') as f:
                JavaScript.generate(compiler, f)
            shutil.copyfile('./tests.mjs', os.path.join(dir, 'tests.mjs'))

            status = os.system(f'cd "{dir}" && node tests.mjs')
            if status != 0:
                with open(os.path.join(dir, 'parser.mjs'), 'r') as f:
                    print(f.read())
            self.assertTrue(status == 0)

if __name__ == '__main__':
    compiler = ParserCalc()
    if sys.argv[1] == '-':
        JavaScript.generate(compiler, sys.stdout)
    else:
        with open(os.path.join(sys.argv[1], 'parser.mjs'), 'w') as f:
            JavaScript.generate(compiler, f)
