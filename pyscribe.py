#!/usr/bin/env python3
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

import argparse
import sys
import traceback

from branch_macros import BRANCH_TYPES
from execution import PYSCRIBE_EXT, Executor, FileSystem
import log


class Main:

  def __init__(self, *, input_args=None, fs=FileSystem(), main_file=sys.argv[0],
               ArgumentParser=argparse.ArgumentParser):
    self.__input_args = input_args
    self.__fs = fs
    self.__main_file = main_file
    self.__ArgumentParser = ArgumentParser

  def Run(self):
    self.__LoadEnvironment()
    self.__ParseArguments()
    self.__Execute()

  def __LoadEnvironment(self):
    """Retrieves the environment: current directory."""
    # pylint: disable=attribute-defined-outside-init
    self.__current_dir = self.__fs.getcwd()

  def __ParseArguments(self):
    """
    Parses the command-line arguments given at construction.

    Quits on error or if --help is passed.

    Sets the following values in self:
      __args: The command-line arguments object.
      __logger: The logger to use.
    """
    fs = self.__fs
    # pylint: disable=attribute-defined-outside-init
    def ParseDefine(value):
      (name, sep, text) = value.partition('=')
      if not sep:
        raise argparse.ArgumentTypeError(
            'invalid value, expected format: name=text; got: {}'.format(value))
      return (name, text)

    def ValidateBasename(value):
      if value != fs.basename(value):
        raise argparse.ArgumentTypeError(
            'expected basename without separator, got: {}'.format(value))
      return value

    parser = self.__ArgumentParser()
    parser.add_argument('-d', '--define', metavar='NAME=TEXT',
                        dest='defines',
                        default=[], action='append', type=ParseDefine,
                        help='set a macro in the root context')
    parser.add_argument('--error_format', metavar='FORMAT',
                        dest='error_format',
                        default='simple',
                        choices=sorted(log.Logger.FORMATS),
                        help='error reporting format; default: %(default)s')
    parser.add_argument('-f', '--format', metavar='FORMAT',
                        dest='format',
                        default='html',
                        choices=sorted(BRANCH_TYPES),
                        help='format to render into; sets $format; '
                             'default: %(default)s')
    parser.add_argument('-o', '--output', metavar='DIR',
                        dest='output_dir',
                        default=self.__current_dir,
                        help='output directory')
    parser.add_argument('-p', '--output-basename-prefix', type=ValidateBasename,
                        metavar='BASENAME',
                        dest='output_basename_prefix',
                        default='',
                        help='basename prefix of the output files; defaults to '
                             'the input file basename without extension')
    parser.add_argument('-q', '--quiet',
                        dest='info_file',
                        action='store_const', const=None,
                        default=fs.stdout,
                        help='do not print informational messages')
    parser.add_argument('--lib-dir',
                        metavar='DIR',
                        dest='lib_dir',
                        default=fs.MakeAbsolute(
                            self.__current_dir,
                            fs.join(fs.dirname(self.__main_file), 'lib')),
                        help='library directory, sets $dir.lib; '
                             'default: %(default)s')
    parser.add_argument('input_filename', metavar='filename',
                        help='root *.psc file to execute')
    args = parser.parse_args(self.__input_args)

    # Logger
    self.__logger = log.Logger(fmt=log.Logger.FORMATS[args.error_format],
                               err_file=fs.stderr,
                               info_file=args.info_file)

    # Constants
    self.__constants = dict(args.defines)
    self.__constants['format'] = args.format

    self.__args = args

  def __Execute(self):
    """Executes the action specified on the command-line."""
    fs = self.__fs
    constants = self.__constants
    args = self.__args

    # Compute the absolute input file path.
    input_path = Executor.ResolveFilePathStatic(
        args.input_filename,
        abs_directory=self.__current_dir,
        default_ext=PYSCRIBE_EXT,
        fs=fs)

    # Compute the path constants based on the input path.
    constants.update(
        _ComputePathConstants(
              fs=fs,
              current_dir=self.__current_dir,
              lib_dir=args.lib_dir,
              output_dir=args.output_dir,
              input_path=input_path,
              output_basename_prefix=args.output_basename_prefix))
    output_dir = constants['dir.output']
    output_path_prefix = \
        fs.MakeAbsolute(output_dir,
                        constants['file.output.basename.prefix'])

    # Create the output directory.
    fs.makedirs(output_dir, exist_ok=True)

    executor = Executor(logger=self.__logger, fs=fs,
                        current_dir=self.__current_dir,
                        output_path_prefix=output_path_prefix)

    # Set the constants.
    executor.AddConstants(constants)

    try:
      # Load and execute the input file.
      executor.ExecuteFile(input_path)
      executor.RenderBranches()
    except log.FatalError:
      if args.error_format == 'python':
        traceback.print_exc(file=fs.stderr)
      sys.exit(1)


def _ComputePathConstants(*, fs, current_dir, lib_dir, output_dir,
                          input_path, output_basename_prefix):
  """
  Returns the standard constant definitions for files and directories.

  Args:
    current_dir: (string) The current directory, used to resolve relative paths.
    lib_dir: (string) The path to the directory that contains core.psc.
    output_dir: (string) The path to the output directory.
    input_path: (string) The absolute path to the top-level file being executed.
    output_basename_prefix: (string) The basename prefix of all output files.
      Defaults to the basename of input_filename without extension if empty.

  Returns:
    (name string, value string) dict
  """
  output_dir = fs.MakeAbsolute(current_dir, output_dir)
  input_dir = fs.dirname(input_path)
  input_basename = fs.basename(input_path)
  input_basename_noext = fs.splitext(input_basename)[0]
  output_basename_prefix = output_basename_prefix or input_basename_noext

  constants = {
      'dir.lib': lib_dir,
      'dir.output': output_dir,
      'dir.input': input_dir,
      'dir.input.rel.output': fs.relpath(input_dir, output_dir),
      'file.input.basename': input_basename,
      'file.input.basename.noext': input_basename_noext,
      'file.output.basename.prefix': output_basename_prefix,
  }

  return {name: fs.MakeUnix(value) for name, value in constants.items()}


if __name__ == '__main__':
  Main().Run()
