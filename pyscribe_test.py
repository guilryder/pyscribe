#!/usr/bin/env python3
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

import collections
import shlex

import pyscribe
from testutils import *


class EndToEndTestCase(TestCase):

  def setUp(self):
    super().setUp()
    self.inputs = {}
    self.fs = self.GetFileSystem(self.inputs)
    self.fs.InitializeForWrites()

  def GetStdFile(self, name):
    return getattr(self.fs, 'std' + name).getvalue().strip()

  def assertOutput(self, expected_filename, expected_output, expected_err=''):
    self.assertEqual(self.GetStdFile('err'), expected_err)
    self.assertEqual(self.fs.GetOutputs(),
                     {expected_filename: expected_output})

  def Execute(self, cmdline, expect_failure=False):
    args = shlex.split(cmdline)
    main = pyscribe.Main(
        input_args=args,
        fs=self.fs,
        main_file=FAKE_PYSCRIBE_DIR / 'pyscribe.py',
        ArgumentParser=lambda: FakeArgumentParser(self.fs.stderr))
    if expect_failure:
      with self.assertRaises(SystemExit):
        main.Run()
    else:
      try:
        main.Run()
      except SystemExit as e:  # pragma: no cover
        msg = 'Unexpected error:\n' + self.GetStdFile('err')
        raise AssertionError(msg) from e


class MainTest(EndToEndTestCase):

  @staticmethod
  def __Output(contents, branch_type='text'):
    return ('$branch.create.root[' + branch_type + '][root][.out]' +
            '$branch.write[root][' + contents + ']')

  def setUp(self):
    super().setUp()
    self.inputs.update({
        '/cur/input.psc': self.__Output('Hello, World!'),
        '/cur/format.psc': self.__Output('Format: $format'),
        '/cur/error.psc': '$invalid',
    })

  def testNoArguments(self):
    self.Execute('', expect_failure=True)
    self.assertEqual(self.GetStdFile('err'),
                     'error: the following arguments are required: filename')
    self.assertEqual(self.fs.GetOutputs(), {})

  def testTwoArguments(self):
    self.Execute('first second', expect_failure=True)
    self.assertEqual(self.GetStdFile('err'),
                     'error: unrecognized arguments: second')
    self.assertEqual(self.fs.GetOutputs(), {})

  def testHelp(self):
    self.Execute('--help', expect_failure=True)
    self.assertIn('positional arguments', self.GetStdFile('err'))
    self.assertEqual(self.fs.GetOutputs(), {})

  def testSimple(self):
    self.Execute('input.psc')
    self.assertOutput('/cur/input.out', 'Hello, World!')
    self.assertEqual(self.GetStdFile('out'),
                     'Writing: /cur/input.out')

  def testSimple_autoExtension(self):
    self.Execute('input')
    self.assertOutput('/cur/input.out', 'Hello, World!')

  def testSimple_quiet(self):
    self.Execute('input.psc -q')
    self.assertOutput('/cur/input.out', 'Hello, World!')
    self.assertEqual(self.GetStdFile('out'), '')

  def testCustomOutput_relative(self):
    self.Execute('input.psc --output ignored/../custom')
    self.assertEqual(self.fs.created_dirs, {'/cur/custom'})
    self.assertEqual(self.GetStdFile('out'),
                     'Writing: /cur/custom/input.out')
    self.assertEqual(self.GetStdFile('err'), '')
    self.assertEqual(self.fs.GetOutputs(),
                     {'/cur/custom/input.out': 'Hello, World!'})

  def testCustomOutput_absolute(self):
    self.Execute('input.psc --output /custom')
    self.assertEqual(self.fs.created_dirs, {'/custom'})
    self.assertEqual(self.GetStdFile('out'),
                     'Writing: /custom/input.out')
    self.assertEqual(self.GetStdFile('err'), '')
    self.assertEqual(self.fs.GetOutputs(),
                     {'/custom/input.out': 'Hello, World!'})

  def testCustomOutput_quiet(self):
    self.Execute('input.psc --output /custom --quiet')
    self.assertEqual(self.GetStdFile('out'), '')
    self.assertEqual(self.GetStdFile('err'), '')
    self.assertEqual(self.fs.GetOutputs(),
                     {'/custom/input.out': 'Hello, World!'})

  def testExecutionError_simpleErrorFormat(self):
    self.Execute('error.psc', expect_failure=True)
    self.assertEqual(self.GetStdFile('err'),
                     '/cur/error.psc:1: macro not found: $invalid\n'
                     'Set --error_format=python for details.')
    self.assertEqual(self.fs.GetOutputs(), {})

  def testExecutionError_pythonErrorFormat(self):
    self.Execute('error.psc --error_format python', expect_failure=True)
    error_log = self.GetStdFile('err')
    self.assertIn('File "/cur/error.psc", line 1\n' +
                  '    macro not found: $invalid',
                  error_log)
    self.assertIn('log.FatalError', error_log)
    self.assertEqual(self.fs.GetOutputs(), {})

  def testOutputFormat_default(self):
    self.Execute('format.psc')
    self.assertOutput('/cur/format.out', 'Format: html')

  def testOutputFormat_custom(self):
    self.Execute('format.psc --format latex')
    self.assertOutput('/cur/format.out', 'Format: latex')

  def testOutputFormat_invalid(self):
    self.Execute('format.psc --format invalid', expect_failure=True)
    self.assertIn('--format', self.GetStdFile('err'))
    self.assertEqual(self.fs.GetOutputs(), {})

  def testDefines(self):
    self.inputs['/cur/defines.psc'] = self.__Output('$one,$two,$three,$a.b')
    self.Execute('defines.psc -d one=1 -d two=2 -d three= -d two=2=2 -d a.b=c')
    self.assertOutput('/cur/defines.out', '1,2=2,,c')

  def testDefinesInvalidFormat(self):
    self.Execute('input.psc -d name', expect_failure=True)
    self.assertIn('-d/--define: invalid value, expected format: ' +
                  'name=text; got: name',
                  self.GetStdFile('err'))

  def testOutputFormatOverwritesDefines(self):
    self.Execute('format.psc --format html -d format=ignored')
    self.assertOutput('/cur/format.out', 'Format: html')

  def testOutputBasenamePrefix_empty(self):
    self.inputs['/cur/dummy.psc'] = (
        self.__Output('$file.output.basename.prefix'))
    self.Execute('dummy.psc -p ""')
    self.assertOutput('/cur/dummy.out', 'dummy')

  def testOutputBasenamePrefix_notEmpty(self):
    self.inputs['/cur/dummy.psc'] = (
        self.__Output('$file.output.basename.prefix'))
    self.Execute('dummy.psc -p custom-output-prefix')
    self.assertOutput('/cur/custom-output-prefix.out', 'custom-output-prefix')

  def testOutputBasenamePrefix_invalid_dirSeparator(self):
    self.Execute('dummy.psc -p dir/basename', expect_failure=True)
    self.assertIn('-p/--output-basename-prefix: expected basename without '
                  'separator, got: dir/basename',
                  self.GetStdFile('err'))
    self.assertEqual(self.fs.GetOutputs(), {})

  def testLibDir_custom(self):
    self.inputs['/cur/dummy.psc'] = self.__Output('$dir.lib')
    self.Execute('dummy.psc --lib-dir dir/sub')
    self.assertOutput('/cur/dummy.out', 'dir/sub')

  def testConstants(self):
    constants = {
        'dir.lib': '/pyscribe/lib',
        'dir.output': '/cur',
        'dir.input': '/cur',
        'dir.input.rel.output': '.',
        'file.input.basename': 'constants.psc',
        'file.input.basename.noext': 'constants',
        'file.output.basename.prefix': 'constants',
    }
    self.inputs['/cur/constants.psc'] = (
        self.__Output(', '.join(f'{name}=${name}' for name in constants)))
    self.Execute('constants.psc')
    self.assertOutput('/cur/constants.out',
                      ', '.join(f'{name}={value}'
                                for name, value in constants.items()))

  def testError_inputFileNotFound(self):
    self.Execute('does_not_exist', expect_failure=True)
    self.assertEqual(self.GetStdFile('err'),
                     "[Errno 2] File not found: '/cur/does_not_exist.psc'\n"
                     'Set --error_format=python for details.')
    self.assertEqual(self.fs.GetOutputs(), {})

  def testError_outputWriteError(self):
    self.Execute('input.psc -p not_writeable', expect_failure=True)
    self.assertEqual(self.GetStdFile('err'),
                     '/cur/input.psc:1: $branch.create.root:'
                     ' unable to write to file: /cur/not_writeable.out\n'
                     "[Errno 13] File not writeable: '/cur/not_writeable.out'\n"
                     'Set --error_format=python for details.')
    self.assertEqual(self.fs.GetOutputs(), {})

  def testError_renderBranchesFailure(self):
    self.inputs['/cur/render.psc'] = (
        self.__Output('$tag.open[div][block]test', branch_type='html'))
    self.Execute('render.psc --format html', expect_failure=True)
    self.assertOutput('/cur/render.out', '',
                      expected_err='element not closed in branch "root":'
                                   ' <div>\n'
                                   'Set --error_format=python for details.')


# Command-line to generated output file basename.
_DEFAULT_HTML_FLAGS = ' -d core.css.filename=../lib/core.css'
GOLDEN_TEST_DEFINITIONS = collections.OrderedDict((
  ('Hello.psc --format=latex', 'Hello.tex'),
  ('Hello.psc --format=html' + _DEFAULT_HTML_FLAGS, 'Hello.html'),
  ('Hello.psc --format=html'
      ' -d inline=1'
      ' -d core.css.filename=small.css'
      ' -p Hello-inline', 'Hello-inline.html'),
  ('Test.psc --format=html' + _DEFAULT_HTML_FLAGS, 'Test.html'),
  ('Test.psc --format=latex -d inline=1', 'Test.tex'),  # inline is a noop
))

class GoldenTest(EndToEndTestCase):

  def __Run(self, cmdline, output_basename):
    self.fs.cwd = self.fs.Path('/pyscribe/testdata')
    output_path = self.fs.cwd / output_basename
    self.Execute(cmdline)
    with self.OpenSourceFile(output_path) as expected_file:
      self.maxDiff = None
      self.assertOutput(str(output_path), expected_file.read())

  @classmethod
  def AddTestMethod(cls, cmdline, output_basename):
    setattr(cls, 'test_' + output_basename.replace(' ', '_'),
            lambda self: self.__Run(cmdline, output_basename))

for definition in GOLDEN_TEST_DEFINITIONS.items():
  GoldenTest.AddTestMethod(*definition)


class ComputePathConstantsTest(TestCase):

  def testAbsoluteInputPaths(self):
    fs = self.GetFileSystem({})
    self.assertEqual(pyscribe._ComputePathConstants(
                        fs=fs,
                        current_dir=fs.Path('/root/current/ignored'),
                        lib_dir=fs.Path('/pyscribe/lib'),
                        output_dir=fs.Path('/root/output'),
                        input_path=fs.Path('/root/input/sub/file.abc.psc'),
                        output_basename_prefix='outbn'),
                     {
                        'dir.lib': '/pyscribe/lib',
                        'dir.output': '/root/output',
                        'dir.input': '/root/input/sub',
                        'dir.input.rel.output': '../input/sub',
                        'file.input.basename': 'file.abc.psc',
                        'file.input.basename.noext': 'file.abc',
                        'file.output.basename.prefix': 'outbn',
                     })

  def testRelativeInputPaths(self):
    fs = self.GetFileSystem({})
    self.assertEqual(pyscribe._ComputePathConstants(
                        fs=fs,
                        current_dir=fs.Path('/root/current'),
                        lib_dir=fs.Path('..'),
                        output_dir=fs.Path('output'),
                        input_path=fs.Path('/root/current/file.abc.psc'),
                        output_basename_prefix=''),
                     {
                        'dir.lib': '..',
                        'dir.output': '/root/current/output',
                        'dir.input': '/root/current',
                        'dir.input.rel.output': '..',
                        'file.input.basename': 'file.abc.psc',
                        'file.input.basename.noext': 'file.abc',
                        'file.output.basename.prefix': 'file.abc',
                     })


if __name__ == '__main__':
  unittest.main()
