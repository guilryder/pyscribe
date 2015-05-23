#!/usr/bin/env python
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

from abc import abstractmethod

from log import *
from testutils import *


class FormatMessageTest(TestCase):

  def testNoneMessage(self):
    self.assertEqual(FormatMessage(None), 'unknown error')

  def testEmptyMessage(self):
    self.assertEqual(FormatMessage(''), 'unknown error')

  def testMessageOnly(self):
    self.assertEqual(FormatMessage('message {blah}'), 'message {blah}')

  def testMessageAndArgs(self):
    self.assertEqual(FormatMessage('message {blah}', blah='arg'), 'message arg')


class ExceptionTestCase(TestCase):

  @abstractmethod
  def exception(self, *unused_args, **unused_kwargs):
    pass  # pragma: no cover

  def testNoArgs(self):
    self.assertEqual(self.exception().message, 'unknown error')

  def testEmptyMessage(self):
    self.assertEqual(self.exception('').message, 'unknown error')

  def testMessageOnly(self):
    self.assertEqual(self.exception('message {blah}').message,
                     'message {blah}')

  def testMessageAndArgs(self):
    self.assertEqual(self.exception('message {blah}', blah='arg').message,
                     'message arg')

  def testStr(self):
    self.assertEqual(str(self.exception('message {blah}', blah='arg')),
                     'message arg')


class FatalErrorTest(ExceptionTestCase):

  exception = FatalError


class InternalErrorTest(ExceptionTestCase):

  exception = InternalError


class FilenameTest(TestCase):

  test_filename = Filename('file.txt', '/cur')

  def testStr(self):
    self.assertEqual(str(self.test_filename), 'file.txt')

  def testEq(self):
    self.assertEqual(self.test_filename, Filename('file.txt', '/cur'))
    self.assertNotEqual(self.test_filename, Filename('other.txt', '/cur'))
    self.assertNotEqual(self.test_filename, Filename('file.txt', '/'))


class LocationTest(TestCase):

  def testRepr(self):
    self.assertEqual(repr(test_location), 'file.txt:42')

  def testEq(self):
    self.assertEqual(test_location, Location(Filename('file.txt', '/cur'), 42))
    self.assertNotEqual(test_location, Location(Filename('other.txt', '/'), 42))
    self.assertNotEqual(test_location, Location(test_location.filename, 43))


class LoggerTest(TestCase):

  def setUp(self):
    super(LoggerTest, self).setUp()
    self.output_file = self.FakeOutputFile()

  def assertOutput(self, expected_lines):
    self.assertEqual(self.output_file.getvalue(),
                     '\n'.join(expected_lines + ['']))
    self.output_file.close()

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
