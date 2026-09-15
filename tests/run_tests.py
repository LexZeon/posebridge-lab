"""Isolate all application storage before importing the application/test suite."""
from pathlib import Path
import hashlib
import os
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'.runtime-deps'),str(ROOT/'tests')]


def main():
    personal=Path(os.environ.get('POSEBRIDGE_HOME',Path(os.environ.get('LOCALAPPDATA',Path.home()))/'PoseBridgeLab'))/'settings.json'
    def fingerprint():return hashlib.sha256(personal.read_bytes()).digest() if personal.exists() else None
    before=fingerprint()
    with tempfile.TemporaryDirectory(prefix='posebridge-tests-') as folder:
        os.environ['POSEBRIDGE_HOME']=folder
        suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        assert fingerprint()==before,'Personal settings changed during tests'
    print('Application storage isolated; personal settings unchanged.')
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
