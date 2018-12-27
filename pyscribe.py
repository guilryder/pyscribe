#!/usr/bin/env python3
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

import argparse
import sys

from execution import PYSCRIBE_EXT, Executor, FileSystem
import log


class Main:

  def __init__(self, input_args, fs=FileSystem(),
               ArgumentParser=argparse.ArgumentParser):
    self.__input_args = input_args
    self.__fs = fs
    self.__ArgumentParser = ArgumentParser

  def Run(self):
    self.__LoadEnvironment()
    self.__ParseArguments()
    self.__Execute()

  def __LoadEnvironment(self):
    """Retrieves the environment: current directory, etc."""
    # pylint: disable=attribute-defined-outside-init
    fs = self.__fs
    self.__lib_dir = fs.dirname(fs.normpath(__file__))
    self.__current_dir = fs.getcwd()

  def __ParseArguments(self):
    """
    Parses the command-line arguments given at construction.

    Quits on error or if --help is passed.

    Sets the following values in self:
      __args: The command-line arguments object.
      __logger: The logger to use.
    """
    # pylint: disable=attribute-defined-outside-init
    def ParseDefine(value):
      (name, sep, text) = value.partition('=')
      if not sep:
        raise argparse.ArgumentTypeError(
            'invalid value, expected format: name=text; got: {value}'.format(
                value=value))
      return (name, text)

    parser = self.__ArgumentParser()
    parser.add_argument('-d', '--define', metavar='NAME=TEXT',
                        dest='defines',
                        default=[], action='append', type=ParseDefine,
                        help='set a macro in the root context')
    parser.add_argument('--error_format', metavar='FORMAT',
                        dest='logger_format',
                        default='simple',
                        choices=sorted(log.Logger.FORMATS),
                        help='error reporting format, used to set the ' +
                             '$output.format variable; default: %(default)s')
    parser.add_argument('-f', '--format', metavar='FORMAT',
                        dest='output_format',
                        default='',
                        help='output format')
    parser.add_argument('-o', '--output', metavar='DIR',
                        dest='output_dir',
                        default=self.__current_dir,
                        help='output directory')
    parser.add_argument('-q', '--quiet',
                        dest='info_file',
                        action='store_const', const=None,
                        default=self.__fs.stdout,
                        help='do not print informational messages')
    parser.add_argument('input_filename', metavar='filename',
                        help='root *.psc file to execute')
    args = parser.parse_args(self.__input_args)

    # Output directory
    self.__fs.makedirs(args.output_dir, exist_ok=True)

    # Logger
    self.__logger = log.Logger(fmt=log.Logger.FORMATS[args.logger_format],
                               err_file=self.__fs.stderr,
                               info_file=args.info_file)

    # Constants
    self.__constants = constants = dict(args.defines)
    constants['output.format'] = args.output_format

    self.__args = args

  def __Execute(self):
    """Executes the action specified on the command-line."""
    args = self.__args
    executor = Executor(args.output_dir, logger=self.__logger, fs=self.__fs)
    executor.AddConstants(self.__constants)

    try:
      resolved_path = executor.ResolveFilePath(args.input_filename,
                                               cur_dir=self.__current_dir,
                                               default_ext=PYSCRIBE_EXT)
      executor.ExecuteFile(resolved_path)
      executor.RenderBranches()
    except log.FatalError:
      sys.exit(1)


if __name__ == '__main__':
  Main(None).Run()
