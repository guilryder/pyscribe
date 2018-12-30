#!/usr/bin/env python3
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

from argparse import ArgumentParser
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

  def assertOutput(self, expected_output, expected_filename='/cur/output.txt'):
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
    return ('$branch.create.root[text][root][output.txt]' +
            '$branch.write[root][' + contents + ']')

  def setUp(self):
    super(MainTest, self).setUp()
    self.inputs.update({
        '/cur/input.psc': self.__Output('Hello, World!'),
        '/cur/format.psc': self.__Output('Format: $output.format'),
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
    self.assertOutput('Hello, World!')
    self.assertEqual(self.GetStdFile('out'),
                     'Writing: /cur/output.txt')

  def testSimple_autoExtension(self):
    self.Execute('input')
    self.assertOutput('Hello, World!')

  def testSimple_quiet(self):
    self.Execute('input.psc -q')
    self.assertOutput('Hello, World!')
    self.assertEqual(self.GetStdFile('out'), '')

  def testCustomOutput(self):
    self.Execute('input.psc --output /custom')
    self.assertEqual(self.fs.created_dirs, set(['/custom']))
    self.assertEqual(self.GetStdFile('out'),
                     'Writing: /custom/output.txt')
    self.assertEqual(self.GetStdFile('err'), '')
    self.assertEqual(self.fs.GetOutputs(),
                     {'/custom/output.txt': 'Hello, World!'})

  def testCustomOutput_quiet(self):
    self.Execute('input.psc --output /custom --quiet')
    self.assertEqual(self.GetStdFile('out'), '')
    self.assertEqual(self.GetStdFile('err'), '')
    self.assertEqual(self.fs.GetOutputs(),
                     {'/custom/output.txt': 'Hello, World!'})

  def testExecutionError(self):
    self.Execute('error.psc', expect_failure=True)
    self.assertEqual(self.GetStdFile('err'),
                     '/cur/error.psc:1: macro not found: $invalid')
    self.assertEqual(self.fs.GetOutputs(), {})

  def testCustomErrorFormat(self):
    self.Execute('error.psc --error_format python', expect_failure=True)
    self.assertEqual(self.GetStdFile('err'),
                     'File "/cur/error.psc", line 1\n' +
                     '    macro not found: $invalid')
    self.assertEqual(self.fs.GetOutputs(), {})

  def testDefaultOutputFormat(self):
    self.Execute('format.psc')
    self.assertOutput('Format: ')

  def testCustomOutputFormat(self):
    self.Execute('format.psc --format xhtml')
    self.assertOutput('Format: xhtml')

  def testDefines(self):
    self.inputs['/cur/defines.psc'] = self.__Output('$one,$two,$three,$a.b')
    self.Execute('defines.psc -d one=1 -d two=2 -d three= -d two=2bis -d a.b=c')
    self.assertOutput('1,2bis,,c')

  def testDefinesInvalidFormat(self):
    self.Execute('input.psc -d name', expect_failure=True)
    self.assertIn('-d/--define: invalid value, expected format: ' +
                  'name=text; got: name',
                  self.GetStdFile('err'))

  def testOutputFormatOverwritesDefines(self):
    self.Execute('format.psc --format xhtml -d output.format=ignored')
    self.assertOutput('Format: xhtml')

  def testConstants(self):
    constants = {
        'dir.lib': '/pyscribe/usage',
        'dir.lib.rel.output': '../pyscribe/usage',
        'dir.output': '/cur',
        'dir.source': '/cur',
        'dir.source.rel.output': '.',
    }
    self.inputs['/cur/constants.psc'] = \
        self.__Output(', '.join('{0}=${0}'.format(name) for name in constants))
    self.Execute('constants.psc')
    self.assertOutput(', '.join('{}={}'.format(*constant)
                                for constant in constants.items()))


# Command-line to generated output file basename.
GOLDEN_TEST_DEFINITIONS = {
  'test.psc --format=xhtml': 'Test.html',
  'test.psc --format=latex': 'Test.tex',
}

class GoldenTest(EndToEndTestCase):

  def __Run(self, cmdline, output_basename):
    output_path = '/pyscribe/testdata/' + output_basename
    self.fs.cwd = '/pyscribe/testdata'
    self.Execute(cmdline)
    with self.OpenSourceFile(output_path) as expected_file:
      self.maxDiff = None
      self.assertOutput(expected_file.read(), expected_filename=output_path)

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
                        cur_dir='/root/current/ignored',
                        lib_dir='/pyscribe/usage',
                        out_dir='/root/output',
                        input_filename='/root/input/sub/file.psc'),
                     {
                        'dir.lib': '/pyscribe/usage',
                        'dir.lib.rel.output': '../../pyscribe/usage',
                        'dir.output': '/root/output',
                        'dir.source': '/root/input/sub',
                        'dir.source.rel.output': '../input/sub',
                     })

  def testRelativeInputPaths(self):
    self.assertEqual(pyscribe._ComputePathConstants(
                        fs=self.GetFileSystem({}),
                        cur_dir='/root/current',
                        lib_dir='..',
                        out_dir='output',
                        input_filename='file.psc'),
                     {
                        'dir.lib': '/root',
                        'dir.lib.rel.output': '../..',
                        'dir.output': '/root/current/output',
                        'dir.source': '/root/current',
                        'dir.source.rel.output': '..',
                     })


if __name__ == '__main__':
  unittest.main()
