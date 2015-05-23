#!/usr/bin/env python
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

from copy import copy
import os
import sys
import optparse

from executor import Executor, FileSystem
import log


_USAGE = '%prog [options] input.psc'
_DESCRIPTION = None


class Main:

  def __init__(self, args, fs=FileSystem(), OptionParser=optparse.OptionParser,
               Logger=log.Logger):
    self.__args = args
    self.__fs = fs
    self.__OptionParser = OptionParser
    self.__Logger = Logger

  def Run(self):
    self.__LoadEnvironment()
    self.__ParseOptions()
    self.__Execute()

  def __LoadEnvironment(self):
    """Retrieves the environment: current directory, etc."""
    fs = self.__fs
    self.__lib_dir = fs.dirname(fs.normpath(__file__))
    self.__current_dir = fs.getcwd()

  def __ParseOptions(self):
    """
    Parses the command-line options given at construction.

    Quits on error or if --help is passed.

    Sets the following values in self:
      __input_filename: The path of the file to execute.
      __options: The command-line options object.
      __logger: The logger to use.
    """
    def CheckDefine(option, opt, value):
      (name, sep, text) = value.partition('=')
      if not sep:
        raise optparse.OptionValueError(
            '{opt} option expects format: name=text; got: {value}'.format(
                opt=opt, value=value))
      return (name, text)

    class PyscribeOption(optparse.Option):
      TYPES = optparse.Option.TYPES + ('define',)
      TYPE_CHECKER = copy(optparse.Option.TYPE_CHECKER)
      TYPE_CHECKER['define'] = CheckDefine

    parser = self.__OptionParser(usage=_USAGE, description=_DESCRIPTION,
                                 option_class=PyscribeOption)
    parser.add_option('-d', '--define', metavar='NAME=TEXT',
                      dest='defines',
                      default=[], action='append', type='define',
                      help='set a macro in the root context')
    parser.add_option('--error_format', metavar='FORMAT',
                      dest='logger_format',
                      type='choice', default='simple',
                      choices=sorted(self.__Logger.FORMATS),
                      help='error reporting format')
    parser.add_option('-f', '--format', metavar='FORMAT',
                      dest='output_format',
                      default='',
                      help='output format')
    parser.add_option('-o', '--output', metavar='DIR',
                      dest='output_dir',
                      help='output directory')
    (options, args) = parser.parse_args(self.__args)

    # Input file
    if len(args) != 1:
      parser.error('expected one argument')
    self.__input_filename = args[0]

    # Output directory
    if not options.output_dir:
      options.output_dir = self.__fs.join(self.__current_dir, 'output')

    # Logger
    self.__logger = self.__Logger(self.__Logger.FORMATS[options.logger_format])

    # Constants
    self.__constants = constants = dict(options.defines)
    constants['output.format'] = options.output_format

    self.__options = options

  def __Execute(self):
    """Executes the action specified on the command-line."""
    options = self.__options
    input_filename = self.__input_filename
    executor = Executor(options.output_dir, logger=self.__logger, fs=self.__fs)
    executor.AddConstants(self.__constants)

    try:
      executor.ExecuteFile(input_filename, self.__current_dir)
      executor.RenderBranches()
    except log.FatalError:
      sys.exit(1)


if __name__ == '__main__':
  # Disable stderr buffering.
  sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', 0)

  Main(sys.argv[1:]).Run()
