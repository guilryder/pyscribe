#!/usr/bin/env python3
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

import io
import os
import re
import shlex
import shutil
import subprocess
import sys
import unittest

import pyscribify
import testutils


OUTPUT_DIR = testutils.TESTDATA_DIR / 'output'


class PyscribifyTestCase(unittest.TestCase):

  def setUp(self):
    self.__orig_cwd = os.getcwd()
    os.chdir(testutils.TESTDATA_DIR)

  def tearDown(self):
    os.chdir(self.__orig_cwd)


class EndToEndTest(PyscribifyTestCase):

  @classmethod
  def setUpClass(cls):
    if OUTPUT_DIR.is_dir():
      shutil.rmtree(OUTPUT_DIR)

  def testHello(self):
    try:
      pyscribify_output = subprocess.check_output(
          [sys.executable, '../pyscribify.py', 'Hello'],
          stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:  # pragma: no cover
      print(e.output.decode(), end='')
      raise

    try:
      # Verify the generated filenames.
      output_files_opened = []
      def OpenOutputFile(filename, mode):
        output_files_opened.append(filename)
        return open(OUTPUT_DIR / filename, mode,
                    encoding='utf8' if 't' in mode else None)

      # Compare Hello.tex with the golden.
      with OpenOutputFile('Hello.tex', 'rt') as output, (
           open('Hello.tex', encoding='utf8')) as golden:
        self.assertEqual(output.read(), golden.read(),
                         msg='Hello.tex mismatch')

      # Verify that the other files are valid, with heuristics.
      with OpenOutputFile('Hello.html', 'rt') as output:
        self.assertIn('<title>Hello World</title>', output.read(),
                      msg='Hello.html mismatch')
      with OpenOutputFile('Hello.kfx', 'rb') as output:
        self.assertEqual(output.read(4), b'CONT',
                      msg='Hello.kfx mismatch')
      with OpenOutputFile('Hello.pdf', 'rb') as output:
        self.assertEqual(output.read(4), b'%PDF',
                      msg='Hello.pdf mismatch')
      with OpenOutputFile('Hello.epub', 'rb') as output:
        self.assertEqual(output.read(4), b'PK\x03\x04',
                      msg='Hello.epub mismatch')

      self.assertEqual(
          list(sorted(os.listdir(OUTPUT_DIR))),
          list(sorted(output_files_opened)),
          msg='All Hello* files must be verified.')
    except:  # pragma: no cover
      print(pyscribify_output.decode(), end='')
      raise


class DryRunTest(PyscribifyTestCase):

  __HELLO_HEADER = [
      '',
      r'Processing.* Hello\.psc',
  ]

  __HELLO_PSC_TO_HTML = r'pyscribe.py.* Hello\.psc .*--format=html'
  __HELLO_HTML_TO_EPUB = r'ebook-convert.*Hello\.epub'
  __HELLO_EPUB_TO_KFX = r'calibre-debug.*Hello\.kfx'
  __HELLO_PSC_TO_LATEX = r'pyscribe.py.* Hello\.psc .*--format=latex'
  __HELLO_LATEX_TO_PDF = r'texify.*Hello\.tex'

  def __Pyscribify(self, args, pdftool='texify'):
    output = subprocess.check_output(
        [sys.executable, '../pyscribify.py',
        '--dry-run', '--latex-to-pdf-tool', pdftool] + list(args),
        stderr=subprocess.STDOUT)
    return [self.__ParseLogLine(line) for line in output.decode().splitlines()]

  @staticmethod
  def __ParseLogLine(line):
    """
    Canonicalizes a log line.

    If the line is for an execution, canonicalizes the command-line (removes
    extra backslashes and single quotes).

    Converts backslashes between letters (Windows path separators) into /.
    """
    match = re.search(r'^\(dry run\) Executing: (.*)', line)
    if match:
      line = ' '.join(shlex.split(match.group(1))).replace("'", "")
    return re.sub(r'(\w)\\(\w)', r'\1/\2', line)

  def __assertLines(self, actual_lines, expected_regexes):
    actual_lines = list(actual_lines)
    expected_regexes = list(expected_regexes)
    self.assertEqual(
        len(actual_lines), len(expected_regexes),
        msg='Executions count mismatch; got:\n' + '\n'.join(actual_lines))
    for actual_line, expected_regexp in zip(actual_lines, expected_regexes):
      self.assertRegex(actual_line, expected_regexp or r'^$')

  def testOneFile_allCommandLines_texify(self):
    self.__assertLines(
        self.__Pyscribify(['Hello']),
        [
            '',
            r'^Processing PyScribe file: Hello\.psc$',
            r"pyscribe\.py Hello\.psc"
              r" --lib-dir=.*/pyscribe/lib --format=html --output=output",
            r"ebook-convert.* output/Hello.html output/Hello.epub"
              r" .*--dont-split-on-page-breaks .*--no-default-epub-cover.*",
            r"calibre-debug.* -- --quality --logs"
              r" output/Hello.epub output/Hello.kfx",
            r"pyscribe\.py Hello\.psc"
              r" --lib-dir=.*/pyscribe/lib --format=latex --output=output",
            r"texify.* -I .+/pyscribe/lib Hello\.tex"
              r" --batch --pdf --clean --quiet",
        ])

  def testOneFile_latexToPdfOnly_latexmk(self):
    self.__assertLines(
        self.__Pyscribify(['Hello', '--latex-to-pdf'], pdftool='latexmk'),
        [
            '',
            r'^Processing PyScribe file: Hello\.psc$',
            r"latexmk.* Hello\.tex"
              r" -latexoption=-interaction=batchmode -pdf -gg",
            r"latexmk.* Hello\.tex -c",
        ])

  def testMultipleFiles(self):
    self.__assertLines(
        self.__Pyscribify(['One', 'Two', 'Three', '--psc-to-interm']),
        [
            '',
            r'Processing.* One\.psc',
            r'pyscribe.py.* One\.psc .*--format=html',
            r'pyscribe.py.* One\.psc .*--format=latex',
            '',
            r'Processing.* Two\.psc',
            r'pyscribe.py.* Two\.psc .*--format=html',
            r'pyscribe.py.* Two\.psc .*--format=latex',
            '',
            r'Processing.* Three\.psc',
            r'pyscribe.py.* Three\.psc .*--format=html',
            r'pyscribe.py.* Three\.psc .*--format=latex',
        ])

  def testOutput_texify(self):
    self.__assertLines(
        self.__Pyscribify(['Hello', '-o', 'foo/bar']),
        self.__HELLO_HEADER + [
            r'pyscribe.py.* Hello\.psc .*--format=html --output=foo/bar',
            r'ebook-convert.* foo/bar/Hello\.epub',
            r'calibre-debug.* foo/bar/Hello\.kfx',
            r'pyscribe.py.* Hello\.psc .*--format=latex --output=foo/bar',
            r'texify.* Hello\.tex',  # changes the current directory before
        ])

  def testFormats_htmlOnly(self):
    self.__assertLines(
        self.__Pyscribify(['Hello', '-f', 'html']),
        self.__HELLO_HEADER + [
            self.__HELLO_PSC_TO_HTML,
            self.__HELLO_HTML_TO_EPUB,
            self.__HELLO_EPUB_TO_KFX,
        ])

  def testFormats_latexOnly(self):
    self.__assertLines(
        self.__Pyscribify(['Hello', '-f', 'latex']),
        self.__HELLO_HEADER + [
            self.__HELLO_PSC_TO_LATEX,
            self.__HELLO_LATEX_TO_PDF,
        ])

  def testConversionOptions_one(self):
    self.__assertLines(
        self.__Pyscribify(['Hello', '--psc-to-html']),
        self.__HELLO_HEADER + [
            self.__HELLO_PSC_TO_HTML,
        ])

  def testConversionOptions_multipleDisconnected(self):
    self.__assertLines(
        self.__Pyscribify(['Hello', '--html-to-epub', '--psc-to-latex']),
        self.__HELLO_HEADER + [
            self.__HELLO_HTML_TO_EPUB,
            self.__HELLO_PSC_TO_LATEX,
        ])

  def testConversionOptions_redundantAliases(self):
    self.__assertLines(
        self.__Pyscribify(['Hello', '--html-to-epub', '--psc-to-epub']),
        self.__HELLO_HEADER + [
            self.__HELLO_PSC_TO_HTML,
            self.__HELLO_HTML_TO_EPUB,
        ])

  def testConversionOptions_recursive(self):
    self.__assertLines(
        self.__Pyscribify(['Hello', '--psc-to-ebook']),
        self.__HELLO_HEADER + [
            self.__HELLO_PSC_TO_HTML,
            self.__HELLO_HTML_TO_EPUB,
            self.__HELLO_EPUB_TO_KFX,
        ])

  def testConversionOptions_all(self):
    self.__assertLines(
        self.__Pyscribify([
            'Hello',
            '--psc-to-ebook',
            '--psc-to-epub',
            '--psc-to-kfx',
            '--psc-to-html',
            '--html-to-epub',
            '--html-to-kfx',
            '--epub-to-kfx',
            '--psc-to-pdf',
            '--latex-to-pdf',
            '--psc-to-all',
            '--psc-to-interm',
        ]),
        self.__HELLO_HEADER + [
            self.__HELLO_PSC_TO_HTML,
            self.__HELLO_HTML_TO_EPUB,
            self.__HELLO_EPUB_TO_KFX,
            self.__HELLO_PSC_TO_LATEX,
            self.__HELLO_LATEX_TO_PDF,
        ])

  def testCompilerOptions(self):
    options = [
        'Hello',
        '--lib-dir=foo/lib/dir',
        '--pyscribe-bin=/foo/pyscribe/bin',
        '--pyscribe-options=--pyscribe-opt -a',
        '--calibre-bin=/foo/calibre/bin',
        '--calibre-epub-options=--epub-opt -c',
        '--calibre-debug-bin=/foo/calibre-debug/bin',
        '--calibre-kfx-options=--kfx-opt -d',
        '--texify-bin=/foo/texify/bin',
        '--texify-options=--texify-opt -e',
        '--latexmk-bin=/foo/latexmk/bin',
        '--latexmk-options=--latexmk-opt -f',
        '--latexmk-clean-options=--latexmk-clean-opt -g',
    ]
    commands_common = self.__HELLO_HEADER + [
        r"^.+ .foo/pyscribe/bin Hello\.psc"
          r" --lib-dir=.+/testdata/foo/lib/dir --format=html"
          r" --output=output --pyscribe-opt -a",
        r"^.foo/calibre/bin output/Hello.html output/Hello.epub"
          r" --epub-opt -c",
        r"^.foo/calibre-debug/bin --kfx-opt -d"
          r" output/Hello.epub output/Hello.kfx",
        r"^.+ .foo/pyscribe/bin Hello\.psc"
          r" --lib-dir=.+/testdata/foo/lib/dir --format=latex"
          r" --output=output --pyscribe-opt -a",
    ]
    self.__assertLines(
        self.__Pyscribify(options, pdftool='texify'),
        commands_common + [
            r"^.foo/texify/bin -I .+/foo/lib/dir Hello\.tex --texify-opt -e",
        ])
    self.__assertLines(
        self.__Pyscribify(options, pdftool='latexmk'),
        commands_common + [
            r"^.foo/latexmk/bin Hello\.tex --latexmk-opt -f",
            r"^.foo/latexmk/bin Hello\.tex --latexmk-clean-opt -g",
        ])


class CoverageTest(PyscribifyTestCase):

  def testDryRun(self):
    for latex2pdf in ('texify', 'latexmk'):
      with self.subTest(latex2pdf=latex2pdf):
        self.__Run('Hello', '--dry-run', '--latex-to-pdf-tool', latex2pdf)

  def __Run(self, *args):
    output = io.StringIO()
    main = pyscribify.Main(
        input_args=args,
        stdout=output,
        ArgumentParser=lambda: testutils.FakeArgumentParser(output))
    with self.assertRaises(SystemExit):
      main.Run()


if __name__ == '__main__':
  testutils.unittest.main()
