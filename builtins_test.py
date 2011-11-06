#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

import collections
import os

from builtins import *
from executor import *
from testutils import *


class SpecialCharsTest(ExecutionTestCase):

  def testAll(self):
    self.assertExecution(
        special_chars,
        ' '.join((
            u"% &",
            u"a\xa0b",
            u"–c—",
            u"d…",
            u"«e»",
            u"« f »",
            u"'g'h'",
            u"i ! j: k ; l?",
            u"m!:;?",
        )))


class IncludeTest(ExecutionTestCase):

  def testNested(self):
    self.assertExecution(
        {
            '/root': 'roota $include[one.psc]rootb',
            '/one.psc': '1a $include[two.psc]1b` ',
            '/two.psc': '2a $include[three.psc]2b` ',
            '/three.psc': '3` ',
        },
        'roota 1a 2a 3 2b 1b rootb')

  def testRecursive(self):
    self.assertExecution(
        {
            '/root': (
                '$macro.new[callA][$include[a]]',
                '$macro.new[callB][$include[b]]',
                '$callA',
            ),
            '/a': (
                'A ',
                '$callB',
            ),
            '/b': (
                'B ',
                '$macro.new[callB][end]',
                '$callA',
            ),
        },
        'A B A end')

  def testFileNotFound(self):
    self.assertExecution(
        '$include[dummy]',
        messages=['/root:1: $include: unable to include "dummy": ' +
                  'file not found: /dummy'])

  def testMaxNestedIncludes(self):
    self.assertExecution(
        'test$include[/root]',
        messages=['/root:1: $include: unable to include "/root": ' +
                  'too many nested includes'] +
                 ['  /root:1: $include'] * 24)


class MacroNewTest(ExecutionTestCase):

  def testNoArgs(self):
    self.assertExecution(
        (
            '$macro.new[alias][value]',
            '$alias',
        ),
        'value')

  def testTwoArgs(self):
    self.assertExecution(
        (
            '$macro.new[plusRule(a,b)][$a + $b = $b + $a]',
            '$plusRule[1][2]',
        ),
        '1 + 2 = 2 + 1')

  def testNestedCallsSameArgumentNames(self):
    self.assertExecution(
        (
            '$macro.new[plusRule(a,b)][$a + $b = $b + $a]',
            '$macro.new[plus(a,b)][$a + $b]',
            '$macro.new[minus(a,b)][$a - ($b)]',
            '$plusRule[$minus[$minus[6][1]][2]][$minus[3][$plus[4][5]]]',
        ),
        '6 - (1) - (2) + 3 - (4 + 5) = 3 - (4 + 5) + 6 - (1) - (2)')

  def testArgumentsCountMismatch(self):
    self.assertExecution(
        '$macro.new[1]',
        messages=['/root:1: $macro.new(signature,*body): ' +
                  'arguments count mismatch: expected 2, got 1'])
    self.assertExecution(
        '$macro.new[1][2][3]',
        messages=['/root:1: $macro.new(signature,*body): ' +
                  'arguments count mismatch: expected 2, got 3'])

  def testDuplicateSignatureArguments(self):
    self.assertExecution(
        '$macro.new[test(one,two,three,two)][body]',
        messages=['/root:1: $macro.new: duplicate argument in signature: two'])

  def testTextCompatible(self):
    self.assertExecution(
        (
            '$macro.new[double(arg)][$arg$arg]',
            '$macro.new[$double[test](arg)][!$arg!]',
            '$testtest[input]'
        ),
        '!input!')

  def testInvalidSignature(self):
    self.assertExecution(
        '$macro.new[macro(][blah]',
        messages=['/root:1: $macro.new: invalid signature: macro('])
    self.assertExecution(
        '$macro.new[macro()(][blah]',
        messages=['/root:1: $macro.new: invalid signature: macro()('])

  def testBranchScope(self):
    self.assertExecution(
        (
            '$macro.new[top][$macro.new[sub(arg)][inside sub: $arg]]',
            '$top'
            '$sub[test]',
        ),
        'inside sub: test')

  def testCallScopeSimple(self):
    self.assertExecution(
        (
            '$macro.new[test(one,two)][$one $two]',
            '$test[1][2]',
        ),
        '1 2')

  def testCallScopeNestedCalls(self):
    self.assertExecution(
        (
            '$macro.new[test(one,two)][$eval.text[$one] $identity[$two]]',
            '$test[1][2]',
        ),
        '1 2')

  def testArgumentSameNameInOtherMacro(self):
    self.assertExecution(
        (
            '$macro.new[inner(arg)][@$arg@]',
            '$macro.new[outer(arg)][%$arg% $inner[!$arg!]]',
            '$outer[test]',
        ),
        '%test% @!test!@')

  def testArgumentSameNameAsMacro(self):
    self.assertExecution(
        (
            '$macro.new[macro(macro)][$macro $macro]',
            '$macro[test]',
        ),
        'test test')

  def testArgumentSameNameInNestedDefinitions(self):
    self.assertExecution(
        ''.join((
            '$macro.new[id(arg)][$arg]',
            '$macro.new[outer(arg)][',
                '$macro.new[inner(arg)][$id[I$arg]` ]',
                'Oarg$arg` ',
                '$inner[Onested]',
            ']',
            '$outer[1]',
            '$inner[2]',
        )),
        'Oarg1 IOnested I2')

  def testDifferentNamesInNestedDefinitions(self):
    self.assertExecution(
        ''.join((
            '$macro.new[id(x)][$x]',
            '$macro.new[outer(y)][',
                '$macro.new[inner(z)][$id[I$z]` ]',
                'Oy$y` ',
                '$inner[Onested]',
            ']',
            '$outer[1]',
            '$inner[2]',
        )),
        'Oy1 IOnested I2')

  def testPartialMacros(self):
    self.assertExecution(
        ''.join((
            '$macro.new[outer(x)][',
                '$macro.new[inner(y)][x=$x y=$y]',
            ']',
            '$outer[1]',
            '$inner[2]',
        )),
        'x=1 y=2')


class MacroCallTest(ExecutionTestCase):

  @staticmethod
  @macro(public_name='wrap', args_signature='*contents', text_compatible=True)
  def WrapMacro(executor, call_node, contents):
    executor.AppendText('A')
    executor.ExecuteNodes(contents)
    executor.AppendText('B')

  @staticmethod
  @macro(public_name='AoneOrTwoB', args_signature='a,b?', text_compatible=True)
  def TwoWrappedMacro(executor, call_node, a, b):
    executor.AppendText(a)
    executor.AppendText('-')
    executor.AppendText(b)

  def testHardcodedName(self):
    self.assertExecution('$macro.call[wrap][arg]', 'AargB')

  def testComputedName(self):
    self.assertExecution(
        (
            '$macro.new[AtestB][1]',
            '$macro.call[$wrap[test]]',
        ),
        '1')

  def testOneArg(self):
    self.assertExecution('$macro.call[$wrap[oneOrTwo]][x]', 'x-')

  def testTwoArgs(self):
    self.assertExecution('$macro.call[$wrap[oneOrTwo]][x][y]', 'x-y')

  def testTooManyArgs(self):
    self.assertExecution(
        '$macro.call[$wrap[oneOrTwo]][a][b][c]',
        messages=['/root:1: $AoneOrTwoB(a,b?): arguments count mismatch: ' +
                  'expected 1..2, got 3',
                  '  /root:1: $macro.call'])

  def testEmptyName(self):
    self.assertExecution(
        '$macro.call[]',
        messages=['/root:1: $macro.call: expected non-empty macro name'])

  def testMacroNotFound(self):
    self.assertExecution(
        '$macro.call[invalid]',
        messages=['/root:1: macro not found: $invalid',
                  '  /root:1: $macro.call'])

  def testNonTextMacroName(self):
    self.assertExecution(
        '$macro.call[test$macro.new[inside][test]]',
        messages=['/root:1: $macro.new: text-incompatible macro call',
                  '  /root:1: $macro.call'])


class BranchWriteTest(ExecutionTestCase):

  def GetExecutionBranch(self, executor):
    self.CreateBranch(executor, TextBranch, name='other')
    return executor.system_branch

  def testCurrentBranch(self):
    self.assertExecution(
        '$branch.write[system][contents]',
        dict(system='contents', other=''))

  def testDifferentBranch(self):
    self.assertExecution(
        '$branch.write[other][contents]',
        dict(system='', other='contents'))

  def testBranchNotFound(self):
    self.assertExecution(
        '$branch.write[invalid][contents]',
        messages=['/root:1: $branch.write: branch not found: invalid'])


class BranchCreateTest(ExecutionTestCase):

  def testRoot_text(self):
    self.assertExecution(
        (
            '$branch.create.root[text][new][out]\n',
            '$branch.write[new][one\n\ntwo]\n',
        ),
        {'system': '', '/output/out': 'one\n\ntwo'})

  def testRoot_unknownType(self):
    self.assertExecution(
        '$branch.create.root[invalid][new][output]',
        messages=['/root:1: $branch.create.root: unknown branch type: invalid;' +
                  ' expected one of: latex, text, xhtml'])

  def testRoot_duplicateBranchName(self):
    self.assertExecution(
        (
            '$branch.create.root[text][one][a.out]',
            '$branch.create.root[text][two][b.out]',
            '$branch.create.root[text][one][c.out]',
        ),
        messages=['/root:3: $branch.create.root: ' +
                  'a branch of this name already exists: one'])

  def testRoot_invalidOutputFilename(self):
    self.assertExecution(
        '$branch.create.root[text][one][../output]',
        messages=["/root:1: $branch.create.root: invalid output file name: " +
                  "'../output'; must be below the output directory"])

  def testRoot_relativeBelowOutput(self):
    self.assertExecution(
        (
            '$branch.create.root[text][new][../output/below]\n',
            '$branch.write[new][test]\n',
        ),
        {'system': '', '/output/below': 'test'})

  def testRoot_nameRef(self):
    self.assertExecution(
        (
            '$branch.create.root[text][!new][out]',
            '$branch.write[$new][inside]',
            '$new',
        ),
        {'system': 'auto1', '/output/out': 'inside'})

  def testRoot_inheritsCurrentBranch(self):
    self.assertExecution(
        (
            '$macro.new[first][one]',
            '$branch.create.root[text][new][new]',
            '$macro.new[second][two]',
            '$branch.write[new][$first $second]',
        ),
        {'system': '', '/output/new': 'one two'})

  def testRoot_doesNotInheritsOtherBranches(self):
    self.assertExecution(
        (
            '$branch.create.root[text][new1][new1]',
            '$branch.create.root[text][new2][new2]',
            '$branch.write[new1][$macro.new[macro][test]]',
            '$branch.write[new2][',
                '$macro]',
        ),
        messages=['/root:5: macro not found: $macro',
                  '  /root:4: $branch.write'])

  def testSub_multiple(self):
    self.assertExecution(
        (
            '$branch.create.sub[one]',
            'one` ',
            '$branch.append[one]',
            'two` ',
            '$branch.write[one][oneA` ]'
            '$branch.create.sub[two]',
            '$branch.append[two]',
            '$branch.write[one][oneB` ]'
            'three` ',
            '$branch.write[two][twoA` ]'
            '$branch.create.sub[three]',
            '$branch.write[one][oneC` ]'
            '$branch.append[three]',
            'four',
        ),
        'one oneA oneB oneC two twoA three four')

  def testSub_nested(self):
    self.assertExecution(
        (
            'one` ',
            '$branch.create.sub[one]',
            '$branch.append[one]',
            'two` ',
            '$branch.create.sub[two]',
            '$branch.append[two]',
            'three',
            '$branch.write[one]['
                'oneB` '
                '$branch.create.sub[oneA]',
                '$branch.append[oneA]',
                'oneE` ',
            ']',
            '$branch.write[two]['
                'twoB` '
                '$branch.create.sub[twoA]',
                '$branch.append[twoA]',
                'twoE` ',
            ']',
            '$branch.write[oneA][oneI` ]',
            '$branch.write[twoA][twoI` ]',
        ),
        'one oneB oneI oneE two twoB twoI twoE three')

  def testSub_duplicateName(self):
    self.assertExecution(
        (
            '$branch.create.sub[one]',
            '$branch.create.sub[two]',
            '$branch.create.sub[one]',
        ),
        messages=['/root:3: $branch.create.sub: ' +
                  'a branch of this name already exists: one'])

  def testSub_nameRef(self):
    self.assertExecution(
        (
            '$branch.create.sub[!new]',
            'before $branch.append[$new] after',
            '$branch.write[$new][inside]',
        ),
        'before inside after')


class BranchAppendTest(ExecutionTestCase):

  def testParentMismatch_siblings(self):
    self.assertExecution(
        (
            '$branch.create.sub[one]',
            '$branch.create.sub[two]',
            '$branch.write[one][$branch.create.sub[one-sub]]',
            '$branch.write[two][$branch.append[one-sub]]',
        ),
        messages=["/root:4: $branch.append: expected a sub-branch created by" +
                  " branch 'two'; got one created by branch 'one'",
                  "  /root:4: $branch.write"])

  def testParentMismatch_childIntoParent(self):
    self.assertExecution(
        (
            '$branch.create.sub[child]',
            '$branch.write[child][$branch.create.sub[child-sub]]',
            '$branch.append[child-sub]',
        ),
        messages=["/root:3: $branch.append: expected a sub-branch created by" +
                  " branch 'system'; got one created by branch 'child'"])

  def testParentMismatch_parentIntoChild(self):
    self.assertExecution(
        (
            '$branch.create.sub[child]',
            '$branch.create.sub[sibling]',
            '$branch.write[child][$branch.append[sibling]]',
        ),
        messages=["/root:3: $branch.append: expected a sub-branch created by" +
                  " branch 'child'; got one created by branch 'system'",
                  "  /root:3: $branch.write"])

  def testAlreadyAttached(self):
    self.assertExecution(
        (
            '$branch.create.sub[sub]',
            '$branch.append[sub]',
            '$branch.append[sub]',
        ),
        messages=[
            "/root:3: $branch.append: the sub-branch 'sub' is already attached",
        ])


class ArabicToRomanTest(TestCase):

  def testZeroUnsupported(self):
    self.assertRaises(InternalError, lambda: ArabicToRoman(0))

  def testNegativeUnsupported(self):
    self.assertRaises(InternalError, lambda: ArabicToRoman(-1))

  def testTooLargeUnsupported(self):
    self.assertRaises(InternalError, lambda: ArabicToRoman(5000))

  def testSmallValues(self):
    values = ((1, 'I'), (2, 'II'), (3, 'III'), (4, 'IV'), (5, 'V'), (6, 'VI'),
              (7, 'VII'), (8, 'VIII'), (9, 'IX'), (10, 'X'))
    for arabic, roman in values:
      self.assertEqualExt(roman, ArabicToRoman(arabic),
                          'ArabicToRoman mismatch for ' + str(arabic))

  def testLargeValues(self):
    values = ((20, 'XX'), (50, 'L'), (42, 'XLII'), (99, 'XCIX'),
              (399, 'CCCXCIX'), (499, 'CDXCIX'), (1000, 'M'), (1999, 'MCMXCIX'),
              (3789, 'MMMDCCLXXXIX'), (3999, 'MMMCMXCIX'))
    for arabic, roman in values:
      self.assertEqualExt(roman, ArabicToRoman(arabic),
                          'ArabicToRoman mismatch for ' + str(arabic))

  def testAllValues(self):
    for arabic in xrange(1, 4000):
      ArabicToRoman(arabic)


class RomanTest(ExecutionTestCase):

  def testValidArabicNumber(self):
    self.assertExecution('$roman[42]', 'XLII')

  def testInvalidArabicNumber(self):
    self.assertExecution(
        '$roman[nan]',
        messages=['/root:1: $roman: invalid Arabic number: nan'])

  def testUnsupportedArabicNumber(self):
    self.assertExecution(
        '$roman[0]',
        messages=[
            '/root:1: $roman: unsupported number for conversion to Roman: 0',
        ])


class IfEqTest(ExecutionTestCase):

  def testEq(self):
    self.assertExecution('$identity[$if.eq[test][test][yes][no]]', 'yes')

  def testNotEq_elseBlock(self):
    self.assertExecution('$identity[$if.eq[one][two][yes][no]]', 'no')

  def testNotEq_noElseBlock(self):
    self.assertExecution('$identity[$if.eq[one][two][yes]]', '')


class CounterTest(ExecutionTestCase):

  def testCreate_overwritesExisting(self):
    self.assertExecution(
        (
            '$counter.create[test]',
            '$test.incr',
            ' before: $test',
            '$counter.create[test]',
            ' - after: $test',
        ),
        'before: 1 - after: 0')

  def testCreate_initiallyZero(self):
    self.assertExecution(
        (
            '$counter.create[test]',
            '$test',
        ),
        '0')

  def testIfPositive_zero(self):
    self.assertExecution(
        (
            '$counter.create[test]',
            '$test.set[0]',
            '$test.if.positive[positive]',
        ),
        '')

  def testIfPositive_negative(self):
    self.assertExecution(
        (
            '$counter.create[test]',
            '$test.set[-1]',
            '$test.if.positive[positive]',
        ),
        '')

  def testIfPositive_positive(self):
    self.assertExecution(
        (
            '$counter.create[test]',
            '$test.set[1]',
            '$test.if.positive[positive]',
        ),
        'positive')

  def testSet_invalid(self):
    self.assertExecution(
        (
            '$counter.create[test]',
            '$test.set[invalid]',
        ),
        messages=['/root:2: $test.set: invalid integer value: invalid'])

  def testValue(self):
    self.assertExecution(
        (
            '$counter.create[test]',
            '$test',
            '$test.incr $test',
            '$test.incr $test',
            '$test.set[12345] $test',
            '$test.set[-42] $test',
        ),
        '0 1 2 12345 -42')


if __name__ == '__main__':
  unittest.main()
