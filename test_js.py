import os, sys
import tempfile
import shutil
import unittest
from playlang.javascript import JavaScript
from tests import CompilerCalc

class TestJavaScript(unittest.TestCase):
    def test_javasript(self):
        print('js')
        compiler = CompilerCalc()
        with tempfile.TemporaryDirectory() as dir:
            with open(os.path.join(dir, 'parser.mjs'), 'w') as f:
                JavaScript.generate(compiler, f)
            shutil.copyfile('./tests.mjs', os.path.join(dir, 'tests.mjs'))

            self.assertEqual(os.system(f'cd "{dir}" && node tests.mjs'), 0)

if __name__ == '__main__':
    compiler = CompilerCalc()
    with open(os.path.join(sys.argv[1], 'parser.mjs'), 'w') as f:
        JavaScript.generate(compiler, f)
