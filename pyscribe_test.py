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
    self.fs = self.GetFileSystem({
        '/cur/input.psc':
            '$branch.create.root[text][root][output.txt]' +
            '$branch.write[root][Hello, World!]',
        '/cur/error.psc':
            '$invalid',
    })

  def GetStdOutput(self):
    return self.std_output.getvalue().strip()

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
    self.assert_('Usage' in self.GetStdOutput())
    self.assertEqual({}, self.fs.GetOutputs())

  def testSimple(self):
    self.Execute('input.psc')
    self.assertEqual('', self.GetStdOutput())
    self.assertEqual({'/cur/output/output.txt': 'Hello, World!'},
                     self.fs.GetOutputs())

  def testCustomOutput(self):
    self.Execute('input.psc --output /custom')
    self.assertEqual('', self.GetStdOutput())
    self.assertEqual({'/custom/output.txt': 'Hello, World!'},
                     self.fs.GetOutputs())

  def testExecutionError(self):
    self.Execute('error.psc')
    self.assertEqual('File "/cur/error.psc", line 1\n' +
                     '    macro not found: $invalid',
                     self.GetStdOutput())
    self.assertEqual({}, self.fs.GetOutputs())

  def testCustomErrorFormat(self):
    self.Execute('error.psc --error_format simple')
    self.assertEqual('/cur/error.psc:1: macro not found: $invalid',
                     self.GetStdOutput())
    self.assertEqual({}, self.fs.GetOutputs())

if __name__ == '__main__':
  unittest.main()
