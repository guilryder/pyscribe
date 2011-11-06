#!/usr/bin/env python
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

from optparse import OptionParser
import shlex
from StringIO import StringIO
import sys

import log
from pyscribe import Main
from testutils import *


class MainTest(TestCase):

  def setUp(self):
    super(MainTest, self).setUp()
    self.std_output = StringIO()
    def Output(contents):
      return ('$branch.create.root[text][root][output.txt]' +
              '$branch.write[root][' + contents + ']')

    self.fs = self.GetFileSystem({
        '/cur/input.psc': Output('Hello, World!'),
        '/cur/format.psc': Output('Format: $output.format'),
        '/cur/defines.psc': Output('$one,$two,$three,$a.b'),
        '/cur/error.psc':
            '$invalid',
    })

  def GetStdOutput(self):
    return self.std_output.getvalue().strip()

  def assertOutput(self, expected_output):
    self.assertEqual('', self.GetStdOutput())
    self.assertEqual({'/cur/output/output.txt': expected_output},
                     self.fs.GetOutputs())

  def Execute(self, cmdline):
    class FakeOptionParser(OptionParser):
      """Option parser that prints to self.std_output."""
      def exit(parser, status=0, msg=None, **kwargs):
        self.std_output.write(msg)
        sys.exit(status)

      def error(parser, msg):
        parser.exit(2, "error: %s\n" % msg)

      def print_help(parser, file=None, **kwargs):
        OptionParser.print_help(parser, self.std_output , **kwargs)

    class TestLogger(log.Logger):
      def __init__(logger, *args, **kwargs):
        super(TestLogger, logger).__init__(*args, output_file=self.std_output,
                                           **kwargs)

    args = shlex.split(cmdline)
    Main(args, self.fs, FakeOptionParser, TestLogger).Run()

  def testNoArguments(self):
    self.assertRaises(SystemExit, self.Execute, '')
    self.assertEqual('error: expected one argument', self.GetStdOutput())
    self.assertEqual({}, self.fs.GetOutputs())

  def testTwoArguments(self):
    self.assertRaises(SystemExit, self.Execute, 'first second')
    self.assertEqual('error: expected one argument', self.GetStdOutput())
    self.assertEqual({}, self.fs.GetOutputs())

  def testHelp(self):
    self.assertRaises(SystemExit, self.Execute, '--help')
    self.assertIn('Usage', self.GetStdOutput())
    self.assertEqual({}, self.fs.GetOutputs())

  def testSimple(self):
    self.Execute('input.psc')
    self.assertOutput('Hello, World!')

  def testCustomOutput(self):
    self.Execute('input.psc --output /custom')
    self.assertEqual('', self.GetStdOutput())
    self.assertEqual({'/custom/output.txt': 'Hello, World!'},
                     self.fs.GetOutputs())

  def testExecutionError(self):
    self.Execute('error.psc')
    self.assertEqual('/cur/error.psc:1: macro not found: $invalid',
                     self.GetStdOutput())
    self.assertEqual({}, self.fs.GetOutputs())

  def testCustomErrorFormat(self):
    self.Execute('error.psc --error_format python')
    self.assertEqual('File "/cur/error.psc", line 1\n' +
                     '    macro not found: $invalid',
                     self.GetStdOutput())
    self.assertEqual({}, self.fs.GetOutputs())

  def testDefaultOutputFormat(self):
    self.Execute('format.psc')
    self.assertOutput('Format:')

  def testCustomOutputFormat(self):
    self.Execute('format.psc --format xhtml')
    self.assertOutput('Format: xhtml')

  def testDefines(self):
    self.Execute('defines.psc -d one=1 -d two=2 -d three= -d two=2bis -d a.b=c')
    self.assertOutput('1,2bis,,c')

  def testDefinesInvalidFormat(self):
    self.assertRaises(SystemExit, self.Execute, 'defines.psc -d name')
    self.assertIn('-d option expects format: name=text; got: name',
                  self.GetStdOutput())

  def testOutputFormatOverwritesDefines(self):
    self.Execute('format.psc --format xhtml -d output.format=ignored')
    self.assertOutput('Format: xhtml')


if __name__ == '__main__':
  unittest.main()
