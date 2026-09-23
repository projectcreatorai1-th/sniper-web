"""Run the web test suite:  python run_web_tests.py

Note: tests/web intentionally has NO __init__.py - the desktop runner
(python run_tests.py) skips non-package subdirectories, so the desktop
suite stays exactly as before. This runner discovers tests/web with that
directory itself on sys.path (helpers import as top-level modules).
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB_TESTS = os.path.join(ROOT, "tests", "web")
sys.path.insert(0, ROOT)
sys.path.insert(0, WEB_TESTS)

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.discover(WEB_TESTS, pattern="test_web_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
