#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

import collections
import io
import os
from StringIO import StringIO
import unittest

from executor import Branch, Executor
from log import *
from macros import macro, GetPublicMacros
import tests  # for unittest hooks


def loc(display_path, lineno, dir_path='/cur'):
  return Location(Filename(display_path, dir_path), lineno)

test_location = loc('file.txt', 42)
test_unicode = u'Îñţérñåţîöñåļîžåţîöñ'
special_chars = ' '.join((
    "% & _ `$ $text.dollar `# $text.hash",
    "a~b",
    "--c---",
    "d...",
    "<<e>>",
    "<< f >>",
    "'g'h'",
    "i ! j: k ; l?",
    "m!:;?",
))


class FakeLogger(Logger):

  """
  Records logged entries in a string buffer.

  Example output: GetOutput() == 'file.txt:42: some error'
  """

  FORMAT = (
      u'{location!r}: {message}\n',
      u'  {call_node.location!r}: ${call_node.name}\n')

  def __init__(self):
    self.output_file = StringIO()
    super(FakeLogger, self).__init__(self.FORMAT, self.output_file)

  def GetOutput(self):
    """Returns the text logged so far, then clears it."""
    output = self.output_file.getvalue().strip()
    self.Clear()
    return output

  def Clear(self):
    """Clears the log cache."""
    self.output_file.truncate(0)


class FakeFileSystem(object):

  __cwd = '/cur'

  def __unixpath(self, path):
    return path.replace(os.sep, '/')

  def dirname(self, path):
    return self.__unixpath(os.path.dirname(path))

  def getcwd(self):
    return self.__cwd

  def join(self, path1, *paths):
    return self.__unixpath(os.path.join(path1, *paths))

  def normpath(self, path):
    return self.__unixpath(os.path.normpath(path))

  def open(self, *args, **kwargs):  # pragma:nocover
    raise NotImplementedError()


class TestCase(unittest.TestCase):

  def FailureMessage(self, fmt_string, msg, fmt, *args):  #pragma: no cover
    if msg:
      msg += '\n'
    else:
      msg = ''
    return msg + (fmt_string % tuple(map(fmt, args)))

  def assertIn(self, expected_contained, actual, msg=None, fmt=repr):
    """Same as assertTrue(expected_contained in actual)."""
    if expected_contained not in actual:  #pragma: no cover
      raise self.failureException, self.FailureMessage(
          'Expected to contain: %s\nActual: %s',
          msg, fmt, expected_contained, actual)

  def assertNotIn(self, expected_contained, actual, msg=None, fmt=repr):
    """Same as assertTrue(expected_contained not in actual)."""
    if expected_contained in actual:  #pragma: no cover
      raise self.failureException, self.FailureMessage(
          'Expected not to contain: %s\nActual: %s',
          msg, fmt, expected_contained, actual)

  def assertEqualExt(self, first, second, msg=None, fmt=repr):
    """Same as assertEqual but prints expected/actual even if msg is set."""
    if not first == second:  #pragma: no cover
      raise self.failureException, self.FailureMessage(
          'Expected: %s\nActual:   %s', msg, fmt, first, second)

  def assertTextEqual(self, first, second, msg=None):
    """Same as assertEqual but prints arguments without escaping them."""
    if not first == second:  #pragma: no cover
      raise self.failureException, self.FailureMessage(
          'Expected:\n%s\nActual:\n%s', msg, None, first, second)

  def FakeInputFile(self, contents, **kwargs):
    """
    Returns a fake input file supporting the read() and close() methods.

    Args:
      contents: (string) The contents of the file.
        If None, the file raises IOError on all reads.
    """
    if contents is None:
      class FakeErrorFile(object):
        def read(self):
          raise IOError('Fake error')
        close = read
      return FakeErrorFile()
    else:
      return io.StringIO(contents, **kwargs)

  def FakeOutputFile(self, **kwargs):
    return io.StringIO(**kwargs)

  def GetFileSystem(self, inputs):
    class TestFileSystem(FakeFileSystem):
      def __init__(fs):
        super(TestFileSystem, fs).__init__()
        fs.__output_writers = {}

      def open(fs, filename, mode='rt', **kwargs):
        if mode == 'rt':
          # Open an input file.
          if filename in inputs:
            return self.FakeInputFile(inputs[filename], **kwargs)
          else:
            raise IOError(2, 'file not found: ' + filename)
        elif mode == 'wt':
          # Open an output file.
          assert filename not in fs.__output_writers, \
              'Output file already open: ' + filename
          writer = self.FakeOutputFile(**kwargs)
          fs.__output_writers[filename] = writer
          return writer
        else:  # pragma: nocover
          assert False, 'Unsupported mode: ' + mode

      def GetOutputs(fs, strip_output=True):
        outputs = {}
        for output_filename, output_writer in fs.__output_writers.iteritems():
          output = output_writer.getvalue()
          if strip_output:
            output = output.strip()
          outputs[output_filename] = output
        return outputs

    return TestFileSystem()


class ExecutionTestCase(TestCase):

  @staticmethod
  @macro(public_name='identity', args_signature='*contents')
  def IdentityMacro(executor, call_node, contents):
    executor.ExecuteNodes(contents)

  @staticmethod
  @macro(public_name='eval.text', args_signature='text', text_compatible=True)
  def EvalTextMacro(executor, call_node, text):
    executor.AppendText(text)

  def setUp(self):
    super(ExecutionTestCase, self).setUp()
    self.additional_builtin_macros = GetPublicMacros(self)

  def CreateBranch(self, executor, branch_class, **kwargs):
    kwargs.setdefault('name', 'root')
    writer = executor.fs.open(kwargs['name'], mode='wt')
    branch = branch_class(
        parent=None, parent_context=executor.system_branch.context,
        writer=writer, **kwargs)
    executor.RegisterBranch(branch)
    return branch

  def GetExecutionBranch(self, executor):
    return executor.system_branch

  def PrepareInputOutput(self, text_or_iter, separator):
    if isinstance(text_or_iter, collections.Iterable) and \
        not isinstance(text_or_iter, basestring):
      return separator.join(text_or_iter)
    else:
      return text_or_iter

  def InputHook(self, text):
    return text

  def assertExecutionOutput(self, expected, actual, msg):
    self.assertEqualExt(expected, actual, msg)

  def assertExecution(self, inputs, expected_outputs=None, messages=(),
                      fatal_error=None, strip_output=True):
    """
    Args:
      inputs: (string|string list|string -> string|string list dict)
        The input files, keyed by name. If not a dictionary, the contents of the
        '/root' input file. Each entry is processed by PrepareInputOutput with
        '\n' as separator if a fatal error is expected, else ''.
      expected_outputs:
        (None|string|string list|string -> string|string list dict)
        The expected output of each branch, keyed by branch name.
        If not a dictionary, the expected output of GetExecutionBranch().
        Processed by PrepareInputOutput with '' as separator.
      messages: (string list) The expected error messages.
      fatal_error: (bool) Whether a fatal error is expected.
        Automatically set to True if messages is not None.
    """

    # By default, expect a fatal error if log messages are expected.
    if fatal_error is None:
      fatal_error = (len(messages) > 0)

    # Create the input dictionary.
    if not isinstance(inputs, collections.Mapping):
      inputs = {'/root': inputs}
    if fatal_error:
      input_separator = '\n'
    else:
      input_separator = ''
    inputs = dict(
        (filename, self.InputHook(
            self.PrepareInputOutput(text_or_iter,
                                    separator=input_separator)))
        for filename, text_or_iter in inputs.iteritems())

    fs = self.GetFileSystem(inputs)

    logger = FakeLogger()
    executor = Executor(output_dir='/output', logger=logger, fs=fs)
    executor.system_branch.writer = \
        fs.open(executor.system_branch.name, 'wt')
    output_branch = self.GetExecutionBranch(executor)
    executor.current_branch = output_branch
    output_branch.context.AddMacros(self.additional_builtin_macros)

    # Create the expected output dictionary.
    if not isinstance(expected_outputs, collections.Mapping):
      expected_outputs = {output_branch.name: expected_outputs}
    expected_outputs = dict(
        (branch_name, self.PrepareInputOutput(text_or_iter, separator=''))
        for branch_name, text_or_iter in expected_outputs.iteritems())

    # Execute the input, render the output branches.
    try:
      executor.ExecuteFile('/root', cur_dir='/cur')
      actual_fatal_error = False
    except FatalError:
      actual_fatal_error = True

    # Retrieve the output of each branch.
    actual_outputs = {}
    if not actual_fatal_error:
      try:
        executor.RenderBranches()
      except InternalError, e:
        actual_fatal_error = True
        logger.Log(loc('<unknown>', -1, dir_path='/'), e)
      actual_outputs = fs.GetOutputs(strip_output)

    # Verify the output.
    if fatal_error:
      self.assertTrue(actual_fatal_error, 'expected a fatal error')
    else:
      self.assertFalse(actual_fatal_error,
                       'unexpected fatal error; messages: {0}'.format(
                           logger.GetOutput()))
      expected_filenames = expected_outputs.keys()
      actual_filenames = actual_outputs.keys()
      self.assertTrue(
          set(expected_filenames).issubset(set(actual_filenames)),
          ('output file names mismatch; expected filenames:\n  {expected}\n' +
           'should be a subset of actual filenames:\n  {actual}').format(
              expected=expected_filenames, actual=actual_filenames))
      for filename in expected_outputs:
        self.assertExecutionOutput(expected_outputs[filename],
                                   actual_outputs[filename],
                                   'output mismatch for: ' + filename)

    # Verify the log messages.
    self.assertEqualExt('\n'.join(messages), logger.GetOutput(),
                        'messages mismatch')


class BranchTestCase(TestCase):

  def PrepareMix(self, branch):
    sub_branch1 = branch.CreateSubBranch()
    sub_branch2 = branch.CreateSubBranch()
    sub_branch12 = sub_branch1.CreateSubBranch()
    sub_branch21 = sub_branch2.CreateSubBranch()

    sub_branch1.AppendText('sub1 ')
    sub_branch1.AppendSubBranch(sub_branch12)
    sub_branch12.AppendText('sub12 ')

    branch.AppendText('one ')
    branch.AppendSubBranch(sub_branch1)
    branch.AppendText('two ')
    branch.AppendSubBranch(sub_branch2)
    branch.AppendText('three ')

    sub_branch2.AppendSubBranch(sub_branch21)
    sub_branch21.AppendText('sub21 ')

    self.assertEqual(branch, branch.root)
    self.assertEqual(branch, sub_branch1.root)
    self.assertEqual(branch, sub_branch12.root)