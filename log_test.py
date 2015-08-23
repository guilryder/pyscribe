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


class Helpers:
  class ExceptionClassTestCase(TestCase):

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


class FatalErrorTest(Helpers.ExceptionClassTestCase):

  exception = FatalError


class InternalErrorTest(Helpers.ExceptionClassTestCase):

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
    self.err_file = self.FakeOutputFile()
    self.info_file = self.FakeOutputFile()

  def __CreateLogger(self, **kwargs):
    # pylint: disable=missing-kwoa
    kwargs.setdefault('fmt', Logger.FORMATS['simple'])
    kwargs.setdefault('err_file', self.err_file)
    kwargs.setdefault('info_file', self.info_file)
    return Logger(**kwargs)

  def assertOutputs(self, err=(), info=()):
    for file, expected_lines in ((self.err_file, err), (self.info_file, info)):
      self.assertEqual(file.getvalue(),
                       '\n'.join(list(expected_lines) + ['']))
      file.close()

  def testLogLocation_simpleFormat(self):
    logger = self.__CreateLogger(fmt=Logger.FORMATS['simple'])
    logger.LogLocation(Location(Filename('file.txt', '/'), 42), 'one')
    logger.LogLocation(Location(Filename('other.txt', '/'), 27), 'two')
    self.assertOutputs(err=['file.txt:42: one', 'other.txt:27: two'])

  def testLogLocation_pythonFormat(self):
    logger = self.__CreateLogger(fmt=Logger.FORMATS['python'])
    logger.LogLocation(Location(Filename('file.txt', '/'), 42), 'one')
    logger.LogLocation(Location(Filename('other.txt', '/'), 27), 'two')
    self.assertOutputs(err=['  File "file.txt", line 42\n    one',
                            '  File "other.txt", line 27\n    two'])

  def testLogLocation_someArgs(self):
    logger = self.__CreateLogger(fmt=Logger.FORMATS['simple'])
    logger.LogLocation(test_location, 'arg={arg}; {number}',
                       arg='value', number=42)
    self.assertOutputs(err=['file.txt:42: arg=value; 42'])

  def testLogInfo_enabled(self):
    logger = self.__CreateLogger()
    logger.LogInfo('one')
    logger.LogInfo('two')
    self.assertOutputs(info=['one', 'two'])

  def testLogInfo_disabled(self):
    logger = self.__CreateLogger(info_file=None)
    logger.LogInfo('one')
    logger.LogInfo('two')
    self.assertOutputs(info=[])


if __name__ == '__main__':
  unittest.main()
