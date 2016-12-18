#!/usr/bin/env python
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

from builtin_macros import BRANCH_TYPES
from execution import *
from parsing import CallNode
from testutils import *


class TextBranchTest(BranchTestCase):

  def setUp(self):
    super(TextBranchTest, self).setUp()
    self.branch = TextBranch(parent=None, name='dummy')

  def assertRender(self, expected):
    with self.FakeOutputFile() as writer:
      self.branch.writer = writer
      self.branch.Render()
      self.assertEqual(writer.getvalue(), expected)

  def testRepr(self):
    self.assertEqual(repr(self.branch), '<TextBranch: dummy>')

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

  @macro(public_name='name')
  def MacroCallback(self):
    pass  # pragma: no cover

  def setUp(self):
    super(ExecutorTest, self).setUp()
    self.logger = FakeLogger()
    self.executor = Executor(output_dir='output', logger=self.logger)

  def testSystemBranch(self):
    self.assertEqual(self.executor.branches.get('system'),
                     self.executor.system_branch)
    self.assertIn(self.executor.system_branch, self.executor.root_branches)

  def testRegisterBranch_alreadyNamed(self):
    branch = TextBranch(parent=None, name='test')
    self.executor.RegisterBranch(branch)
    self.assertEqual(branch.name, 'test')
    self.assertEqual(self.executor.branches.get('test'), branch)

  def testRegisterBranch_unnamed(self):
    branch1 = TextBranch(parent=None)
    self.executor.RegisterBranch(branch1)
    branch2 = TextBranch(parent=None)
    self.executor.RegisterBranch(branch2)
    self.assertEqual(branch1.name, 'auto1')
    self.assertEqual(branch2.name, 'auto2')

  def testRegisterBranch_root(self):
    branch = TextBranch(parent=None)
    self.executor.RegisterBranch(branch)
    self.assertEqual(self.executor.branches.get(branch.name), branch)
    self.assertIn(branch, self.executor.root_branches)

  def testRegisterBranch_nonRoot(self):
    branch_root = TextBranch(parent=None)
    branch_child = TextBranch(parent=branch_root)
    self.executor.RegisterBranch(branch_child)
    self.assertEqual(self.executor.branches.get(branch_child.name),
                     branch_child)
    self.assertNotIn(branch_child, self.executor.root_branches)

  def testRegisterBranch_registersSubBranches(self):
    branch_root = TextBranch(parent=None)
    branch_child = TextBranch(parent=branch_root)
    branch_grand_child = TextBranch(parent=branch_child)
    self.executor.RegisterBranch(branch_root)
    self.assertEqual(branch_root.name, 'auto1')
    self.assertEqual(branch_child.name, 'auto2')
    self.assertEqual(branch_grand_child.name, 'auto3')

  def CheckArgumentCount(self, min_args_count, max_args_count,
                         actual_args_count):
    call_node = CallNode(test_location, 'name',
                         [str(i) for i in range(actual_args_count)])
    self.executor.CheckArgumentCount(
        call_node, self.MacroCallback, min_args_count, max_args_count)

  def assertCheckArgumentCountFailure(self, expected_error, *args, **kwargs):
    with self.assertRaises(FatalError):
      self.CheckArgumentCount(*args, **kwargs)
    self.assertEqual(self.logger.ConsumeStdErr(),
                     'file.txt:42: $name: ' + expected_error)

  def testCheckArgumentCount_minAndMax(self):
    self.CheckArgumentCount(0, 4, actual_args_count=0)
    self.CheckArgumentCount(0, 4, actual_args_count=4)
    self.CheckArgumentCount(1, 4, actual_args_count=2)
    self.CheckArgumentCount(2, 3, actual_args_count=2)
    self.CheckArgumentCount(2, 2, actual_args_count=2)
    self.assertCheckArgumentCountFailure(
        'arguments count mismatch: expected 1..4, got 5',
        1, 4, actual_args_count=5)
    self.assertCheckArgumentCountFailure(
        'arguments count mismatch: expected 2, got 3',
        2, 2, actual_args_count=3)

  def testCheckArgumentCount_implicitMax(self):
    self.CheckArgumentCount(0, None, actual_args_count=0)
    self.CheckArgumentCount(2, None, actual_args_count=2)
    self.assertCheckArgumentCountFailure(
        'arguments count mismatch: expected 1, got 2',
        1, None, actual_args_count=2)
    self.assertCheckArgumentCountFailure(
        'arguments count mismatch: expected 2, got 0',
        2, None, actual_args_count=0)

  def testCheckArgumentCount_noMax(self):
    self.CheckArgumentCount(0, -1, actual_args_count=0)
    self.CheckArgumentCount(2, -1, actual_args_count=2)
    self.assertCheckArgumentCountFailure(
        'arguments count mismatch: expected at least 2, got 1',
        2, -1, actual_args_count=1)


class ExecutorEndToEndTest(ExecutionTestCase):

  def testBranchType(self):
    self.assertExecution('$identity[$branch.type]', 'text')

  def testEmpty(self):
    self.assertExecution('', '', expected_infos=[])

  def testUnicode(self):
    self.assertExecution(test_unicode, test_unicode)

  def testSyntaxError(self):
    self.assertExecution(
        '$identity[',
        messages=['/root:1: syntax error: macro argument should be closed'],
        expected_infos=[])

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

  def testMaxNestedCalls_limitReached(self):
    self.assertExecution(
        (
            '$macro.new[recurse][x$recurse]',
            '$recurse',
        ),
        messages=['/root:1: $recurse: too many nested macro calls'] +
                 ['  /root:1: $recurse'] * (MAX_NESTED_CALLS - 1) +
                 ['  /root:2: $recurse'])

  def testMaxNestedCalls_limitNotReached(self):
    expected_loop_iterations = MAX_NESTED_CALLS//2 - 1
    self.assertExecution(
        (
            '$counter.create[i]',
            '$macro.new[loop][',
              '$i ',
              '$i.incr',
              '$if.eq[$i][%d][][$loop]' % expected_loop_iterations,
            ']',
            '$loop',
        ),
        ' '.join(map(str, range(expected_loop_iterations))) + ' ')

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

  def testAllBranchTypes(self):
    for branch_type_name in BRANCH_TYPES:
      executor = self.assertExecution(
          (
              '$branch.create.root[%s][new][newoutput]' % branch_type_name,
              '$branch.write[new][test]',
          ),
          {},
          expected_infos=['Writing: /output/newoutput'])
      self.__VerifyBranchType(branch_type_name,
                              executor.branches.get('new').context)

  def __VerifyBranchType(self, branch_type_name, context):
    # Collect all macros available in the branch.
    macros = []
    while context:
      macros.extend(context.macros.values())
      context = context.parent
    self.assertGreater(len(macros), 10)

    # Check that the macros are all built-in.
    for callback in macros:
      self.assertTrue(
          callback.builtin,
          'initial macros should be built-in: {0} in branch of type {1}'.format(
              callback.public_name, branch_type_name))


class ExecutorAddConstantsTest(ExecutionTestCase):

  def GetExecutionBranch(self, executor):
    executor.AddConstants({
        'one': 'value',
        'two': '$~!',
    })
    return executor.system_branch

  def testAddConstants(self):
    self.assertExecution('$one $two', 'value $~!')


if __name__ == '__main__':
  unittest.main()
