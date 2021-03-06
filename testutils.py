# -*- coding: utf-8 -*-
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license
# pylint: disable=no-self-use

__author__ = 'Guillaume Ryder'

import argparse
import collections
import errno
import io
import os
import sys
import unittest

import execution
from log import FatalError, Filename, Location, Logger, NodeError
from macros import macro, GetPublicMacros


__import__('tests')  # for unittest hooks


def loc(display_path, lineno, dir_path='/cur'):
  return Location(Filename(display_path, dir_path), lineno)

TEST_LOCATION = loc('file.txt', 42)
TEST_UNICODE = 'Îñţérñåţîöñåļîžåţîöñ'

SPECIAL_CHARS = ' '.join((
    "| / ^^ ^$ ^#",  # no text macro for these
    r"% & \ _",
    "a~b",
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
SPECIAL_CHARS_AS_RAW_TEXT = SPECIAL_CHARS.replace(' ^', ' ')
SPECIAL_CHARS_AFTER_TEXT_MACROS = ' '.join((
    "| / ^ $ #",
    r"% & \ _",
    "a\xa0b",
    "–c—",
    "d…",
    "«e»",
    "« f »",
    "`g'h' 'g`h`",
    "“i”j” ”k“l“",
    "“`m”'",
    "n ! o: p ; q?",
    "r!:;?",
))
SPECIAL_CHARS_AS_PARSING_ESCAPE_ALL = ' '.join((
    "'| / ^ $ #",
    "'$text.percent' '$text.ampersand' '$text.backslash' '$text.underscore'",
    "a'$text.nbsp'b",
    "'$text.dash.en'c'$text.dash.em'",
    "d'$text.ellipsis'",
    "'$text.guillemet.open'e'$text.guillemet.close'",
    "'$text.guillemet.open' f '$text.guillemet.close'",
    "'$text.backtick'g'$text.apostrophe'h'$text.apostrophe'",
    "'$text.apostrophe'g'$text.backtick'h'$text.backtick'",
    "'$text.quote.open'i'$text.quote.close'j'$text.quote.close'",
    "'$text.quote.close'k'$text.quote.open'l'$text.quote.open'",
    "'$text.quote.open$text.backtick'm'$text.quote.close$text.apostrophe'",
    "n '$text.punctuation.double['!']'",
    "o'$text.punctuation.double[':']'",
    "p '$text.punctuation.double[';']'",
    "q'$text.punctuation.double['?']'",
    "r'$text.punctuation.double['!:;?']",
))
SPECIAL_CHARS_AS_HTML = (
    SPECIAL_CHARS.replace('&', '&amp;')
                 .replace('<', '&lt;')
                 .replace('>', '&gt;'))
SPECIAL_CHARS_AS_HTML_TYPO_INDEPENDENT = ' '.join((
    "| / ^ $ #",
    r"% &amp; \ _",
    "a\xa0b",
    "–c—",
    "d…",
))
TYPO_TO_SPECIAL_CHARS_AS_HTML = {
    'neutral': ' '.join((
        SPECIAL_CHARS_AS_HTML_TYPO_INDEPENDENT,

        "«e»",
        "« f »",
        "`g'h' 'g`h`",
        "“i”j” ”k“l“",
        "“`m”'",
        "n ! o: p ; q?",
        "r!:;?",
    )),
    'english': ' '.join((
        SPECIAL_CHARS_AS_HTML_TYPO_INDEPENDENT,

        "«e»",
        "« f »",
        "‘g’h’ ’g‘h‘",
        "“i”j” ”k“l“",
        "“‘m”’",
        "n ! o: p ; q?",
        "r!:;?",
    )),
    'french': ' '.join((
        SPECIAL_CHARS_AS_HTML_TYPO_INDEPENDENT,

        "«\xa0e\xa0»",
        "«\xa0f\xa0»",
        "‘g’h’ ’g‘h‘",
        "“i”j” ”k“l“",
        "“‘m”’",
        "n\xa0! o\xa0: p\xa0; q\xa0?",
        "r\xa0!:;?",
    )),
}
SPECIAL_CHARS_AS_LATEX_ESCAPE_ALL = ' '.join((
    "| / ^ $ #",
    r"\% \& \textbackslash{} \_",
    "a~b",
    "--c---",
    r"d\dots{}",
    "«e»",
    "« f »",
    "`g'h' 'g`h`",
    "“i”j” ”k“l“",
    "“`m”'",
    "n ! o: p ; q?",
    "r!:;?",
))

OTHER_TEXT_MACROS = ' '.join((
    '$text.ampersand',
    '$text.dollar',
    '$text.hash',
    '$text.caret',
    'A$text.nbsp^B',
    'C$-D',
))
OTHER_TEXT_MACROS_AS_TEXT = "& $ # ^ A\xa0B C\xadD"
OTHER_TEXT_MACROS_AS_HTML = "&amp; $ # ^ A\xa0B C\xadD"
OTHER_TEXT_MACROS_AS_LATEX = r'\& \$ \# \string^ A~B C\-D'

FAKE_PYSCRIBE_DIR = '/pyscribe/'
REAL_PYSCRIBE_DIR = os.path.join(os.path.dirname(__file__), '')
TESTDATA_DIR = os.path.join(REAL_PYSCRIBE_DIR, 'testdata')


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
    super(FakeLogger, self).__init__(fmt='test',
                                     err_file=self.err_file,
                                     info_file=None,
                                     fmt_definition=self.FORMAT)

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

  basename = staticmethod(os.path.basename)

  @classmethod
  def dirname(cls, path):
    return cls.MakeUnix(os.path.dirname(path))

  def getcwd(self):
    return self.cwd

  isabs = staticmethod(os.path.isabs)

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
        If None, the file raises OSError on all reads.
    """
    if contents is None:
      class FakeErrorFile(io.StringIO):
        def read(self):
          raise OSError('Fake read error')
      return FakeErrorFile('')
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
            raise FileNotFoundError(errno.ENOENT, 'File not found', filename)
        elif mode == 'wt':
          # Open an output file.
          assert filename not in fs.__output_writers, \
              'Output file already open: ' + filename
          if 'not_writeable' in filename:
            raise PermissionError(errno.EACCES, 'File not writeable', filename)
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
    executor = execution.Executor(logger=logger, fs=fs,
                                  current_dir='/cur',
                                  output_path_prefix='/output')
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
    except FatalError as e:
      logger.LogException(e)
      actual_fatal_error = True

    # Retrieve the output of each branch.
    actual_outputs = {}
    if not actual_fatal_error:
      try:
        executor.RenderBranches()
      except NodeError as e:
        actual_fatal_error = True
        logger.LogException(e)
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


class FakeArgumentParser(argparse.ArgumentParser):
  """Option parser that prints to self.stderr."""
  # pylint: disable=arguments-differ

  def __init__(self, stderr):
    super(FakeArgumentParser, self).__init__()
    self.__stderr = stderr

  def exit(self, status=0, msg='', **unused_kwargs):
    self.__stderr.write(msg)
    sys.exit(status)

  def error(self, msg):
    self.exit(2, "error: {}\n".format(msg))

  def print_help(self, file=None, **kwargs):
    argparse.ArgumentParser.print_help(self, self.__stderr, **kwargs)
