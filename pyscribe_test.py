#!/usr/bin/env python3
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

import io
from argparse import ArgumentParser
import shlex
import sys

from pyscribe import Main
from testutils import *


class MainTest(TestCase):

  def setUp(self):
    super(MainTest, self).setUp()
    def Output(contents):
      return ('$branch.create.root[text][root][output.txt]' +
              '$branch.write[root][' + contents + ']')

    self.fs = self.GetFileSystem({
        '/cur/input.psc': Output('Hello, World!'),
        '/cur/format.psc': Output('Format: $output.format'),
        '/cur/defines.psc': Output('$one,$two,$three,$a.b'),
        '/cur/error.psc': '$invalid',
    })
    self.fs.stdout = io.StringIO()
    self.fs.stderr = io.StringIO()

  def GetStdFile(self, name):
    return getattr(self.fs, 'std' + name).getvalue().strip()

  def assertOutput(self, expected_output):
    self.assertEqual(self.GetStdFile('err'), '')
    self.assertEqual(self.fs.GetOutputs(),
                     {'/cur/output/output.txt': expected_output})

  def Execute(self, cmdline):
    # pylint: disable=no-self-argument
    class FakeArgumentParser(ArgumentParser):
      """Option parser that prints to self.stderr."""
      def exit(parser, status=0, msg='', **unused_kwargs):
        self.fs.stderr.write(msg)
        sys.exit(status)

      def error(parser, msg):
        parser.exit(2, "error: %s\n" % msg)

      def print_help(parser, file=None, **kwargs):
        ArgumentParser.print_help(parser, self.fs.stderr, **kwargs)

    args = shlex.split(cmdline)
    Main(args, self.fs, FakeArgumentParser).Run()

  def testNoArguments(self):
    with self.assertRaises(SystemExit):
      self.Execute('')
    self.assertEqual(self.GetStdFile('err'),
                     'error: the following arguments are required: filename')
    self.assertEqual(self.fs.GetOutputs(), {})

  def testTwoArguments(self):
    with self.assertRaises(SystemExit):
      self.Execute('first second')
    self.assertEqual(self.GetStdFile('err'),
                     'error: unrecognized arguments: second')
    self.assertEqual(self.fs.GetOutputs(), {})

  def testHelp(self):
    with self.assertRaises(SystemExit):
      self.Execute('--help')
    self.assertIn('usage', self.GetStdFile('err'))
    self.assertEqual(self.fs.GetOutputs(), {})

  def testSimple(self):
    self.Execute('input.psc')
    self.assertOutput('Hello, World!')
    self.assertEqual(self.GetStdFile('out'),
                     'Writing: /cur/output/output.txt')

  def testSimple_autoExtension(self):
    self.Execute('input')
    self.assertOutput('Hello, World!')

  def testSimple_quiet(self):
    self.Execute('input.psc -q')
    self.assertOutput('Hello, World!')
    self.assertEqual(self.GetStdFile('out'), '')

  def testCustomOutput(self):
    self.Execute('input.psc --output /custom')
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
    with self.assertRaises(SystemExit):
      self.Execute('error.psc')
    self.assertEqual(self.GetStdFile('err'),
                     '/cur/error.psc:1: macro not found: $invalid')
    self.assertEqual(self.fs.GetOutputs(), {})

  def testCustomErrorFormat(self):
    with self.assertRaises(SystemExit):
      self.Execute('error.psc --error_format python')
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
    self.Execute('defines.psc -d one=1 -d two=2 -d three= -d two=2bis -d a.b=c')
    self.assertOutput('1,2bis,,c')

  def testDefinesInvalidFormat(self):
    with self.assertRaises(SystemExit):
      self.Execute('defines.psc -d name')
    self.assertIn('-d/--define: invalid value, expected format: ' +
                  'name=text; got: name',
                  self.GetStdFile('err'))

  def testOutputFormatOverwritesDefines(self):
    self.Execute('format.psc --format xhtml -d output.format=ignored')
    self.assertOutput('Format: xhtml')


if __name__ == '__main__':
  unittest.main()
