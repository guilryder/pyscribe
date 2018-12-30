#!/usr/bin/env python3
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

import argparse
import sys
import traceback

from execution import PYSCRIBE_EXT, Executor, FileSystem
import log


class Main:

  def __init__(self, input_args, fs=FileSystem(), main_file=sys.argv[0],
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
                        dest='error_format',
                        default='simple',
                        choices=sorted(log.Logger.FORMATS),
                        help='error reporting format; default: %(default)s')
    parser.add_argument('-f', '--format', metavar='FORMAT',
                        dest='output_format',
                        default='',
                        help='format to render into; sets $output.format')
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
    self.__logger = log.Logger(fmt=log.Logger.FORMATS[args.error_format],
                               err_file=self.__fs.stderr,
                               info_file=args.info_file)

    # Constants
    self.__constants = dict(args.defines)
    self.__constants['output.format'] = args.output_format

    self.__args = args

  def __Execute(self):
    """Executes the action specified on the command-line."""
    args = self.__args
    fs = self.__fs
    out_dir = args.output_dir
    executor = Executor(out_dir, logger=self.__logger, fs=fs)
    executor.AddConstants(self.__constants)

    try:
      # Resolve the input filename.
      resolved_path = executor.ResolveFilePath(args.input_filename,
                                               cur_dir=self.__current_dir,
                                               default_ext=PYSCRIBE_EXT)

      # Set the constants that depend on the input filename.
      executor.AddConstants(_ComputePathConstants(
          fs,
          cur_dir=self.__current_dir,
          lib_dir=fs.join(fs.dirname(self.__main_file), 'usage'),
          out_dir=out_dir,
          input_filename=args.input_filename))

      # Load and execute the input file.
      executor.ExecuteFile(resolved_path)
      executor.RenderBranches()
    except log.FatalError:
      if args.error_format == 'python':
        traceback.print_exc(file=fs.stderr)
      sys.exit(1)


def _ComputePathConstants(fs, cur_dir, lib_dir, out_dir, input_filename):
  """
  Returns the standard constant definitions for files and directories.

  Args:
    cur_dir: (string) The current directory, used to resolve relative paths.
    lib_dir: (string) The path to the directory that contains core.psc.
    out_dir: (string) The path to the output directory.
    input_filename: (string) The path to the top-level file being executed.

  Returns:
    (name string, value string) dict
  """
  lib_dir = fs.MakeAbsolute(cur_dir, lib_dir)
  out_dir = fs.MakeAbsolute(cur_dir, out_dir)
  source_dir = fs.MakeAbsolute(cur_dir, fs.dirname(input_filename))

  def MakeRelativeToOutDir(abs_path):
    return fs.relpath(abs_path, out_dir)
  constants = {
      'dir.lib': lib_dir,
      'dir.lib.rel.output': MakeRelativeToOutDir(lib_dir),
      'dir.output': out_dir,
      'dir.source': source_dir,
      'dir.source.rel.output': MakeRelativeToOutDir(source_dir),
  }

  return {name: fs.MakeUnix(value) for name, value in constants.items()}


if __name__ == '__main__':
  Main(None).Run()
