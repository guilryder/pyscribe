#!/usr/bin/env python3
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

from abc import abstractmethod
import pathlib
import sys

import log
from log import Filename, Location
import parsing
import testutils
from testutils import TEST_LOCATION


class FormatMessageTest(testutils.TestCase):

  def testNoneMessage(self):
    self.assertEqual(log.FormatMessage(None), 'unknown error')

  def testEmptyMessage(self):
    self.assertEqual(log.FormatMessage(''), 'unknown error')

  def testStringMessage(self):
    self.assertEqual(log.FormatMessage('message {blah}'), 'message {blah}')

  def testException(self):
    self.assertEqual(log.FormatMessage(OSError(5, 'Fake', 'file')),
                     "[Errno 5] Fake: 'file'")


class Helpers:
  class ExceptionClassTestCase(testutils.TestCase):

    @abstractmethod
    def exception(self, *unused_args):
      raise NotImplementedError

    def testNoneMessage(self):
      self.assertEqual(self.exception().message, 'unknown error')

    def testEmptyMessage(self):
      self.assertEqual(self.exception('').message, 'unknown error')

    def testStringMessage(self):
      self.assertEqual(self.exception('message {blah}').message,
                       'message {blah}')

    def testStr(self):
      self.assertEqual(str(self.exception('message {blah}')), 'message {blah}')


class FatalErrorTest(Helpers.ExceptionClassTestCase):

  exception = log.FatalError


class NodeErrorTest(Helpers.ExceptionClassTestCase):

  exception = log.NodeError


class FilenameTest(testutils.TestCase):

  test_filename = Filename('file.txt', '/cur')

  def testPathConstructor(self):
    filename = Filename(pathlib.PurePosixPath('file.txt'),
                        pathlib.PurePosixPath('/cur'))
    self.assertEqual(filename.display_path, 'file.txt')
    self.assertEqual(filename.dir_path, '/cur')

  def testStr(self):
    self.assertEqual(str(self.test_filename), 'file.txt')

  def testEq(self):
    self.assertEqual(self.test_filename, Filename('file.txt', '/cur'))
    self.assertNotEqual(self.test_filename, Filename('other.txt', '/cur'))
    self.assertNotEqual(self.test_filename, Filename('file.txt', '/'))


class LocationTest(testutils.TestCase):

  def testRepr(self):
    self.assertEqual(repr(TEST_LOCATION), 'file.txt:42')

  def testEq(self):
    self.assertEqual(TEST_LOCATION, Location(Filename('file.txt', '/cur'), 42))
    self.assertNotEqual(TEST_LOCATION, Location(Filename('other.txt', '/'), 42))
    self.assertNotEqual(TEST_LOCATION, Location(TEST_LOCATION.filename, 43))


class LoggerTest(testutils.TestCase):

  def setUp(self):
    super().setUp()
    self.err_file = self.FakeOutputFile()
    self.info_file = self.FakeOutputFile()

  def __CreateLogger(self, **kwargs):
    kwargs.setdefault('fmt', 'simple')
    kwargs.setdefault('err_file', self.err_file)
    kwargs.setdefault('info_file', self.info_file)
    return log.Logger(**kwargs)

  @staticmethod
  def __LogMaximalLocationError(logger):
    e = logger.LocationError(
        TEST_LOCATION, 'message {ignored tag}',
        call_stack=(
            parsing.CallNode(testutils.loc('file1.txt', 1), 'one', []),
            parsing.CallNode(testutils.loc('file2.txt', 2), 'two', [])))
    try:
      raise RuntimeError('fake error')
    except RuntimeError:
      exc_info = sys.exc_info()
    else:
      exc_info = (None, None, None)  # pragma: no cover
    logger.LogException(e, exc_info=exc_info, tb_limit=0)

  def assertOutputs(self, err=(), info=()):
    for file, expected_lines in ((self.err_file, err), (self.info_file, info)):
      output = file.getvalue()
      # Workaround for traceback.print_exception() behavior inconsistencies
      # across Python versions: skip the "Traceback" line systematically.
      output = output.replace('Traceback (most recent call last):\n', '')
      self.assertEqual(output, '\n'.join(list(expected_lines) + ['']))
      file.close()

  def testLocationError_simpleFormat_minimal(self):
    logger = self.__CreateLogger(fmt='simple')
    e = logger.LocationError(TEST_LOCATION, 'message')
    self.assertEqual(e.message, 'file.txt:42: message')

  def testLocationError_simpleFormat_maximal(self):
    logger = self.__CreateLogger(fmt='simple')
    self.__LogMaximalLocationError(logger)
    self.assertOutputs(err=[
        'file.txt:42: message {ignored tag}',
        '  file1.txt:1: $one',
        '  file2.txt:2: $two',
        'Set --error_format=python for details.',
    ])

  def testLocationError_pythonFormat_minimal(self):
    logger = self.__CreateLogger(fmt='python')
    e = logger.LocationError(TEST_LOCATION, 'message')
    self.assertEqual(e.message, '  File "file.txt", line 42\n'
                                '    message')

  def testLocationError_pythonFormat_maximal(self):
    logger = self.__CreateLogger(fmt='python')
    self.__LogMaximalLocationError(logger)
    self.assertOutputs(err=[
        '  File "file.txt", line 42',
        '    message {ignored tag}',
        '  File "file1.txt", line 1, in $one',
        '  File "file2.txt", line 2, in $two',
        'RuntimeError: fake error',
    ])

  def testLogException_fromLocationError(self):
    logger = self.__CreateLogger(fmt='simple')
    logger.LogException(logger.LocationError(TEST_LOCATION, 'message'))
    self.assertOutputs(err=['file.txt:42: message'])

  def testLogException_inSequence(self):
    logger = self.__CreateLogger(fmt='simple')
    logger.LogException(log.FatalError('error 1\n'))
    logger.LogException(log.FatalError('error 2\n'))
    self.assertOutputs(err=['error 1', 'error 2'])

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
  testutils.unittest.main()
