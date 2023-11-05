#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

import latex
import testutils


class LatexEndToEndTest(testutils.ExecutionTestCase):

  def GetExecutionBranch(self, executor):
    return self.CreateBranch(executor, latex.LatexBranch)

  def InputHook(self, text):
    return '$$special.chars.latex.mode\n' + text

  def testBranchType(self):
    self.assertExecution('$identity[$branch.type]', 'latex')

  def testEmpty(self):
    self.assertExecution('', '')

  def testUnicode(self):
    self.assertExecution(testutils.TEST_UNICODE, testutils.TEST_UNICODE)

  def testEscape(self):
    self.assertExecution('^% ^&', '% &')

  def testSpecialChars_escapeAll(self):
    self.assertExecution(
        '$$special.chars.escape.all\n' + testutils.SPECIAL_CHARS,
        testutils.SPECIAL_CHARS_AS_LATEX_ESCAPE_ALL)

  def testSpecialChars_latexMode(self):
    self.assertExecution(
        testutils.SPECIAL_CHARS,
        testutils.SPECIAL_CHARS_AS_LATEX_ESCAPE_ALL.replace(
            r'\textbackslash{}', '\\'))

  def testOtherTextMacros(self):
    self.assertExecution(testutils.OTHER_TEXT_MACROS,
                         testutils.OTHER_TEXT_MACROS_AS_LATEX)

  def testLatexSep_beforeWhitelistedChars_noop(self):
    self.assertExecution(
        'a$latex.sep'.join(('', '\\', '^[', '^]', '^{', '^}', '^%')),
        r'a\a[a]a{a}a%')

  def testLatexSep_betweenBackslashes(self):
    self.assertExecution('\\$latex.sep\\', '\\ \\')

  def testLatexSep_beforeWhitespace_noop(self):
    self.assertExecution(
        'a$latex.sep'.join(('', ' ', '\t', '\n', '\r', '\r\n')) + 'a',
        'a a\ta\na\na\na')

  def testLatexSep_beforeRegularCharacter(self):
    self.assertExecution(
        'a$latex.sep'.join(('', '^X', '^#', '^_', '^3')),
        'a Xa #a _a 3')

  def testLatexSep_ignoresRepeatedCalls(self):
    self.assertExecution('^a$latex.sep$latex.sep^b', 'a b')

  def testLatexSep_ignoresRedundantCalls(self):
    self.assertExecution('^a $latex.sep $latex.sep ^b', 'a   b')

  def testLatexSep_ignoresAtBounds(self):
    self.assertExecution('$latex.sep^inside$latex.sep', 'inside')

  def testLatexSep_beforeBranch(self):
    self.assertExecution(
        (
            '$branch.create.sub[sub]',
            '$branch.write[sub][SUB]',
            'begin',
            '$latex.sep',
            '$branch.append[sub]',
            'end',
        ),
        'begin SUBend')

  def testLatexSep_afterBranch(self):
    self.assertExecution(
        (
            '$branch.create.sub[sub]',
            '$branch.write[sub][SUB]',
            'begin',
            '$branch.append[sub]',
            '$latex.sep',
            '^end',
        ),
        'beginSUB end')


  def testLatexSep_insideBranch(self):
    self.assertExecution(
        (
            '$branch.create.sub[sub]',
            '$branch.write[sub]['
              '$latex.sep',
              '^SUB',
              '$latex.sep',
            ']',
            'begin',
            '$branch.append[sub]',
            'end',
        ),
        'begin SUB end')

  def testLatexSep_acrossBranches_relevant(self):
    self.assertExecution(
        (
            '$branch.create.sub[a]',
            '$branch.create.sub[b]',
            '$branch.write[a][',
              '$branch.create.sub[nested]',
              '$branch.write[nested][',
                '$latex.sep',
                r'^\NESTED',
                '$latex.sep',
              ']',
              'A1\\',
              '$branch.append[nested]',
              'A2',
            ']',
            '$branch.write[b][',
              'B',
              '$latex.sep',
            ']',
            'begin',
            '$latex.sep',
            '$branch.append[a]',
            '$latex.sep',
            '$branch.append[b]',
            'end',
        ),
        r'begin A1\ \NESTED A2 B end')

  def testLatexSep_acrossBranches_noop(self):
    self.assertExecution(
        (
            '$branch.create.sub[a]',
            '$branch.create.sub[b]',
            '$branch.write[a][',
              '$branch.create.sub[nested]',
              '$branch.write[nested][',
                '$latex.sep',
                r'\NESTED',
                '$latex.sep',
              ']',
              r'\A1',
              '$branch.append[nested]',
              r'\A2',
            ']',
            '$branch.write[b][',
              r'\B',
              '$latex.sep',
            ']',
            'begin',
            '$latex.sep',
            '$branch.append[a]',
            '$latex.sep',
            '$branch.append[b]',
            '$latex.sep',
            r'\end',
        ),
        r'begin\A1\NESTED\A2\B\end')


if __name__ == '__main__':
  testutils.unittest.main()
