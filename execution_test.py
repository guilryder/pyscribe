#!/usr/bin/env python3
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

import pathlib

from branches import TextBranch
from branch_macros import BRANCH_TYPES
from execution import *
from parsing import CallNode
from testutils import *


class ExecutorTest(TestCase):

  @macro(public_name='name')
  def MacroCallback(self):
    pass  # pragma: no cover

  def setUp(self):
    super().setUp()
    fs = self.GetFileSystem({
        '/exists-no-ext': '',
    })
    self.fs = fs
    self.logger = FakeLogger()
    self.executor = Executor(logger=self.logger, fs=fs,
                             current_dir=fs.Path('/cur'),
                             output_path_prefix=fs.Path('/output'))

  def testResolveFilePath_resolvesDots(self):
    self.assertEqual(
        self.executor.ResolveFilePath('/root/ignored/../dir/./file', '/cur'),
        self.fs.Path('/root/dir/file'))

  def testResolveFilePath_absolute_ignoresCurDir(self):
    self.assertEqual(
        self.executor.ResolveFilePath('/dir/file', '/ignored'),
        self.fs.Path('/dir/file'))

  def testResolveFilePath_relative_insertsCurDir(self):
    self.assertEqual(
        self.executor.ResolveFilePath('../sibling/file', '/cur/dir'),
        self.fs.Path('/cur/sibling/file'))

  def testResolveFilePath_relativeCurDir(self):
    self.assertEqual(
        self.executor.ResolveFilePath('../sibling/file', 'dir/sub'),
        self.fs.Path('/cur/dir/sibling/file'))

  def testResolveFilePath_noDefaultExt(self):
    self.assertEqual(
        self.executor.ResolveFilePath('/file', '/cur', default_ext=None),
        self.fs.Path('/file'))

  def testResolveFilePath_defaultExt_ignoresDir(self):
    self.assertEqual(
        self.executor.ResolveFilePath('/dir.foo/file', '/cur',
                                      default_ext='.ext'),
        self.fs.Path('/dir.foo/file.ext'))

  def testResolveFilePath_defaultExt_hiddenFile(self):
    self.assertEqual(
        self.executor.ResolveFilePath('/dir/.file', '/cur',
                                      default_ext='.ext'),
        self.fs.Path('/dir/.file.ext'))

  def testResolveFilePath_defaultExt_extPresent_fileNotExists(self):
    self.assertEqual(
        self.executor.ResolveFilePath('/dir/missing.ext', '/cur',
                                      default_ext='.ignored'),
        self.fs.Path('/dir/missing.ext'))

  def testResolveFilePath_defaultExt_extMissing_fileNotExists(self):
    self.assertEqual(
        self.executor.ResolveFilePath('/missing', '/cur', default_ext='.ext'),
        self.fs.Path('/missing.ext'))

  def testResolveFilePath_defaultExt_extMissing_fileWithoutExtExists(self):
    self.assertEqual(
        self.executor.ResolveFilePath('/exists-no-ext', '/cur',
                                      default_ext='.ext'),
        self.fs.Path('/exists-no-ext'))

  def testResolveFilePath_defaultExt_trailingDot(self):
    self.assertEqual(
        self.executor.ResolveFilePath('/file.', '/cur',
                                      default_ext='.ext'),
        self.fs.Path('/file..ext'))

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
    call_node = CallNode(TEST_LOCATION, 'name',
                         [str(i) for i in range(actual_args_count)])
    self.executor.CheckArgumentCount(
        call_node, self.MacroCallback, min_args_count, max_args_count)

  def assertCheckArgumentCountFailure(self, expected_error, *args, **kwargs):
    with self.assertRaises(FatalError) as ctx:
      self.CheckArgumentCount(*args, **kwargs)
    self.logger.LogException(ctx.exception)
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
    self.assertExecution(TEST_UNICODE, TEST_UNICODE)

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
              f'$if.eq[$i][{expected_loop_iterations}][][$loop]',
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

  def testOutputFileOpenedTwice_withoutSuffix(self):
    self.assertExecution(
        (
            '$branch.create.root[latex][new][]',
            '$branch.create.root[latex][new][]',
        ),
        messages=['/root:2: $branch.create.root: output file already opened: '
                  '/output'])

  def testOutputFileOpenedTwice_withSuffix(self):
    self.assertExecution(
        (
            '$branch.create.root[latex][new][.foo]',
            '$branch.create.root[latex][new][.foo]',
        ),
        messages=['/root:2: $branch.create.root: output file already opened: '
                  '/output.foo'])

  def testOutputFileOverwritesInput(self):
    self.assertExecution(
        {
            '/root': '$include[/output]',
            '/output.psc': '$branch.create.root[latex][new][.psc]',
        },
        messages=['/output.psc:1: $branch.create.root: '
                  'output file already opened: /output.psc',
                  '  /root:1: $include'])

  def testLatex(self):
    self.assertExecution(
        (
            '$branch.create.root[latex][new][.tex]',
            '$branch.write[new][%test&]',
        ),
        {'/output.tex': '\\%test\\&'})

  def testAllBranchTypes(self):
    for type_name in BRANCH_TYPES:
      executor = self.assertExecution(
          (
              f'$branch.create.root[{type_name}][new][.suffix]',
              '$branch.write[new][test]',
          ),
          {},
          expected_infos=['Writing: /output.suffix'])
      self.__VerifyBranchType(type_name,
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
          f'initial macros should be built-in: {callback.public_name}'
          f' in branch of type {branch_type_name}')


class ExecutorAddConstantsTest(ExecutionTestCase):

  def GetExecutionBranch(self, executor):
    executor.AddConstants({
        'one': 'value',
        'two': '$~!',
    })
    return executor.system_branch

  def testAddConstants(self):
    self.assertExecution('$one $two', 'value $~!')



class FileSystemTest(TestCase):

  fs = FileSystem()
  cwd = pathlib.Path.cwd()
  home = pathlib.Path.home()

  def testBasename(self):
    self.assertEqual(self.fs.basename(self.home / 'foo' / 'bar'), 'bar')

  def testGetcwd(self):
    self.assertEqual(self.fs.getcwd(), self.cwd)

  def testLexists_exists(self):
    self.assertTrue(self.fs.lexists(self.cwd))

  def testLexists_doesNotExist(self):
    self.assertFalse(self.fs.lexists(self.cwd / 'does' / 'not' / 'exist'))

  def testOpen(self):
    with self.fs.open(__file__, mode='rt') as f:
      self.assertIn('def testOpen(self)', f.read())

  def testMakedirs(self):
    self.fs.makedirs(self.cwd, exist_ok=True)

  def testRelpath_self(self):
    self.assertEqual(self.fs.relpath(self.cwd, self.cwd), '.')

  def testRelpath_grandChild(self):
    self.assertEqual(self.fs.relpath(self.cwd / 'foo' / 'bar', self.cwd),
                     str(self.fs.Path('foo', 'bar')))

  def testRelpath_grandParent(self):
    self.assertEqual(self.fs.relpath(self.cwd, self.cwd / 'foo' / 'bar'),
                     str(self.fs.Path('..', '..')))

  def testRelpath_sibling(self):
    self.assertEqual(self.fs.relpath(self.cwd / 'foo', self.cwd / 'bar'),
                     str(self.fs.Path('..', 'foo')))

  def testMakeAbsolute_alreadyAbsolute(self):
    absolute_path = self.home / 'foo' / 'bar'
    self.assertEqual(
        self.fs.MakeAbsolute(self.cwd, absolute_path),
        absolute_path)

  def testMakeAbsolute_relative(self):
    self.assertEqual(
        self.fs.MakeAbsolute(self.cwd, str(self.fs.Path('foo', 'bar'))),
        self.cwd / 'foo' / 'bar')

  def testMakeAbsolute_removesDot(self):
    self.assertEqual(
        self.fs.MakeAbsolute(
            self.cwd, str(self.cwd / '.' / 'foo' / '.' / 'bar' / '.')),
        self.cwd / 'foo' / 'bar')

  def testMakeAbsolute_normalizesDotDot(self):
    self.assertEqual(
        self.fs.MakeAbsolute(
            self.cwd, str(self.cwd / 'a' / 'b' / '..' / 'c' / '..' / 'd')),
        self.cwd / 'a' / 'd')


class FakeFileSystemTest(FileSystemTest):

  fs = FakeFileSystem()
  cwd = fs.cwd
  home = fs.Path('/fake/home')

  def testLexists_exists(self):
    with self.assertRaises(NotImplementedError):
      super().testLexists_exists()

  def testLexists_doesNotExist(self):
    with self.assertRaises(NotImplementedError):
      super().testLexists_doesNotExist()

  def testOpen(self):
    with self.assertRaises(NotImplementedError):
      super().testOpen()

  def testMakedirs(self):
    self.fs.InitializeForWrites()
    super().testMakedirs()



if __name__ == '__main__':
  unittest.main()
