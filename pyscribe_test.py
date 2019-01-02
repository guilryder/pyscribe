#!/usr/bin/env python3
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

from argparse import ArgumentParser
import collections
import shlex
import sys

import pyscribe
from testutils import *


class EndToEndTestCase(TestCase):

  def setUp(self):
    super(EndToEndTestCase, self).setUp()
    self.inputs = {}
    self.fs = self.GetFileSystem(self.inputs)
    self.fs.InitializeForWrites()

  def GetStdFile(self, name):
    return getattr(self.fs, 'std' + name).getvalue().strip()

  def assertOutput(self, expected_filename, expected_output):
    self.assertEqual(self.GetStdFile('err'), '')
    self.assertEqual(self.fs.GetOutputs(),
                     {expected_filename: expected_output})

  def Execute(self, cmdline, expect_failure=False):
    # pylint: disable=no-self-argument
    class FakeArgumentParser(ArgumentParser):
      """Option parser that prints to self.stderr."""
      # pylint: disable=arguments-differ
      def exit(parser, status=0, msg='', **unused_kwargs):
        self.fs.stderr.write(msg)
        sys.exit(status)

      def error(parser, msg):
        parser.exit(2, "error: {}\n".format(msg))

      def print_help(parser, file=None, **kwargs):
        ArgumentParser.print_help(parser, self.fs.stderr, **kwargs)

    args = shlex.split(cmdline)
    main = pyscribe.Main(args,
                         fs=self.fs,
                         main_file=FAKE_PYSCRIBE_DIR + 'pyscribe.py',
                         ArgumentParser=FakeArgumentParser)
    if expect_failure:
      with self.assertRaises(SystemExit):
        main.Run()
    else:
      try:
        main.Run()
      except SystemExit as e:  # pragma: no cover
        msg = 'Unexpected error:\n{}'.format(self.GetStdFile('err'))
        raise AssertionError(msg) from e


class MainTest(EndToEndTestCase):

  @staticmethod
  def __Output(contents):
    return ('$branch.create.root[text][root][.out]' +
            '$branch.write[root][' + contents + ']')

  def setUp(self):
    super(MainTest, self).setUp()
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
    self.assertIn('usage', self.GetStdFile('err'))
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
    self.assertEqual(self.fs.created_dirs, set(['/cur/custom']))
    self.assertEqual(self.GetStdFile('out'),
                     'Writing: /cur/custom/input.out')
    self.assertEqual(self.GetStdFile('err'), '')
    self.assertEqual(self.fs.GetOutputs(),
                     {'/cur/custom/input.out': 'Hello, World!'})

  def testCustomOutput_absolute(self):
    self.Execute('input.psc --output /custom')
    self.assertEqual(self.fs.created_dirs, set(['/custom']))
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
                     '/cur/error.psc:1: macro not found: $invalid')
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
    self.inputs['/cur/dummy.psc'] = \
        self.__Output('$file.output.basename.prefix')
    self.Execute('dummy.psc -p ""')
    self.assertOutput('/cur/dummy.out', 'dummy')

  def testOutputBasenamePrefix_notEmpty(self):
    self.inputs['/cur/dummy.psc'] = \
        self.__Output('$file.output.basename.prefix')
    self.Execute('dummy.psc -p custom-output-prefix')
    self.assertOutput('/cur/custom-output-prefix.out', 'custom-output-prefix')

  def testOutputBasenamePrefix_invalid_dirSeparator(self):
    self.Execute('dummy.psc -p dir/basename', expect_failure=True)
    self.assertIn('-p/--output-basename-prefix: expected basename without '
                  'separator, got: dir/basename',
                  self.GetStdFile('err'))
    self.assertEqual(self.fs.GetOutputs(), {})

  def testConstants(self):
    constants = {
        'dir.lib': '/pyscribe/usage',
        'dir.lib.rel.output': '../pyscribe/usage',
        'dir.output': '/cur',
        'dir.input': '/cur',
        'dir.input.rel.output': '.',
        'file.input.basename': 'constants.psc',
        'file.input.basename.noext': 'constants',
        'file.output.basename.prefix': 'constants',
    }
    self.inputs['/cur/constants.psc'] = \
        self.__Output(', '.join('{0}=${0}'.format(name) for name in constants))
    self.Execute('constants.psc')
    self.assertOutput('/cur/constants.out',
                      ', '.join('{}={}'.format(*constant)
                                for constant in constants.items()))


# Command-line to generated output file basename.
GOLDEN_TEST_DEFINITIONS = collections.OrderedDict((
  ('Hello.psc --format=latex', 'Hello.tex'),
  ('Hello.psc --format=html', 'Hello.html'),
  ('Hello.psc --format=html'
      ' -d inline=1'
      ' -d core.css.filename=small.css'
      ' -p Hello-inline', 'Hello-inline.html'),
  ('Test.psc --format=html', 'Test.html'),
  ('Test.psc --format=latex -d inline=1', 'Test.tex'),  # inline is a noop
))

class GoldenTest(EndToEndTestCase):

  def __Run(self, cmdline, output_basename):
    output_path = '/pyscribe/testdata/' + output_basename
    self.fs.cwd = '/pyscribe/testdata'
    self.Execute(cmdline)
    with self.OpenSourceFile(output_path) as expected_file:
      self.maxDiff = None
      self.assertOutput(output_path, expected_file.read())

  @classmethod
  def AddTestMethod(cls, cmdline, output_basename):
    setattr(cls, 'test_' + output_basename.replace(' ', '_'),
            lambda self: self.__Run(cmdline, output_basename))

for definition in GOLDEN_TEST_DEFINITIONS.items():
  GoldenTest.AddTestMethod(*definition)


class ComputePathConstantsTest(TestCase):

  def testAbsoluteInputPaths(self):
    self.assertEqual(pyscribe._ComputePathConstants(
                        fs=self.GetFileSystem({}),
                        current_dir='/root/current/ignored',
                        lib_dir='/pyscribe/usage',
                        output_dir='/root/output',
                        input_path='/root/input/sub/file.abc.psc',
                        output_basename_prefix='outbn'),
                     {
                        'dir.lib': '/pyscribe/usage',
                        'dir.lib.rel.output': '../../pyscribe/usage',
                        'dir.output': '/root/output',
                        'dir.input': '/root/input/sub',
                        'dir.input.rel.output': '../input/sub',
                        'file.input.basename': 'file.abc.psc',
                        'file.input.basename.noext': 'file.abc',
                        'file.output.basename.prefix': 'outbn',
                     })

  def testRelativeInputPaths(self):
    self.assertEqual(pyscribe._ComputePathConstants(
                        fs=self.GetFileSystem({}),
                        current_dir='/root/current',
                        lib_dir='..',
                        output_dir='output',
                        input_path='/root/current/file.abc.psc',
                        output_basename_prefix=''),
                     {
                        'dir.lib': '/root',
                        'dir.lib.rel.output': '../..',
                        'dir.output': '/root/current/output',
                        'dir.input': '/root/current',
                        'dir.input.rel.output': '..',
                        'file.input.basename': 'file.abc.psc',
                        'file.input.basename.noext': 'file.abc',
                        'file.output.basename.prefix': 'file.abc',
                     })


if __name__ == '__main__':
  unittest.main()
