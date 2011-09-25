#!/usr/bin/env python
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

import sys


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


class Location(object):
  """Location of a token in a source file."""

  def __init__(self, filename, lineno):
    self.filename = filename
    self.lineno = lineno

  def __repr__(self):
    return '{0.filename}:{0.lineno}'.format(self)

  def __eq__(self, other):
    return isinstance(other, Location) and \
        self.filename == other.filename and \
        self.lineno == other.lineno

Location.unknown = Location('<unknown>', -1)


class Logger(object):
  """
  Logs warnings and error messages.
  """

  SIMPLE_FORMAT = (
      u'{location}: {message}\n',
      u'  {call_node.location}: ${call_node.name}\n')
  PYTHON_FORMAT = (
      u'  File "{location.filename}", line {location.lineno}\n    {message}\n',
      u'  File "{call_node.location.filename}", ' +
          u'line {call_node.location.lineno}, in ${call_node.name}\n')

  def __init__(self, format=SIMPLE_FORMAT, output_file=None):
    (self.__top_format, self.__stack_frame_format) = format
    self.__output_file = output_file or sys.stderr

  def Log(self, location, message, call_stack=(), **kwargs):
    """
    Prints an error message.

    Args:
      location: (Location) The location of the error.
      message: (string) The error message. Interpreted as a format if
        **kwargs is not empty.
      call_stack: (CallNode list) The macro call stack.
      **kwargs: (dict) The formatting parameters to apply to the message.
    """
    self.__output_file.write(self.__top_format.format(
        location=location, message=FormatMessage(message, **kwargs)))
    for call_node in call_stack:
      self.__output_file.write(self.__stack_frame_format.format(
          call_node=call_node))
    return FatalError()
