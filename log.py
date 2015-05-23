# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'


def FormatMessage(message, **kwargs):
  """
  Formats a message.

  Args:
    message: (string) The error message, can be None.
      Returned as is if **kwargs is empty, else interpreted as a format.
    **kwargs: (dict) The formatting parameters to apply to the message.

  Returns:
    (string) The message, never None, formatted if necessary.
  """
  if not message:
    return 'unknown error'
  if kwargs:
    message = message.format(**kwargs)
  elif isinstance(message, InternalError):
    message = message.message
  return message


class BaseError(Exception):
  """
  Base class for PyScribe-specific errors.

  Fields:
    message: (string) The error message, never None.
  """

  def __init__(self, message=None, **kwargs):
    super(BaseError, self).__init__()
    self.message = FormatMessage(message, **kwargs)

  def __str__(self):
    return self.message


class FatalError(BaseError):
  """
  Thrown when a fatal error is encountered.

  The error message is expected to be complete: stacktrace included if needed.
  """

  pass


class InternalError(BaseError):
  """
  Thrown by internal methods when a fatal error is encountered.

  The error should not be exposed to the end-user, as it may miss additional
  information such as stacktrace.
  """

  pass


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

  def __init__(self, *, fmt, err_file, info_file):
    (self.__top_format, self.__stack_frame_format) = fmt
    self.__err_file = err_file
    self.__info_file = info_file

  def LogLocation(self, location, message, call_stack=(), **kwargs):
    """
    Prints an error message for the given location.

    Args:
      location: (Location) The location of the error.
      message: (string) The error message. Interpreted as a format if
        **kwargs is not empty.
      call_stack: (CallNode list) The macro call stack.
      **kwargs: (dict) The formatting parameters to apply to the message.
    """
    self.__err_file.write(self.__top_format.format(
        location=location, message=FormatMessage(message, **kwargs)))
    for call_node in call_stack:
      self.__err_file.write(self.__stack_frame_format.format(
          call_node=call_node))
    return FatalError()

  def LogInfo(self, message):
    """
    Prints a log entry to stderr if --quiet is not set.

    Args:
      message: (string) The message to log.
    """
    if self.__info_file:
      print(message, file=self.__info_file, flush=True)
