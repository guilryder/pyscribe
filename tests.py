#!/usr/bin/env python
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license
#
# Runs unit tests for all modules.

import sys
sys.stderr = sys.stdout  # Hack to avoid interleaving problems.

import coverage
import glob
import optparse
import os
import shutil
import unittest
import webbrowser


# Inject a custom test loader to load only test case classes ending with 'Test'.
# Allows to declare abstract test cases.

class PyscribeTestLoader(unittest.TestLoader):
  def getTestCaseNames(self, testCaseClass):
    if testCaseClass.__name__.endswith('Test'):
      return unittest.TestLoader.getTestCaseNames(self, testCaseClass)
    else:
      return []

def PyscribeTestProgram(**kwargs):
  kwargs['testLoader'] = unittest.defaultTestLoader
  unittest.TestProgram(**kwargs)

unittest.defaultTestLoader = PyscribeTestLoader()
unittest.main = PyscribeTestProgram


# The files to analyze for coverage or run if they are tests.
# *_test.py files are added as tests.
# All other files are analyzed for test coverage.
def GetPythonFiles():
  return glob.glob('*.py')


# The files generated on execution, to be deleted by --clean.
generated_files = [
    'parser.out',
    'parsetab.py',
  ]


# The files to exclude explicitly.
ignored_files = [
    'tests.py',
  ]


class TestsManager:

  # The directory to write coverage files into.
  COVERAGE_DIR = 'cov'

  # The coverage report index file (HTML).
  COVERAGE_INDEX = os.path.join(COVERAGE_DIR, 'index.html')

  def __init__(self, python_files, excluded_files):
    python_files = set(python_files)
    python_files.difference_update(excluded_files)
    self.python_files = python_files
    (self.prod_module_files, self.test_module_names) = \
        self.GetProdAndTestModules(python_files)

  def Main(self):
    parser = optparse.OptionParser(description="Runs the actions in the same "
        "order they are specified.")

    def AddAction(function, name, *args, **kwargs):
      kwargs = dict(kwargs)
      kwargs.update(dict(action='append_const',
          const=function, dest='actions'))
      parser.add_option('--' + name, *args, **kwargs)

    AddAction(self.RunTests, 'test', '-t', help="run the tests")
    AddAction(self.RunTestsAndReportCoverage, 'coverage', '-c',
        help="run the tests, record coverage information, print a summary, and "
            "generate detailed HTML reports (default action)")
    AddAction(self.Clean, 'clean', '-x',
        help="deletes compilation artifacts and coverage reports")
    AddAction(self.ShowCoverage, 'show-coverage', '-s',
        help="shows coverage results in the default Internet browser")
    AddAction(self.Lint, 'lint', '-l',
        help="runs the linter against all source files")
    (options, args) = parser.parse_args()

    if args:
      parser.error('unexpected argument: %s' % args[0])

    default_actions = [self.RunTestsAndReportCoverage]
    actions = options.actions or default_actions

    for action in actions:
      action()

  def GetProdAndTestModules(self, python_files):  # pylint: disable=no-self-use
    """Divides the given Python files into production and test modules.

    Does not load the module, so that coverage information is not lost.

    Args:
      python_files: The Python files to record coverage for or run as tests.

    Returns (module_file list, test_module_name list):
      The module files to compute coverage for (with extension) and the test
      test module names (without extension).
    """
    prod_module_files = []
    test_module_names = []
    for python_file in python_files:
      if python_file.endswith('_test.py'):
        test_module_names.append(python_file[:-3])
      else:
        prod_module_files.append(python_file)
    return (prod_module_files, test_module_names)

  def RunTests(self):
    """Runs all tests among the files specified at construction."""
    tests = map(unittest.defaultTestLoader.loadTestsFromName,
                self.test_module_names)
    suite = unittest.TestSuite()
    suite.addTests(tests)
    runner = unittest.TextTestRunner()
    runner.run(suite)

  def RunTestsAndReportCoverage(self):
    """Run the tests and generates code coverage reports for production code.

    Runs the tests by calling RunTests().

    Generates a coverage report under COVERAGE_DIR.
    """

    # Configure the coverage recorder.
    cov = coverage.coverage(include=self.python_files)
    cov.config.exclude_list.append(r'if __name__ == .__main__.:')
    cov.use_cache(False)

    # Record coverage information.
    cov.start()
    self.RunTests()
    cov.stop()

    # Generate HTML reports.
    cov.html_report(directory=self.COVERAGE_DIR)

    # Print a coverage summary to the standard output.
    cov.report()

  def Clean(self):
    """Deletes compiled Python files and coverage reports."""
    files_to_delete = glob.glob('*.pyc')
    files_to_delete.extend(generated_files)
    for path in files_to_delete:
      if os.path.exists(path):
        os.remove(path)
    shutil.rmtree(self.COVERAGE_DIR, ignore_errors=True)

  def ShowCoverage(self):
    """Opens coverage summary HTML file in the default Internet browser."""
    webbrowser.open(self.COVERAGE_INDEX)

  def Lint(self):
    """Runs the linter against all source files."""
    lint_files = self.python_files | set(['tests.py'])
    os.system('python -m pylint --output-format=parseable {files}'
        .format(files=' '.join(lint_files)))


if __name__ == '__main__':
  os.chdir(os.path.dirname(sys.argv[0]) or '.')
  tests_manager = TestsManager(python_files=GetPythonFiles(),
                               excluded_files=ignored_files + generated_files)
  tests_manager.Main()
