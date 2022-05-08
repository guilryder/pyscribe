# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

from dataclasses import dataclass
from os import PathLike
import traceback
from typing import Union


def FormatMessage(message):
  """
  Formats a message.

  Args:
    message: (str|Exception) The error message, can be None.

  Returns:
    (str) The message, never None.
  """
  return str(message) if message else 'unknown error'


class BaseError(Exception):
  """
  Base class for PyScribe-specific errors.

  Fields:
    message: (str) The error message, possibly with trailing newline.
  """

  def __init__(self, message=None):
    super().__init__()
    self.message = FormatMessage(message).rstrip()

  def __str__(self):
    return self.message


class FatalError(BaseError):
  """
  Thrown when a fatal error is encountered.

  Can be exposed as-is to the end user, includes any available contextual
  information: location, stacktrace.
  """


class NodeError(BaseError):
  """
  Thrown on error when executing a node.

  Translated into FatalError in Executor.ExecuteNodes().

  Avoid exposing the error as-is to the end user, because the message lacks
  contextual information: location, stacktrace.
  """


@dataclass(frozen=True)
class Filename:
  """Name and path of a file."""

  # The name of the file as it should be displayed in error messages.
  # Does not have to be valid or absolute.
  # Typically set to an arbitrary human-readable string for stdin/stdout files.
  display_path: str

  # The path of the directory of the file. Should always be valid.
  # Typically set to the current directory for stdin/stdout files.
  dir_path: str

  def __init__(self, display_path: Union[PathLike[str], str],
               dir_path: Union[PathLike[str], str]):
    object.__setattr__(self, 'display_path', str(display_path))
    object.__setattr__(self, 'dir_path', str(dir_path))

  def __str__(self):
    return self.display_path


@dataclass(frozen=True)
class Location:
  """Location of a token in a source file."""

  filename: Filename
  lineno: int  # 1 for the first line, -1 if no line index is available.

  def __repr__(self):
    return f'{self.filename}:{self.lineno}'


@dataclass(frozen=True)
class LoggerFormat:
  name: str
  top: str  # format arguments: {location: Location, message: str}
  stack_frame: str  # format arguments: {call_node: CallNode}


LOGGER_FORMATS = {
    fmt.name: fmt
    for fmt in [
        LoggerFormat(
            name='simple',
            top=
                '{location}: {message}\n',
            stack_frame=
                '  {call_node.location}: ${call_node.name}\n'),
        LoggerFormat(
            name='python',
            top=
                '  File "{location.filename}", line {location.lineno}\n' +
                '    {message}\n',
            stack_frame=
                '  File "{call_node.location.filename}", ' +
                'line {call_node.location.lineno}, in ${call_node.name}\n'),
    ]
}


class Logger:
  """
  Logs warnings and error messages.
  """

  def __init__(self, *, fmt, err_file, info_file):
    if isinstance(fmt, LoggerFormat):
      self.__fmt = fmt
    else:
      self.__fmt = LOGGER_FORMATS[fmt]
    self.__err_file = err_file
    self.__info_file = info_file

  def LocationError(self, location, message, *, call_stack=()):
    """
    Creates a FatalError for the given location.

    Args:
      location: (Location) The location of the error.
      message: (str) The error message.
      call_stack: (List[CallNode]) The macro call stack.
    """
    top = self.__fmt.top.format(
        location=location, message=FormatMessage(message))
    stack = ''.join(self.__fmt.stack_frame.format(call_node=call_node)
                    for call_node in call_stack)
    return FatalError(top + stack)

  def LogException(self, e, exc_info=(None, None, None), tb_limit=None):
    """
    Prints a log entry for the given exception.

    See traceback.print_exception() for details on exc_info and tb_limit.

    Args:
      e: (Exception) The exception to log.
      exc_info: (etype, value, tb) The exception information returned by
        sys.exc_info(), (None, None, None) if unavailable.
      tb_limit: (int|None) The maximum number of stacktrace entries to print,
        None for unlimited.
    """
    print(str(e), file=self.__err_file)
    if exc_info != (None, None, None):
      if self.__fmt.name == 'python':
        traceback.print_exception(*exc_info, file=self.__err_file,
                                  limit=tb_limit)
      else:
        print('Set --error_format=python for details.', file=self.__err_file)

  def LogInfo(self, message):
    """
    Prints a log entry to stderr if --quiet is not set.

    Args:
      message: (str) The message to log.
    """
    if self.__info_file:
      print(message, file=self.__info_file, flush=True)
