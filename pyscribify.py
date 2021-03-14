#!/usr/bin/env python3
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license
# pragma: no cover

__author__ = 'Guillaume Ryder'

import argparse
import os
import platform
import shlex
import shutil
import subprocess
import sys


_FORMATS = ('html', 'latex')


def _TryFindExecutable(filename, default=None):
  return shutil.which(filename) or default or filename


class Main:

  def __init__(self, *, input_args=None, stdout=sys.stdout,
               ArgumentParser=argparse.ArgumentParser):
    self.__input_args = input_args
    self.__stdout = stdout
    self.__ArgumentParser = ArgumentParser
    self.__all_success = True
    self.__pyscribe_dir = os.path.dirname(sys.argv[0])

  def Run(self):
    self.__ParseArguments()

    for psc_filename in self.__args.psc_filenames:
      self.__ProcessSourceFile(psc_filename)

    sys.exit(0 if self.__all_success else 1)

  def __ParseArguments(self):
    """
    Parses the command-line arguments given at construction.

    Quits on error or if --help is passed.

    Stores the parsed arguments in self.__args.
    """
    # pylint: disable=attribute-defined-outside-init
    parser = self.__ArgumentParser()

    parser.add_argument('-o', '--output', metavar='DIR', dest='output_dir',
                        default='output',
                        help='output directory, absolute or relative to each'
                             ' source file')

    parser.add_argument('psc_filenames', metavar='PSC-FILE', nargs='+',
                        help='source PyScribe files, *.psc extension optional')

    parser.add_argument('-f', '--formats', dest='formats', nargs='+',
                        type=str, choices=_FORMATS, default=_FORMATS,
                        help='run conversions only for the specified formats,'
                             ' even if --X-to-Y flags for other formats are'
                             ' set; default: all formats')

    parser.add_argument('-n', '--dry-run', dest='dry_run', action='store_true',
                        help='print the shell commands without running them')

    aliases = {}  # (from_arg, to_arg tuple) dict, *NOT* topologically sorted

    def AddAlias(args_group, from_flag, to_flags, help_suffix=''):
      aliases[from_flag] = to_flags
      args_group.add_argument('--' + from_flag, action='store_true',
                              help='alias for ' +
                                   ' '.join('--' + flag for flag in to_flags) +
                                   help_suffix)

    # Conversions to perform.
    group = parser.add_argument_group('HTML-based conversions (ePub, Mobi)')
    AddAlias(group, 'psc-to-ebook', ('psc-to-epub', 'psc-to-mobi'))
    AddAlias(group, 'psc-to-epub', ('psc-to-html', 'html-to-epub'))
    AddAlias(group, 'psc-to-mobi', ('psc-to-html', 'html-to-mobi'))
    group.add_argument('--psc-to-html', action='store_true',
                       help='compile the *.psc files to HTML with PyScribe')
    group.add_argument('--html-to-epub', action='store_true',
                       help='compile the HTML files to ePub with Calibre')
    group.add_argument('--html-to-mobi', action='store_true',
                       help='compile the HTML files to Mobi with Calibre')

    group = parser.add_argument_group('Latex-based conversions (PDF)')
    AddAlias(group, 'psc-to-pdf', ('psc-to-latex', 'latex-to-pdf'))
    group.add_argument('--psc-to-latex', action='store_true',
                       help='compile the *.psc files to Latex with PyScribe')
    group.add_argument('--latex-to-pdf', action='store_true',
                       help='compile the Latex files to PDF with'
                            ' --latex-to-pdf-tool')
    group.add_argument('--latex-to-pdf-tool',
                       choices=('texify', 'latexmk'),
                       default='texify' if platform.system() == 'Windows'
                               else 'latexmk',
                       help='Latex to PDF compiler; default: %(default)s')

    group = parser.add_argument_group('Convenience aliases')
    AddAlias(group, 'psc-to-all', ('psc-to-ebook', 'psc-to-pdf'),
             help_suffix='; enabled by default to no --X-to-Y flag is set')
    AddAlias(group, 'psc-to-interm', ('psc-to-html', 'psc-to-latex'))

    # Compiler options.
    group = parser.add_argument_group('Compiler options')
    group.add_argument('--lib-dir', metavar='DIR',
                       default=os.path.join(self.__pyscribe_dir, 'lib'),
                       help='PyScribe library directory; default: %(default)s')

    group.add_argument('--pyscribe-bin', metavar='PATH',
                       default=os.path.join(self.__pyscribe_dir, 'pyscribe.py'),
                       help='PyScribe path; default: %(default)s')
    group.add_argument('--pyscribe-options', metavar='OPTIONS',
                       default='',
                       help='extra command-line options for PyScribe')

    group.add_argument('--calibre-bin', metavar='PATH',
                       default=_TryFindExecutable(
                          'ebook-convert',
                          r'C:\Program Files\Calibre\ebook-convert.exe'
                              if platform.system() == 'Windows' else None),
                       help='Calibre converter path; default: %(default)s')
    group.add_argument('--calibre-options', metavar='OPTIONS',
                       default=r'--toc-filter="\[[0-9]+\]"',
                       help='shared command-line options for Calibre'
                            '; default: %(default)s')
    group.add_argument('--calibre-epub-options', metavar='OPTIONS',
                       default='--dont-split-on-page-breaks'
                               ' --no-default-epub-cover',
                       help='ePub-specific command-line options for Calibre'
                            '; default: %(default)s')
    group.add_argument('--calibre-mobi-options', metavar='OPTIONS',
                       default='--no-inline-toc --mobi-keep-original-images'
                               ' --cover=' + os.devnull,
                       help='Mobi-specific command-line options for Calibre'
                            '; default: %(default)s')

    group.add_argument('--texify-bin', metavar='PATH',
                       default=_TryFindExecutable('texify'),
                       help='texify path; default: %(default)s')
    group.add_argument('--texify-options', metavar='OPTIONS',
                       default='--batch --pdf --clean --quiet',
                       help='texify command-line options; default: %(default)s')

    group.add_argument('--latexmk-bin', metavar='PATH',
                       default=_TryFindExecutable('latexmk'),
                       help='latexmk path; default: %(default)s')
    group.add_argument('--latexmk-options', metavar='OPTIONS',
                       default='-latexoption=-interaction=batchmode -pdf -gg',
                       help='latexmk command-line options'
                            '; default: %(default)s')
    group.add_argument('--latexmk-clean-options', metavar='OPTIONS',
                       default='-c',
                       help='latexmk cleanup command-line options'
                            '; default: %(default)s')

    self.__args = args = parser.parse_args(self.__input_args)

    # Default to --psc-to-all if no --X-to-Y is set.
    args.psc_to_all |= not any('_to_' in name and value is True
                               for name, value in vars(args).items())

    # Propagate the convenience aliases. Not optimal (should use a topologically
    # sorted list of aliases) but good enough.
    def PropagateFlag(flag, force_true):
      arg_name = flag.replace('-', '_')
      if force_true:
        setattr(args, arg_name, True)
      elif not getattr(args, arg_name):
        return
      for to_flag in aliases.pop(flag, ()):
        PropagateFlag(to_flag, True)
    for from_flag in list(aliases):
      PropagateFlag(from_flag, force_true=False)

    # Make paths absolute.
    args.lib_dir = os.path.abspath(args.lib_dir)

  def __ProcessSourceFile(self, psc_filename):
    args = self.__args

    # Append the default *.psc extension if necessary.
    if not os.path.splitext(psc_filename)[1] \
        and not os.path.lexists(psc_filename):
      psc_filename += '.psc'
    basename_noext = os.path.splitext(os.path.basename(psc_filename))[0]

    # Compute the paths of output files.
    output_dir = os.path.join(os.path.dirname(psc_filename), args.output_dir)
    output_path_noext = os.path.join(output_dir, basename_noext)

    print('\nProcessing PyScribe file: {}'.format(psc_filename),
          file=self.__stdout)

    # HTML.
    if 'html' in args.formats:
      # PyScribe to HTML.
      psc_to_html_success = True
      if args.psc_to_html:
        psc_to_html_success &= self.__CallPyscribe(
            psc_filename=psc_filename, output_dir=output_dir,
            psc_format='html')

      # HTML to ePub.
      if psc_to_html_success and args.html_to_epub:
        self.__CallCalibre(input_path=output_path_noext + '.html',
                           output_path=output_path_noext + '.epub',
                           extra_options=args.calibre_epub_options)

      # HTML to Mobi.
      if psc_to_html_success and args.html_to_mobi:
        self.__CallCalibre(input_path=output_path_noext + '.html',
                           output_path=output_path_noext + '.mobi',
                           extra_options=args.calibre_mobi_options)

    # Latex.
    if 'latex' in args.formats:
      # PyScribe to Latex.
      psc_to_latex_success = True
      if args.psc_to_latex:
        psc_to_latex_success &= self.__CallPyscribe(
            psc_filename=psc_filename, output_dir=output_dir,
            psc_format='latex')

      # Latex to PDF.
      if psc_to_latex_success and args.latex_to_pdf:
        if args.latex_to_pdf_tool == 'texify':
          # With texify.
          self.__CallProgram(args.texify_bin,
                             '-I', args.lib_dir,
                             basename_noext + '.tex',
                             *shlex.split(args.texify_options),
                             cwd=output_dir)
        elif args.latex_to_pdf_tool == 'latexmk':
          # With latexmk.
          env = os.environ.copy()
          env['TEXINPUTS'] = '{}:'.format(args.lib_dir)
          self.__CallProgram(args.latexmk_bin,
                             basename_noext + '.tex',
                             *shlex.split(args.latexmk_options),
                             cwd=output_dir, env=env)
          self.__CallProgram(args.latexmk_bin,
                             basename_noext + '.tex',
                             *shlex.split(args.latexmk_clean_options),
                             cwd=output_dir)

  def __CallPyscribe(self, *, psc_filename, output_dir, psc_format):
    args = self.__args
    return self.__CallProgram(
        sys.executable, args.pyscribe_bin,
        psc_filename,
        '--lib-dir=' + args.lib_dir,
        '--format=' + psc_format,
        '--output=' + output_dir,
        *shlex.split(args.pyscribe_options))

  def __CallCalibre(self, *, input_path, output_path, extra_options):
    args = self.__args
    return self.__CallProgram(
        args.calibre_bin, input_path, output_path,
        *(shlex.split(args.calibre_options) + shlex.split(extra_options)))

  def __CallProgram(self, *args, **kwargs):
    """
    Invokes a program.

    Args:
      *args: the command-line arguments, with the program absolute path first.
      **kwargs: extra options for subprocess.call().
    Returns: (bool) Whether the execution succeeded.
    """
    print('{prefix}Executing: {cmdline}'.format(
            prefix='(dry run) ' if self.__args.dry_run else '',
            cmdline=' '.join(map(shlex.quote, args))),
          flush=True, file=self.__stdout)

    if self.__args.dry_run:
      return True

    try:  # pragma: no cover - covered by end-to-end tests
      subprocess.check_call(args, **kwargs)
    except subprocess.CalledProcessError:  # pragma: no cover
      self.__all_success = False
      return False
    else:  # pragma: no cover
      return True


if __name__ == '__main__':
  Main().Run()
