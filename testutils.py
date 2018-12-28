# -*- coding: utf-8 -*-
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license
# pylint: disable=no-self-use

__author__ = 'Guillaume Ryder'

import collections
import io
import os
import unittest

import execution
from log import FatalError, Filename, InternalError, Location, Logger
from macros import macro, GetPublicMacros


__import__('tests')  # for unittest hooks


def loc(display_path, lineno, dir_path='/cur'):
  return Location(Filename(display_path, dir_path), lineno)

TEST_LOCATION = loc('file.txt', 42)
TEST_UNICODE = 'Îñţérñåţîöñåļîžåţîöñ'
SPECIAL_CHARS = ' '.join((
    "% & _ ^$ $text.dollar ^# $text.hash",
    "a~b",
    "n$-o",
    "--c---",
    "d...",
    "<<e>>",
    "<< f >>",
    "`g'h' 'g`h`",
    "``i''j'' ''k``l``",
    "```m'''",
    "n ! o: p ; q?",
    "r!:;?",
))
SPECIAL_CHARS_AS_HTML = (
    SPECIAL_CHARS.replace('&', '&amp;')
                 .replace('<', '&lt;')
                 .replace('>', '&gt;'))

FAKE_PYSCRIBE_DIR = '/pyscribe/'
REAL_PYSCRIBE_DIR = os.path.join(os.path.dirname(__file__), '')


class FakeLogger(Logger):

  """
  Records logged entries in a string buffer.

  Example output: GetOutput() == 'file.txt:42: some error'
  """

  FORMAT = (
      '{location!r}: {message}\n',
      '  {call_node.location!r}: ${call_node.name}\n')

  def __init__(self):
    self.err_file = io.StringIO()
    self.info_messages = []
    super(FakeLogger, self).__init__(fmt=self.FORMAT,
                                     err_file=self.err_file,
                                     info_file=None)

  def ConsumeStdErr(self):
    """Returns the errors logged so far, then clears them."""
    output = self.err_file.getvalue().strip()
    self.err_file.seek(0)
    self.err_file.truncate()
    return output

  def LogInfo(self, message):
    self.info_messages.append(message)


class FakeFileSystem(execution.AbstractFileSystem):

  def __init__(self):
    super(FakeFileSystem, self).__init__()
    self.stdout = None
    self.stderr = None
    self.cwd = '/cur'
    self.created_dirs = None

  def InitializeForWrites(self):
    self.stdout = io.StringIO()
    self.stderr = io.StringIO()
    self.created_dirs = set()

  @classmethod
  def dirname(cls, path):
    return cls.MakeUnix(os.path.dirname(path))

  def getcwd(self):
    return self.cwd

  @classmethod
  def join(cls, path1, *paths):
    return cls.MakeUnix(os.path.join(path1, *paths))

  def lexists(self, path):
    raise NotImplementedError()  # pragma: no cover

  def makedirs(self, path, exist_ok=False):
    if not exist_ok:
      raise NotImplementedError()  # pragma: no cover
    self.created_dirs.add(path)

  @classmethod
  def normpath(cls, path):
    return cls.MakeUnix(os.path.normpath(path))

  def open(self, *args, **kwargs):
    raise NotImplementedError()  # pragma: no cover

  @classmethod
  def relpath(cls, path, start):
    return cls.MakeUnix(os.path.relpath(path, start))

  splitext = staticmethod(os.path.splitext)


class TestCase(unittest.TestCase):

  def __FailureMessage(self, fmt_string, msg, fmt, *args):  #pragma: no cover
    if msg:
      msg += '\n'
    else:
      msg = ''
    if fmt is None:
      fmt = lambda x: x
    return msg + fmt_string.format(*map(fmt, args))

  def assertEqualExt(self, actual, expected, msg=None, fmt=repr):
    """Same as assertEqual but prints expected/actual even if msg is set."""
    if not actual == expected:  #pragma: no cover
      raise self.failureException(self.__FailureMessage(
          'Actual:   {}\nExpected: {}', msg, fmt, actual, expected))

  def assertTextEqual(self, actual, expected, msg=None):
    """Same as assertEqual but prints arguments without escaping them."""
    if not actual == expected:  #pragma: no cover
      if '\xa0' in actual or '\xa0' in expected:
        actual, expected = repr(actual), repr(expected)
      raise self.failureException(self.__FailureMessage(
          'Actual:\n{}\nExpected:\n{}', msg, None, actual, expected))

  def FakeInputFile(self, contents, **kwargs):
    """
    Returns a fake input file supporting the read() and close() methods.

    Args:
      contents: (string) The contents of the file.
        If None, the file raises IOError on all reads.
    """
    if contents is None:
      class FakeErrorFile:
        def read(self):
          raise IOError('Fake error')
        close = read
      return FakeErrorFile()
    else:
      return io.StringIO(contents, **kwargs)

  def FakeOutputFile(self, **kwargs):
    return io.StringIO(**kwargs)

  def OpenSourceFile(self, path, **kwargs):
    kwargs.setdefault('encoding', 'utf-8')
    assert path.startswith(FAKE_PYSCRIBE_DIR), (
        'Source path must start with {}: {}'.format(FAKE_PYSCRIBE_DIR, path))
    real_suffix = path[len(FAKE_PYSCRIBE_DIR):]
    real_path = os.path.normpath(os.path.join(REAL_PYSCRIBE_DIR, real_suffix))
    return open(real_path, **kwargs)

  def GetFileSystem(self, inputs):
    class TestFileSystem(FakeFileSystem):
      # pylint: disable=no-self-argument
      def __init__(fs):
        super(TestFileSystem, fs).__init__()
        fs.__output_writers = {}

      def lexists(fs, path):
        return path in inputs

      def open(fs, filename, mode='rt', **kwargs):  # pylint: disable=inconsistent-return-statements
        # pylint: disable=arguments-differ
        assert kwargs.pop('encoding', None) == 'utf-8'
        filename = fs.MakeAbsolute(fs.getcwd(), filename)
        if mode == 'rt':
          # Open an input file.
          if filename in inputs:
            return self.FakeInputFile(inputs[filename], **kwargs)
          elif filename.startswith(FAKE_PYSCRIBE_DIR):
            return self.OpenSourceFile(filename, mode=mode, **kwargs)
          else:
            raise IOError(2, 'file not found: ' + filename)
        elif mode == 'wt':
          # Open an output file.
          assert filename not in fs.__output_writers, \
              'Output file already open: ' + filename
          writer = self.FakeOutputFile(**kwargs)
          fs.__output_writers[filename] = writer
          return writer
        else:  # pragma: no cover
          assert False, 'Unsupported mode: ' + mode

      def GetOutputs(fs):
        outputs = {}
        for output_filename, output_writer in fs.__output_writers.items():
          output = output_writer.getvalue()
          output_writer.close()
          outputs[output_filename] = output
        return outputs

    return TestFileSystem()


class ExecutionTestCase(TestCase):

  @staticmethod
  @macro(public_name='identity', args_signature='*contents')
  def IdentityMacro(executor, unused_call_node, contents):
    executor.ExecuteNodes(contents)

  @staticmethod
  @macro(public_name='eval.text', args_signature='text', text_compatible=True)
  def EvalTextMacro(executor, unused_call_node, text):
    executor.AppendText(text)

  def setUp(self):
    super(ExecutionTestCase, self).setUp()
    self.additional_builtin_macros = GetPublicMacros(self)

  @staticmethod
  def GetBranchFilename(branch_name):
    if branch_name == 'system':
      return '/system'
    else:
      return '/output/' + branch_name

  def CreateBranch(self, executor, branch_class, **kwargs):
    name = kwargs.setdefault('name', 'root')
    writer = executor.fs.open(self.GetBranchFilename(name),
                              mode='wt', encoding='utf-8')
    branch = branch_class(
        parent=None, parent_context=executor.system_branch.context,
        writer=writer, **kwargs)
    executor.RegisterBranch(branch)
    return branch

  def GetExecutionBranch(self, executor):
    return executor.system_branch

  def PrepareInputOutput(self, text_or_iter, separator):
    if isinstance(text_or_iter, collections.Iterable) and \
        not isinstance(text_or_iter, str):
      return separator.join(text_or_iter)
    else:
      return text_or_iter

  def InputHook(self, text):
    return text

  def assertExecutionOutput(self, actual, expected, msg):
    self.assertEqualExt(actual, expected, msg)

  def assertExecution(self, inputs, expected_outputs=None, *, messages=(),
                      fatal_error=None, expected_infos=None):
    """
    Args:
      inputs: (input|(string, input) dict) The input files.
        If a dictionary, the input files keyed by name.
        If not a dictionary, the contents of the '/root' input file.
        Each entry is processed by PrepareInputOutput to generate the file
        contents: either a string, or a sequence of strings joined with '\n' if
        fatal_error is true, or '' if fatal_error is false.
      expected_outputs: (output|(string, output) dict) The expected branch
        outputs. If a dictionary, the outputs keyed by branch name.
        If not a dictionary, the expected output of GetExecutionBranch().
        Each entry is processed by PrepareInputOutput: either a string, or a
        sequence of strings to join with '\n'.
      messages: (string list) The expected error messages.
      fatal_error: (bool) Whether a fatal error is expected.
        Automatically set to True if messages is not None.
      expected_infos: (string list|None) If set, the expected messages logged
        via Logger.LogInfo().
    Returns: (Executor) The executor created to do the verification.
    """

    # By default, expect a fatal error if log messages are expected.
    if fatal_error is None:
      fatal_error = bool(messages)

    # Create the input dictionary.
    if not isinstance(inputs, collections.Mapping):
      inputs = {'/root': inputs}
    inputs = {
        filename: self.InputHook(
            self.PrepareInputOutput(text_or_iter,
                                    separator=fatal_error and '\n' or ''))
        for filename, text_or_iter in inputs.items()}

    fs = self.GetFileSystem(inputs)

    logger = FakeLogger()
    executor = execution.Executor(output_dir='/output', logger=logger, fs=fs)
    executor.system_branch.writer = fs.open(
        self.GetBranchFilename(executor.system_branch.name), 'wt',
        encoding='utf-8')
    output_branch = self.GetExecutionBranch(executor)
    executor.current_branch = output_branch
    output_branch.context.AddMacros(self.additional_builtin_macros)

    # Create the expected output dictionary.
    if not isinstance(expected_outputs, collections.Mapping):
      expected_outputs = {
          self.GetBranchFilename(output_branch.name): expected_outputs,
      }
    expected_outputs = {
        branch_name: self.PrepareInputOutput(text_or_iter, separator='\n')
        for branch_name, text_or_iter in expected_outputs.items()
    }

    # Execute the input, render the output branches.
    try:
      executor.ExecuteFile('/root')
      actual_fatal_error = False
    except FatalError:
      actual_fatal_error = True

    # Retrieve the output of each branch.
    actual_outputs = {}
    if not actual_fatal_error:
      try:
        executor.RenderBranches()
      except InternalError as e:
        actual_fatal_error = True
        logger.LogLocation(loc('<unknown>', -1, dir_path='/'), e)
      actual_outputs = fs.GetOutputs()

    # Verify the output.
    if fatal_error:
      self.assertTrue(actual_fatal_error, 'expected a fatal error')
    else:
      self.assertFalse(actual_fatal_error,
                       'unexpected fatal error; messages: {}'.format(
                           logger.ConsumeStdErr()))
      expected_filenames = frozenset(expected_outputs.keys())
      actual_filenames = frozenset(actual_outputs.keys())
      self.assertTrue(
          expected_filenames.issubset(actual_filenames),
          ('output file names mismatch; expected filenames:\n  {expected}\n' +
           'should be a subset of actual filenames:\n  {actual}').format(
              expected=expected_filenames, actual=actual_filenames))
      for filename in expected_outputs:
        self.assertExecutionOutput(actual_outputs[filename],
                                   expected_outputs[filename],
                                   'output mismatch for: ' + filename)

    # Verify the log messages.
    self.assertEqualExt(logger.ConsumeStdErr(), '\n'.join(messages),
                        'error messages mismatch')
    if expected_infos is not None:
      self.assertEqual(logger.info_messages, expected_infos,
                       'info messages mismatch')
    return executor


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

    self.assertEqual(branch.root, branch)
    self.assertEqual(sub_branch1.root, branch)
    self.assertEqual(sub_branch12.root, branch)
