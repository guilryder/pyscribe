#!/usr/bin/env python
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

from log import *
from testutils import *


class FormatMessageTest(TestCase):

  def testNoneMessage(self):
    self.assertEqual('unknown error', FormatMessage(None))

  def testEmptyMessage(self):
    self.assertEqual('unknown error', FormatMessage(''))

  def testMessageOnly(self):
    self.assertEqual('message {blah}', FormatMessage('message {blah}'))

  def testMessageAndArgs(self):
    self.assertEqual('message arg', FormatMessage('message {blah}', blah='arg'))


class ExceptionTestCase(TestCase):

  def testNoArgs(self):
    self.assertEqual('unknown error', self.exception().message)

  def testEmptyMessage(self):
    self.assertEqual('unknown error', self.exception('').message)

  def testMessageOnly(self):
    self.assertEqual('message {blah}',
                     self.exception('message {blah}').message)

  def testMessageAndArgs(self):
    self.assertEqual('message arg',
                     self.exception('message {blah}', blah='arg').message)

  def testStr(self):
    self.assertEqual('message arg',
                     str(self.exception('message {blah}', blah='arg')))


class FatalErrorTest(ExceptionTestCase):

  exception = FatalError


class InternalErrorTest(ExceptionTestCase):

  exception = InternalError


class FilenameTest(TestCase):

  test_filename = Filename('file.txt', '/cur')

  def testStr(self):
    self.assertEqual('file.txt', str(self.test_filename))

  def testEq(self):
    self.assertEqual(Filename('file.txt', '/cur'), self.test_filename)
    self.assertNotEqual(Filename('other.txt', '/cur'), self.test_filename)
    self.assertNotEqual(Filename('file.txt', '/'), self.test_filename)


class LocationTest(TestCase):

  def testRepr(self):
    self.assertEqual('file.txt:42', repr(test_location))

  def testEq(self):
    self.assertEqual(Location(Filename('file.txt', '/cur'), 42), test_location)
    self.assertNotEqual(Location(Filename('other.txt', '/'), 42), test_location)
    self.assertNotEqual(Location(test_location.filename, 43), test_location)


class LoggerTest(TestCase):

  def setUp(self):
    super(LoggerTest, self).setUp()
    self.output_file = self.FakeOutputFile()

  def assertOutput(self, expected_lines):
    self.assertEqual('\n'.join(expected_lines + ['']),
                     self.output_file.getvalue())

  def testLog_simpleFormat(self):
    logger = Logger(Logger.FORMATS['simple'], self.output_file)
    logger.Log(Location(Filename('file.txt', '/'), 42), 'one')
    logger.Log(Location(Filename('other.txt', '/'), 27), 'two')
    self.assertOutput(['file.txt:42: one', 'other.txt:27: two'])

  def testLog_pythonFormat(self):
    logger = Logger(Logger.FORMATS['python'], self.output_file)
    logger.Log(Location(Filename('file.txt', '/'), 42), 'one')
    logger.Log(Location(Filename('other.txt', '/'), 27), 'two')
    self.assertOutput(['  File "file.txt", line 42\n    one',
                       '  File "other.txt", line 27\n    two'])

  def testLog_someArgs(self):
    logger = Logger(Logger.FORMATS['simple'], self.output_file)
    logger.Log(test_location, 'arg={arg}; {number}', arg='value', number=42)
    self.assertOutput(['file.txt:42: arg=value; 42'])


if __name__ == '__main__':
  unittest.main()
