# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

import traceback


def FormatMessage(message, **kwargs):
  """
  Formats a message.

  Args:
    message: (string|Exception) The error message, can be None.
      If an exception, wraps it with str().
      Returned as is if **kwargs is empty, else interpreted as a format.
    **kwargs: (dict) The formatting parameters to apply to the message.

  Returns:
    (string) The message, never None, formatted if necessary.
  """
  if not message:
    return 'unknown error'
  elif kwargs:
    return message.format(**kwargs)
  elif isinstance(message, Exception):
    return str(message)
  else:
    return message


class BaseError(Exception):
  """
  Base class for PyScribe-specific errors.

  Fields:
    message: (string) The error message, possibly with trailing newline.
  """

  def __init__(self, message=None, **kwargs):
    super(BaseError, self).__init__()
    self.message = FormatMessage(message, **kwargs).rstrip()

  def __str__(self):
    return self.message


class FatalError(BaseError):
  """
  Thrown when a fatal error is encountered.

  The error message is expected to be complete: stacktrace included if needed.
  """


class InternalError(BaseError):
  """
  Thrown by internal methods when a fatal error is encountered.

  The error should not be exposed to the end-user, as it may miss additional
  information such as stacktrace.
  """


class Filename:
  """
  Name and path of a file.

  Fields:
    display_path: (string) The name of the file as it should be displayed in
      error messages. Does not have to be valid or absolute. Typically set to an
      arbitrary human-readable string for stdin/stdout files.
    dir_path: (string) The path of the directory of the file.
      Should always be valid; typically set to the current directory
      for stdin/stdout files.
  """

  def __init__(self, display_path, dir_path):
    self.display_path = display_path
    self.dir_path = dir_path

  def __str__(self):
    return self.display_path

  def __eq__(self, other):
    return isinstance(other, Filename) and \
        self.display_path == other.display_path and \
        self.dir_path == other.dir_path


class Location:
  """
  Location of a token in a source file.

  Fields:
    filename: (Filename) The file of the location.
    lineno: (int) The line index of the location, 1 for the first line,
      -1 if no line index is available.
  """

  def __init__(self, filename, lineno):
    assert isinstance(filename, Filename)
    self.filename = filename
    self.lineno = lineno

  def __repr__(self):
    return '{0.filename}:{0.lineno}'.format(self)

  def __eq__(self, other):
    return isinstance(other, Location) and \
        self.filename == other.filename and \
        self.lineno == other.lineno


class Logger:
  """
  Logs warnings and error messages.
  """

  FORMATS = dict(
    simple=('{location}: {message}\n',
            '  {call_node.location}: ${call_node.name}\n'),
    python=('  File "{location.filename}", line {location.lineno}\n' +
                '    {message}\n',
            '  File "{call_node.location.filename}", ' +
                'line {call_node.location.lineno}, in ${call_node.name}\n'),
  )

  def __init__(self, *, fmt, err_file, info_file, fmt_definition=None):
    self.__fmt = fmt
    (self.__top_format, self.__stack_frame_format) = \
        fmt_definition or self.FORMATS[fmt]
    self.__err_file = err_file
    self.__info_file = info_file

  def LocationError(self, location, message, call_stack=(), **kwargs):
    """
    Creates a FatalError for the given location.

    Args:
      location: (Location) The location of the error.
      message: (string) The error message. Interpreted as a format if
        **kwargs is not empty.
      call_stack: (CallNode list) The macro call stack.
      **kwargs: (dict) The formatting parameters to apply to the message.
    """
    return FatalError('{header}{stack}',
        header=self.__top_format.format(
            location=location, message=FormatMessage(message, **kwargs)),
        stack=''.join(self.__stack_frame_format.format(call_node=call_node)
                      for call_node in call_stack))

  def LogException(self, e, exc_info=None, tb_limit=None):
    """
    Prints a log entry for the given exception.

    See traceback.print_exception() for details on exc_info and tb_limit.

    Args:
      e: (Exception) The exception to log.
      exc_info: (etype, value, tb) The exception information returned by
        sys.exc_info(), None if unavailable.
      tb_limit: (int|None) The maximum number of stacktrace entries to print,
        None for unlimited.
    """
    print(str(e), file=self.__err_file)
    if exc_info is not None:
      if self.__fmt == 'python':
        traceback.print_exception(*exc_info, file=self.__err_file,
                                  limit=tb_limit)

  def LogInfo(self, message):
    """
    Prints a log entry to stderr if --quiet is not set.

    Args:
      message: (string) The message to log.
    """
    if self.__info_file:
      print(message, file=self.__info_file, flush=True)
