# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

from collections.abc import Sequence
from dataclasses import dataclass
from os import PathLike
import traceback
from types import TracebackType
from typing import Optional, TextIO, TYPE_CHECKING, Union

if TYPE_CHECKING:
  from parsing import CallNode


MessageT = Union[None, str, BaseException]


def FormatMessage(message: MessageT) -> str:
  """Formats a message to text."""
  return str(message) if message else 'unknown error'


class BaseError(Exception):
  """Base class for PyScribe-specific errors."""

  # The error message, possibly with trailing newline.
  message: str

  def __init__(self, message: Optional[str]=None):
    super().__init__()
    self.message = FormatMessage(message).rstrip()

  def __str__(self) -> str:
    return self.message


class FatalError(BaseError):
  """Thrown when a fatal error is encountered.

  Can be exposed as-is to the end user, includes any available contextual
  information: location, stacktrace.
  """


class NodeError(BaseError):
  """Thrown on error when executing a node.

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

  def __str__(self) -> str:
    return self.display_path


@dataclass(frozen=True)
class Location:
  """Location of a token in a source file."""

  filename: Filename
  lineno: int  # 1 for the first line, -1 if no line index is available.

  def __repr__(self) -> str:
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



_ExcInfoT = tuple[type[BaseException], BaseException, TracebackType]
_OptExcInfoT = Union[_ExcInfoT, tuple[None, None, None]]

class Logger:
  """Logs warnings and error messages."""

  def __init__(self, *, fmt: Union[str, LoggerFormat],
               err_file: TextIO, info_file: Optional[TextIO]):
    if isinstance(fmt, LoggerFormat):
      self.__fmt = fmt
    else:
      self.__fmt = LOGGER_FORMATS[fmt]
    self.__err_file = err_file
    self.__info_file = info_file

  def LocationError(self, location: Location, message: MessageT, *,
                    call_stack: Sequence['CallNode']=()) -> FatalError:
    """Creates a FatalError for the given location."""
    top = self.__fmt.top.format(
        location=location, message=FormatMessage(message))
    stack = ''.join(self.__fmt.stack_frame.format(call_node=call_node)
                    for call_node in call_stack)
    return FatalError(top + stack)

  def LogException(self, e: BaseException,
                   exc_info: _OptExcInfoT=(None, None, None),
                   tb_limit: Optional[int]=None) -> None:
    """Prints a log entry for the given exception.

    See traceback.print_exception() for details on exc_info and tb_limit.

    Args:
      e: The exception to log.
      exc_info: The exception information returned by sys.exc_info(),
        (None, None, None) if unavailable.
      tb_limit: The maximum number of stacktrace entries to print,
        None for unlimited.
    """
    print(str(e), file=self.__err_file)
    if exc_info != (None, None, None):
      valid_exc_info: _ExcInfoT = exc_info  # type: ignore[assignment]
      if self.__fmt.name == 'python':
        traceback.print_exception(*valid_exc_info, file=self.__err_file,
                                  limit=tb_limit)
      else:
        print('Set --error_format=python for details.', file=self.__err_file)

  def LogInfo(self, message: str) -> None:
    """Prints a log entry to stderr if --quiet is not set.

    Args:
      message: The message to log.
    """
    if self.__info_file:
      print(message, file=self.__info_file, flush=True)
