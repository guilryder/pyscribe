#!/usr/bin/env python
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

import collections

from executor import *
from testutils import *


class TextBranchTest(BranchTestCase):

  def setUp(self):
    super(TextBranchTest, self).setUp()
    self.branch = TextBranch(parent=None)

  def assertRender(self, expected):
    writer = self.FakeOutputFile()
    self.branch.writer = writer
    self.branch.Render()
    self.assertEqual(expected, writer.getvalue())

  def testRender_empty(self):
    self.assertRender('')

  def testRender_text(self):
    self.branch.AppendText('one ')
    self.branch.AppendText('two ')
    self.branch.AppendText('three ')
    self.assertRender('one two three ')

  def testRender_mix(self):
    self.PrepareMix(self.branch)
    self.assertRender('one sub1 sub12 two sub21 three ')

  def testRender_unattachedBranch(self):
    self.branch.CreateSubBranch()
    self.branch.AppendText('test')
    self.assertRender('test')


class ExecutorTest(TestCase):

  def setUp(self):
    super(ExecutorTest, self).setUp()
    self.logger = FakeLogger()
    self.executor = Executor(output_dir='output', logger=self.logger)

  def testSystemBranch(self):
    self.assertEqual(self.executor.system_branch,
                     self.executor.branches.get('system'))
    self.assertTrue(self.executor.system_branch in self.executor.root_branches)

  def testRegisterBranch_alreadyNamed(self):
    branch = TextBranch(parent=None, name='test')
    self.executor.RegisterBranch(branch)
    self.assertEqual('test', branch.name)
    self.assertEqual(branch, self.executor.branches.get('test'))

  def testRegisterBranch_unnamed(self):
    branch1 = TextBranch(parent=None)
    self.executor.RegisterBranch(branch1)
    branch2 = TextBranch(parent=None)
    self.executor.RegisterBranch(branch2)
    self.assertEqual('auto1', branch1.name)
    self.assertEqual('auto2', branch2.name)

  def testRegisterBranch_root(self):
    branch = TextBranch(parent=None)
    self.executor.RegisterBranch(branch)
    self.assertEqual(branch, self.executor.branches[branch.name])
    self.assertTrue(branch in self.executor.root_branches)

  def testRegisterBranch_nonRoot(self):
    branch_root = TextBranch(parent=None)
    branch_child = TextBranch(parent=branch_root)
    self.executor.RegisterBranch(branch_child)
    self.assertEqual(branch_child, self.executor.branches[branch_child.name])
    self.assertFalse(branch_child in self.executor.root_branches)

  def testRegisterBranch_registersSubBranches(self):
    branch_root = TextBranch(parent=None)
    branch_child = TextBranch(parent=branch_root)
    branch_grand_child = TextBranch(parent=branch_child)
    self.executor.RegisterBranch(branch_root)
    self.assertEqual('auto1', branch_root.name)
    self.assertEqual('auto2', branch_child.name)
    self.assertEqual('auto3', branch_grand_child.name)


class ExecutorEndToEndTest(ExecutionTestCase):

  def testBranchType(self):
    self.assertExecution('$identity[$branch.type]', 'text')

  def testEmpty(self):
    self.assertExecution('', '')

  def testUnicode(self):
    self.assertExecution(test_unicode, test_unicode)

  def testSyntaxError(self):
    self.assertExecution(
        '$identity[',
        messages=['/root:1: syntax error: macro argument not closed'])

  def testMacroNotFoundError(self):
    self.assertExecution(
        '$dummy.macro',
        messages=['/root:1: macro not found: $dummy.macro'])

  def testMacroNotFoundError_nested(self):
    self.assertExecution(
        (
            '$macro.new[main][$dummy.macro]',
            '$main',
        ),
        messages=['/root:1: macro not found: $dummy.macro',
                  '  /root:2: $main'])

  def testMaxNestedCalls(self):
    self.assertExecution(
        (
            '$macro.new[recurse][x$recurse]',
            '$recurse',
        ),
        messages=['/root:1: $recurse: too many nested macro calls'] +
                 ['  /root:1: $recurse'] * 24 +
                 ['  /root:2: $recurse'])

  def testTextCompatible_simpleText(self):
    self.assertExecution('$eval.text[test]', 'test')

  def testTextCompatible_recursive(self):
    self.assertExecution(
        '$eval.text[before $eval.text[inside] after]',
        'before inside after')

  def testTextCompatible_rejectsTextIncompatible(self):
    self.assertExecution(
        (
            '$identity[',
                '$eval.text[',
                    'before ',
                    '$identity[inside]',
                    ' after',
                ']',
            ']',
        ),
        messages=['/root:4: $identity: text-incompatible macro call',
                  '  /root:2: $eval.text',
                  '  /root:1: $identity'])

  def testLatex(self):
    self.assertExecution(
        (
            '$branch.create.root[latex][new][newtex]',
            '$branch.write[new][%test&]',
        ),
        {'/output/newtex': '\\%test\\&'})


if __name__ == '__main__':
  unittest.main()
