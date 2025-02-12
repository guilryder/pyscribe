#!/usr/bin/env python3
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license
#
# Runs unit tests for all modules.

import sys
sys.stderr = sys.stdout  # Hack to avoid interleaving problems.

import argparse
import coverage
import glob
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import unittest
import webbrowser


class TestsManager:

  # The directory to write coverage files into.
  COVERAGE_DIR = Path('cov')

  # The coverage report index file (HTML).
  COVERAGE_INDEX = COVERAGE_DIR / 'index.html'

  # The directories that --clean should delete.
  DIRS_TO_CLEAN = (
    COVERAGE_DIR,
    '__pycache__',
    '.mypy_cache',
  )

  def __init__(self, *, included_files, excluded_files):
    self.__python_files = frozenset(set(included_files) - set(excluded_files))

  def Main(self):
    parser = argparse.ArgumentParser(
        description="Runs the actions in the same order they are specified.")

    def AddAction(function, name, *args, **kwargs):
      kwargs.update(action='append_const', const=function, dest='actions')
      parser.add_argument('--' + name, *args, **kwargs)

    AddAction(self.RunTests, 'test', '-t',
        help="run the tests")
    AddAction(self.RunTestsAndReportCoverage, 'coverage', '-c',
        help="run the tests, record coverage information, print a summary, and "
            "generate detailed HTML reports (default action)")
    AddAction(self.Clean, 'clean', '-x',
        help="delete compilation artifacts and coverage reports")
    AddAction(self.ShowCoverage, 'show-coverage', '-s',
        help="show coverage results in the default Internet browser")
    AddAction(self.TypeCheck, 'typecheck', '-tc',
        help="run the type checker against all source files")
    AddAction(self.Lint, 'lint', '-l',
        help="run the linter against all source files")
    AddAction(self.RegenerateGoldens, 'golden', '-g',
        help="regenerate the golden outputs")
    args = parser.parse_args()

    default_actions = [self.RunTestsAndReportCoverage]
    for action in args.actions or default_actions:
      action()

  def RunTests(self):
    """Runs all tests files."""
    unittest.TextTestRunner().run(
        unittest.defaultTestLoader.loadTestsFromNames(
            python_file[:-3] for python_file in self.__python_files))

  def RunTestsAndReportCoverage(self):
    """Run all tests and generates code coverage reports.

    Runs the tests by calling RunTests().

    Generates a coverage report under COVERAGE_DIR.
    """

    # Configure the coverage recorder.
    cov = coverage.coverage(include=self.__python_files)
    cov.config.exclude_list.append(r'if __name__ == .__main__.:')

    # Record coverage information.
    cov.start()
    self.RunTests()
    cov.stop()

    # Generate HTML reports.
    cov.html_report(directory=str(self.COVERAGE_DIR))

    # Print a coverage summary to the standard output.
    cov.report()

  def Clean(self):
    """Deletes Python cache files and coverage reports."""
    for dir_name in self.DIRS_TO_CLEAN:
      shutil.rmtree(dir_name, ignore_errors=True)

  def ShowCoverage(self):
    """Opens coverage summary HTML file in the default Internet browser."""
    webbrowser.open(self.COVERAGE_INDEX)

  def TypeCheck(self):
    """Runs the type checker against all source files."""
    checked_files = [file for file in self.__python_files
                     if not file.endswith('_test.py') and
                        file != 'testutils.py']
    subprocess.call([sys.executable, '-m', 'mypy'] + checked_files)

  def Lint(self):
    """Runs the linter against all source files."""
    subprocess.call(
        [sys.executable, '-m', 'pylint', '--output-format=parseable'] +
            list(self.__python_files))

  def RegenerateGoldens(self):
    """Regenerates the golden output files under testdata/."""
    # Local imports to avoid impacting coverage reports.
    from pyscribe_test import GOLDEN_TEST_DEFINITIONS
    from testutils import TESTDATA_DIR
    print(f'Switching to: {TESTDATA_DIR}')
    os.chdir(TESTDATA_DIR)
    for cmdline in GOLDEN_TEST_DEFINITIONS:
      args = [sys.executable, '../pyscribe.py'] + shlex.split(cmdline)
      print(f'Executing: {" ".join(map(shlex.quote, args))}',
            flush=True)
      subprocess.call(args)


if __name__ == '__main__':
  os.chdir(Path(sys.argv[0]).parent)
  tests_manager = TestsManager(included_files=glob.glob('*.py'),
                               excluded_files=['tests.py'])
  tests_manager.Main()
