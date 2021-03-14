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
from testutils import FakeArgumentParser, TESTDATA_DIR


OUTPUT_DIR = os.path.join(TESTDATA_DIR, 'output')


class PyscribifyTestCase(unittest.TestCase):

  def setUp(self):
    self.__orig_cwd = os.getcwd()
    os.chdir(os.path.join(TESTDATA_DIR))

  def tearDown(self):
    os.chdir(self.__orig_cwd)


class EndToEndTest(PyscribifyTestCase):

  @classmethod
  def setUpClass(cls):
    if os.path.isdir(OUTPUT_DIR):
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
        return open(os.path.join(OUTPUT_DIR, filename), mode)

      # Compare Hello.tex with the golden.
      with OpenOutputFile('Hello.tex', 'rt') as output, \
           open('Hello.tex', 'rt') as golden:
        self.assertEqual(output.read(), golden.read(),
                         msg='Hello.tex mismatch')

      # Verify that the other files are valid, with heuristics.
      with OpenOutputFile('Hello.html', 'rt') as output:
        self.assertIn('<title>Hello World</title>', output.read(),
                      msg='Hello.html mismatch')
      with OpenOutputFile('Hello.mobi', 'rb') as output:
        self.assertIn(b'BOOKMOBI', output.read(),
                      msg='Hello.mobi mismatch')
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
  __HELLO_HTML_TO_MOBI = r'ebook-convert.*Hello\.mobi'
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
              r" --toc-filter=" + re.escape(r'\[[0-9]+\]') +
              r" --dont-split-on-page-breaks --no-default-epub-cover",
            r"ebook-convert.* output/Hello.html output/Hello.mobi"
              r" --toc-filter=" + re.escape(r'\[[0-9]+\]') +
              r" --no-inline-toc --mobi-keep-original-images --cover=.*nul",
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
            r'ebook-convert.* foo/bar/Hello\.mobi',
            r'pyscribe.py.* Hello\.psc .*--format=latex --output=foo/bar',
            r'texify.* Hello\.tex',  # changes the current directory before
        ])

  def testFormats_htmlOnly(self):
    self.__assertLines(
        self.__Pyscribify(['Hello', '-f', 'html']),
        self.__HELLO_HEADER + [
            self.__HELLO_PSC_TO_HTML,
            self.__HELLO_HTML_TO_EPUB,
            self.__HELLO_HTML_TO_MOBI,
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
            self.__HELLO_HTML_TO_MOBI,
        ])

  def testConversionOptions_all(self):
    self.__assertLines(
        self.__Pyscribify([
            'Hello',
            '--psc-to-ebook',
            '--psc-to-epub',
            '--psc-to-mobi',
            '--psc-to-html',
            '--html-to-epub',
            '--html-to-mobi',
            '--psc-to-pdf',
            '--latex-to-pdf',
            '--psc-to-all',
            '--psc-to-interm',
        ]),
        self.__HELLO_HEADER + [
            self.__HELLO_PSC_TO_HTML,
            self.__HELLO_HTML_TO_EPUB,
            self.__HELLO_HTML_TO_MOBI,
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
        '--calibre-options=--calibre-opt -b',
        '--calibre-epub-options=--epub-opt -c',
        '--calibre-mobi-options=--mobi-opt -d',
        '--texify-bin=/foo/texify/bin',
        '--texify-options=--texify-opt -e',
        '--latexmk-bin=/foo/latexmk/bin',
        '--latexmk-options=--latexmk-opt -f',
        '--latexmk-clean-options=--latexmk-clean-opt -g',
    ]
    commands_common = self.__HELLO_HEADER + [
        r"^.+ /foo/pyscribe/bin Hello\.psc"
          r" --lib-dir=.+/testdata/foo/lib/dir --format=html"
          r" --output=output --pyscribe-opt -a",
        r"^/foo/calibre/bin output/Hello.html output/Hello.epub"
          r" --calibre-opt -b --epub-opt -c",
        r"^/foo/calibre/bin output/Hello.html output/Hello.mobi"
          r" --calibre-opt -b --mobi-opt -d",
        r"^.+ /foo/pyscribe/bin Hello\.psc"
          r" --lib-dir=.+/testdata/foo/lib/dir --format=latex"
          r" --output=output --pyscribe-opt -a",
    ]
    self.__assertLines(
        self.__Pyscribify(options, pdftool='texify'),
        commands_common + [
            r"^/foo/texify/bin -I .+/foo/lib/dir Hello\.tex --texify-opt -e",
        ])
    self.__assertLines(
        self.__Pyscribify(options, pdftool='latexmk'),
        commands_common + [
            r"^/foo/latexmk/bin Hello\.tex --latexmk-opt -f",
            r"^/foo/latexmk/bin Hello\.tex --latexmk-clean-opt -g",
        ])


class CoverageTest(PyscribifyTestCase):

  def testDryRun(self):  # pylint: disable=no-self-use
    output = io.StringIO()
    main = pyscribify.Main(input_args=('Hello', '--dry-run'), stdout=output,
                           ArgumentParser=lambda: FakeArgumentParser(output))
    with self.assertRaises(SystemExit):
      main.Run()


if __name__ == '__main__':
  unittest.main()
