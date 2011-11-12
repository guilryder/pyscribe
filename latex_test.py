#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

from latex import *
from testutils import *


class LatexEndToEndTest(ExecutionTestCase):

  def GetExecutionBranch(self, executor):
    return self.CreateBranch(executor, LatexBranch)

  def testBranchType(self):
    self.assertExecution('$identity[$branch.type]', 'latex')

  def testEmpty(self):
    self.assertExecution('', '')

  def testUnicode(self):
    self.assertExecution(test_unicode, test_unicode)

  def testEscape(self):
    self.assertExecution('`% `&', '% &')

  def testAllSpecialChars(self):
    self.assertExecution(
        special_chars,
        u' '.join((
            u"\\% \\& \\_ $ \\$ # \\#",
            u"a~b",
            u"--c---",
            u"d…",
            u"«e»",
            u"« f »",
            u"'g'h'",
            u"i ! j: k ; l?",
            u"m!:;?",
        )))


if __name__ == '__main__':
  unittest.main()