import unittest
import tempfile
import os
from files import do_thing

class TestDoThing(unittest.TestCase):
    def test_basic(self):
        with tempfile.TemporaryDirectory() as td:
            os.chdir(td)
            with open('target.txt', 'w') as f:
                f.write('data')
            result = do_thing('target.txt')
            self.assertIn(os.path.abspath('target.txt'), result)

    def test_recursive(self):
        with tempfile.TemporaryDirectory() as td:
            os.chdir(td)
            os.makedirs('subdir')
            with open('subdir/nested.txt', 'w') as f:
                f.write('data')
            result = do_thing('nested.txt', recursive=True)
            self.assertIn(os.path.abspath('subdir/nested.txt'), result)

    def test_not_found(self):
        with tempfile.TemporaryDirectory() as td:
            os.chdir(td)
            result = do_thing('nonexistent.txt')
            self.assertEqual(result, [])

if __name__ == '__main__':
    unittest.main()