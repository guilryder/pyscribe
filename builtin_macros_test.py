#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

from builtin_macros import *
from execution import *
from testutils import *


class SpecialCharsTest(ExecutionTestCase):

  def testAll(self):
    self.assertExecution(
        special_chars,
        ' '.join((
            "% & _ $ $ # #",
            "a\xa0b",
            "n\xado",
            "–c—",
            "d…",
            "«e»",
            "« f »",
            "`g'h' 'g`h`",
            "“i”j” ”k“l“",
            "“`m”'",
            "n ! o: p ; q?",
            "r!:;?",
        )))

  def testSoftHyphenAlias(self):
    self.assertExecution(
        (
            '$macro.new[text.softhyphen][OK]',
            'a$-b',
        ),
        'aOKb')

  def testWhitespaceMacros(self):
    self.assertExecution('A$newline^B', 'A\nB')


class EmptyTest(ExecutionTestCase):

  def testNodes(self):
    self.assertExecution('before$empty^after', 'beforeafter')

  def testText(self):
    self.assertExecution('$macro.new[name$empty][inside]$name', 'inside')


class LogTest(ExecutionTestCase):

  def testBasic(self):
    self.assertExecution(
        (
            'before',
            '$log[message!]',
            'after',
        ),
        'beforeafter',
        expected_infos=['message!'])

  def testComplex(self):
    self.assertExecution(
        (
            '$macro.new[message][macro definition]',
            '$log[first]',
            '$log[second $message]',
            '$log[third]',
        ),
        '',
        expected_infos=['first', 'second macro definition', 'third'])

  def testNested(self):
    self.assertExecution(
        '$log[before $log[inside] after]',
        '',
        expected_infos=['inside', 'before  after'])


class IncludeTest(ExecutionTestCase):

  def testNested(self):
    self.assertExecution(
        {
            '/root': 'roota $include[one.psc]rootb',
            '/one.psc': '1a $include[two.psc]1b^ ',
            '/two.psc': '2a $include[three.psc]2b^ ',
            '/three.psc': '3^ ',
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
        '$include[404.psc]',
        messages=['/root:1: $include: unable to include "404.psc": ' +
                  'file not found: /404.psc'])

  def testAutoExtension(self):
    self.assertExecution(
        {
            '/root': '$include[other]',
            '/other.psc': 'OK',
        },
        'OK')

  def testAutoExtension_hiddenFile(self):
    self.assertExecution(
        {
            '/root': '$include[.other]',
            '/.other.psc': 'OK',
        },
        'OK')

  def testAutoExtension_ignoredIfFileExists(self):
    self.assertExecution(
        {
            '/root': '$include[other]',
            '/other': 'OK',
            '/other.psc': 'SHOULD NOT BE INCLUDED',
        },
        'OK')

  def testAutoExtension_notIfExtensionPresent(self):
    self.assertExecution(
        {
            '/root': '$include[other.ext]',
            '/other.ext.psc': 'SHOULD NOT BE INCLUDED',
        },
        messages=['/root:1: $include: unable to include "other.ext": ' +
                  'file not found: /other.ext'])

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

  def testRecursiveCallsBasic(self):
    self.assertExecution(
        (
            '$macro.new[test(arg)][',
              '$arg!',
              '$if.def[recursed][][',
                '$macro.new[recursed][]',
                'REC($test[recursing])',
              ']',
            ']',
            '$test[top]',
        ),
        'top!REC(recursing!)')

  def testRecursiveCallsRedefined(self):
    self.assertExecution(
        (
            '$macro.new[test(arg)][',
              '$arg!',
              '$if.def[recursed][',
                '$macro.new[test(arg)][REDEF:$arg]',
              '][',
                '$macro.new[recursed][]',
                'REC($test[recursing1])',
                'REC($test[recursing2])',
              ']',
            ']',
            '$test[top]',
        ),
        'top!REC(recursing1!)REC(REDEF:recursing2)')

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

  def testInvalidSignature(self):
    self.assertExecution(
        '$macro.new[macro(][blah]',
        messages=['/root:1: $macro.new: invalid signature: macro('])
    self.assertExecution(
        '$macro.new[macro()(][blah]',
        messages=['/root:1: $macro.new: invalid signature: macro()('])

  def testInvalidName(self):
    self.assertExecution(
        '$macro.new[!][body]',
        messages=['/root:1: $macro.new: invalid signature: !'])

  def testEmptyNameNoArgs(self):
    self.assertExecution(
        '$macro.new[][body]',
        messages=['/root:1: $macro.new: invalid signature:'])

  def testEmptyNameOneArg(self):
    self.assertExecution(
        '$macro.new[(arg)][body]',
        messages=['/root:1: $macro.new: invalid signature: (arg)'])

  def testEmptyArgName(self):
    self.assertExecution(
        '$macro.new[test(one,,three)][body]',
        messages=['/root:1: $macro.new: invalid signature: test(one,,three)'])

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

  def testMacroSameNameInCurrentContext(self):
    self.assertExecution(
        (
            '$macro.new[test][initial]',
            '$macro.new[test][new]',
            '$test',
        ),
        'new')

  def testMacroSameNameInParentContext(self):
    self.assertExecution(
        (
            '$macro.new[test][initial!]',
            '$branch.create.sub[sub]',
            '$branch.write[sub][',
              '$macro.new[test][new!]',
              '$test',
            ']',
            '$test',
            '$branch.append[sub]',
            '$test',
        ),
        'initial!new!initial!')

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
        (
            '$macro.new[id(arg)][$arg]',
            '$macro.new[outer(arg)][',
              '$macro.new[inner(arg)][$id[I$arg]^ ]',
              'Oarg$arg^ ',
              '$inner[Onested]',
            ']',
            '$outer[1]',
            '$inner[2]',
        ),
        'Oarg1 IOnested I2 ')

  def testDifferentNamesInNestedDefinitions(self):
    self.assertExecution(
        (
            '$macro.new[id(x)][$x]',
            '$macro.new[outer(y)][',
              '$macro.new[inner(z)][$id[I$z]^ ]',
              'Oy$y^ ',
              '$inner[Onested]',
            ']',
            '$outer[1]',
            '$inner[2]',
        ),
        'Oy1 IOnested I2 ')

  def testPartialMacros(self):
    self.assertExecution(
        (
            '$macro.new[outer(x)][',
              '$macro.new[inner(y)][x=$x y=$y]',
            ']',
            '$outer[1]',
            '$inner[2]',
        ),
        'x=1 y=2')


class MacroOverrideTest(ExecutionTestCase):

  def testNoArgs(self):
    self.assertExecution(
        (
            '$macro.new[test][initial]',
            '$macro.override[test][original][new1 $original new2]',
            '$test',
        ),
        'new1 initial new2')

  def testTwoArgsSameArgNamesAsOriginal(self):
    self.assertExecution(
        (
            '$macro.new[plusRule(a,b)][$a + $b = $b + $a]',
            '$macro.override[plusRule(a,b)][original][$a+$b $original[$a][$b]]',
            '$plusRule[1][2]',
        ),
        '1+2 1 + 2 = 2 + 1')

  def testTwoArgsDifferentArgNamesThanOriginal(self):
    self.assertExecution(
        (
            '$macro.new[a][topA]',
            '$macro.new[b][topB]',
            '$macro.new[plusRule(a,b)][$a + $b = $b + $a]',
            '$macro.override[plusRule(c,d)][original][',
            'a=$a b=$b c=$c d=$d $original[$c][$d]]',
            '$plusRule[1][2]',
        ),
        'a=topA b=topB c=1 d=2 1 + 2 = 2 + 1')

  def testDifferentSignatureThanOriginal(self):
    self.assertExecution(
        (
            '$macro.new[test(a)][initial:$a]',
            '$test[1]',
            '$macro.override[test(b,c)][original][_$original[$b+$c]]',
            '$test[2][3]',
        ),
        'initial:1_initial:2+3')

  def testRecursiveCallsBasic(self):
    self.assertExecution(
        (
            '$macro.new[test(arg)][',
              'initial:$arg!',
              '$if.def[recursed][][',
                '$macro.new[recursed][]',
                'REC($test[recursing])',
              ']',
            ']',
            '$macro.override[test(arg)][original][O($original[$arg])]',
            '$test[top]',
        ),
        'O(initial:top!REC(O(initial:recursing!)))')

  def testMultipleOverridesOrdered(self):
    self.assertExecution(
        (
            '$macro.new[listener][initial]',
            '$macro.override[listener][original][a $original A]',
            '$macro.override[listener][original][b $original B]',
            '$listener'
        ),
        'b a initial A B')

  def testNestedOverrides(self):
    self.assertExecution(
        (
            '$macro.new[test(arg)][',
              'original:$arg ',
              '$macro.override[test(arg)][original1][',
                'override1:$arg ',
                '$original1[$arg]',
                '$macro.override[test(arg)][original2][',
                  'override2:$arg ',
                  '$original2[$arg]',
                 ']',
               ']',
            ']',
            '!$test[1]',
            '!$test[2]',
            '!$test[3]',
        ), (
            '!original:1 '
            '!override1:2 original:2 '
            '!override2:3 override1:3 override1:3 original:3 '
        ))

  def testRecursiveCallsRedefined(self):
    self.assertExecution(
        (
            '$macro.new[test(arg)][',
              'initial:$arg!',
              '$if.def[recursed][',
                '$macro.override[test(arg)][original][O($original[$arg])]',
              '][',
                '$macro.new[recursed][]',
                'REC($test[recursing1])',
                'REC($test[recursing2])',
              ']',
            ']',
            '$test[top]',
        ),
        'initial:top!REC(initial:recursing1!)REC(O(initial:recursing2!))')

  def testNestedCallsSameArgumentNames(self):
    self.assertExecution(
        (
            '$macro.new[plusRule(a,b)][$a + $b = $b + $a]',
            '$macro.new[plus(a,b)][$a + $b]',
            '$macro.new[minus(a,b)][$a - ($b)]',
            '$plusRule[$minus[$minus[6][1]][2]][$minus[3][$plus[4][5]]]',
        ),
        '6 - (1) - (2) + 3 - (4 + 5) = 3 - (4 + 5) + 6 - (1) - (2)')

  def testInvalidSignature(self):
    self.assertExecution(
        '$macro.override[macro(][original][blah]',
        messages=['/root:1: $macro.override: invalid signature: macro('])
    self.assertExecution(
        '$macro.override[macro()(][original][blah]',
        messages=['/root:1: $macro.override: invalid signature: macro()('])

  def testInvalidName(self):
    self.assertExecution(
        '$macro.override[!][original][body]',
        messages=['/root:1: $macro.override: invalid signature: !'])

  def testEmptyNameNoArgs(self):
    self.assertExecution(
        '$macro.override[][original][body]',
        messages=['/root:1: $macro.override: invalid signature:'])

  def testEmptyNameOneArg(self):
    self.assertExecution(
        '$macro.override[(arg)][original][body]',
        messages=['/root:1: $macro.override: invalid signature: (arg)'])

  def testEmptyArgName(self):
    self.assertExecution(
        '$macro.override[test(a,,c)][original][body]',
        messages=['/root:1: $macro.override: invalid signature: test(a,,c)'])

  def testDuplicateSignatureArguments(self):
    self.assertExecution(
        '$macro.override[test(one,two,three,two)][original][body]',
        messages=['/root:1: $macro.override: ' +
                  'duplicate argument in signature: two'])

  def testEmptyOriginalName(self):
    self.assertExecution(
        '$macro.override[test][][body]',
        messages=['/root:1: $macro.override: invalid original macro name:'])

  def testInvalidOriginalName(self):
    self.assertExecution(
        '$macro.override[test][!][body]',
        messages=['/root:1: $macro.override: invalid original macro name: !'])

  def testOriginalNameSameAsArg(self):
    self.assertExecution(
        '$macro.override[test(a,b)][b][body]',
        messages=['/root:1: $macro.override: original macro name conflicts ' +
                  'with signature: b vs. test(a,b)'])

  def testBuiltinMacro(self):
    self.assertExecution(
        '$macro.override[empty][original][]',
        messages=['/root:1: $macro.override: ' +
                  'cannot override a built-in macro: empty'])

  def testTextCompatible(self):
    self.assertExecution(
        (
            '$macro.new[double(arg)][$arg$arg]',
            '$macro.new[testtest(arg)][initial:$arg]',
            '$macro.override[$double[test](arg)][$double[x]][!$arg! $xx[x]]',
            '$testtest[input]'
        ),
        '!input! initial:x')

  def testMacroSameNameInCurrentContext(self):
    self.assertExecution(
        (
            '$macro.new[test][initial]',
            '$macro.new[test][new]',
            '$test',
        ),
        'new')

  def testMacroSameNameInParentContext(self):
    self.assertExecution(
        (
            '$macro.new[test][initial!]',
            '$branch.create.sub[sub]',
            '$branch.write[sub][',
              '$macro.override[test][original][new($original)!]',
              '$test',
            ']',
            '$test',
            '$branch.append[sub]',
            '$test',
        ),
        'initial!new(initial!)!initial!')


class MacroWrapTest(ExecutionTestCase):

  def testBasic(self):
    self.assertExecution(
        (
            '$macro.new[listener][initial]',
            '$macro.wrap[listener][head!][!tail]',
            '$listener'
        ),
        'head!initial!tail')

  def testMultipleWrapsOrdered(self):
    self.assertExecution(
        (
            '$macro.new[listener][!initial!]',
            '$macro.wrap[listener][a][A]',
            '$macro.wrap[listener][b][B]',
            '$macro.wrap[listener][c][C]',
            '$listener'
        ),
        'cba!initial!ABC')

  def testEmptyHeadOrTail(self):
    self.assertExecution(
        (
            '$macro.new[listener][!initial!]',
            '$macro.wrap[listener][][A]',
            '$macro.wrap[listener][][]',
            '$macro.wrap[listener][c][]',
            '$listener'
        ),
        'c!initial!A')

  def testMultipleWrappedMacrosIndependently(self):
    self.assertExecution(
        (
            '$macro.new[listenerX][X]',
            '$macro.new[listenerY][Y]',
            '$macro.wrap[listenerX][a][A]',
            '$macro.wrap[listenerY][b][B]',
            '$macro.wrap[listenerX][c][C]',
            '$macro.wrap[listenerY][d][D]',
            '$listenerX $listenerY',
        ),
        'caXAC dbYBD')

  def testMacroNotExisting(self):
    self.assertExecution(
        (
            '$macro.wrap[nonExistingMacro][head][tail]',
        ),
        messages=['/root:1: $macro.wrap: cannot wrap ' +
                  'a non-existing macro: nonExistingMacro'])

  def testBuiltinMacro(self):
    self.assertExecution(
        '$macro.wrap[empty][head][tail]',
        messages=['/root:1: $macro.wrap: cannot wrap a built-in macro: empty'])

  def testMacroWithArgsAllowed(self):
    self.assertExecution(
        (
            '$macro.new[withArgs(a,b)][$a and $b]',
            '$macro.wrap[withArgs][head!][!tail]',
            '$withArgs[1][2]',
        ),
        'head!1 and 2!tail')

  def testMacroWithArgsDoesNotSetArgVariables(self):
    self.assertExecution(
        (
            '$macro.new[arg][top]',
            '$macro.new[withArg(arg)][$arg]',
            '$macro.wrap[withArg][head:$arg!][!tail:$arg]',
            '$withArg[call]',
        ),
        'head:top!call!tail:top')

  def testTextCompatible(self):
    self.assertExecution(
        (
            '$macro.new[listener][initial]',
            '$macro.wrap[listener][head!][!tail]',
            '$eval.text[$listener]',
        ),
        'head!initial!tail')

  def testBranchScope(self):
    self.assertExecution(
        (
            '$macro.new[listener][initial]'
            '$macro.new[top][$macro.wrap[listener][head!][!tail]]',
            '$top'
            '$listener',
        ),
        'head!initial!tail')

  def testParentMacroArgumentsInBody(self):
    self.assertExecution(
        (
            '$macro.new[listener][initial]'
            '$macro.new[top(arg)][$macro.wrap[listener][$arg!][!$arg]]',
            '$top[top-arg]',
            '$listener',
        ),
        'top-arg!initial!top-arg')

  def testReferenceSameNameInMultipleAppends(self):
    self.assertExecution(
        (
            '$macro.new[listener][initial]'
            '$macro.new[A(ref)][$macro.wrap[listener][a=$ref!][!A=$ref]]',
            '$macro.new[B(ref)][$macro.wrap[listener][b=$ref!][!B=$ref]]',
            '$macro.new[ref][top]',
            '$A[a]',
            '$macro.wrap[listener][top1=$ref!][!Top1=$ref]',
            '$macro.new[ref][topMODIF]',
            '$B[b]',
            '$macro.wrap[listener][top2=$ref!][!Top2=$ref]',
            '$listener',
        ), (
            'top2=topMODIF!'
            'b=b!'
            'top1=topMODIF!'
            'a=a!'
            'initial'
            '!A=a'
            '!Top1=topMODIF'
            '!B=b!Top2=topMODIF'
        ))

  def testMacroInParentContext(self):
    self.assertExecution(
        (
            '$macro.new[test][initial]',
            '$branch.create.sub[sub]',
            '$branch.write[sub][',
              '$macro.wrap[test][head!][!tail]',
              '($test)',
            ']',
            '($test)',
            '$branch.append[sub]',
            '($test)',
        ), (
            '(head!initial!tail)'
            '(head!initial!tail)'
            '(head!initial!tail)'
        ))


class MacroCallTest(ExecutionTestCase):

  @staticmethod
  @macro(public_name='wrap', args_signature='*contents', text_compatible=True)
  def WrapMacro(executor, unused_call_node, contents):
    executor.AppendText('A')
    executor.ExecuteNodes(contents)
    executor.AppendText('B')

  @staticmethod
  @macro(public_name='AoneOrTwoB', args_signature='a,b?', text_compatible=True)
  def TwoWrappedMacro(executor, unused_call_node, a, b):
    executor.AppendText(a)
    executor.AppendText('-')
    if b:
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


class MacroContextNewTest(ExecutionTestCase):

  def GetExecutionBranch(self, executor):
    self.CreateBranch(executor, TextBranch, name='other')
    return executor.system_branch

  def testText(self):
    self.assertExecution(
        'BEFORE $macro.context.new[INSIDE] AFTER',
        'BEFORE INSIDE AFTER')

  def testParentMacroUsed(self):
    self.assertExecution(
        (
            '$macro.new[parent][original]',
            'BEFORE $macro.context.new[INSIDE $parent]',
            ' AFTER $parent',
        ),
        'BEFORE INSIDE original AFTER original')

  def testParentMacroChangedAndUsed(self):
    self.assertExecution(
        (
            '$macro.new[parent][original]',
            'BEFORE $macro.context.new[',
                '$macro.new[parent][modified]',
                'INSIDE $parent',
            ']',
            ' AFTER $parent',
        ),
        'BEFORE INSIDE modified AFTER original')

  def testChildMacroDisappears(self):
    self.assertExecution(
        (
            'BEFORE $macro.context.new[',
                '$macro.new[child][in-child]',
                'INSIDE',
            ']',
            ' AFTER $child',
        ),
        messages=['/root:5: macro not found: $child'])

  def testImpactsOnlyCurrentBranch(self):
    self.assertExecution(
        (
            '$macro.new[parent][original]',
            '$branch.write[other][BEFORE $parent]',
            'BEFORE $macro.context.new[',
                '$macro.new[parent][modified]',
                '$branch.write[other][^ INSIDE $parent]',
                'INSIDE $parent',
            ']',
            '$branch.write[other][^ AFTER $parent]',
            ' AFTER $parent',
        ),
        dict(system='BEFORE INSIDE modified AFTER original',
             other='BEFORE original INSIDE original AFTER original'))


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
        {'system': '\n', '/output/out': 'one\n\ntwo'})

  def testRoot_unknownType(self):
    self.assertExecution(
        '$branch.create.root[invalid][new][output]',
        messages=['/root:1: $branch.create.root: ' +
                  'unknown branch type: invalid;' +
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
        {'system': '\n', '/output/below': 'test'})

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
            'one^ ',
            '$branch.append[one]',
            'two^ ',
            '$branch.write[one][oneA^ ]'
            '$branch.create.sub[two]',
            '$branch.append[two]',
            '$branch.write[one][oneB^ ]'
            'three^ ',
            '$branch.write[two][twoA^ ]'
            '$branch.create.sub[three]',
            '$branch.write[one][oneC^ ]'
            '$branch.append[three]',
            'four',
        ),
        'one oneA oneB oneC two twoA three four')

  def testSub_nested(self):
    self.assertExecution(
        (
            'one^ ',
            '$branch.create.sub[one]',
            '$branch.append[one]',
            'two^ ',
            '$branch.create.sub[two]',
            '$branch.append[two]',
            'three',
            '$branch.write[one]['
              'oneB^ '
              '$branch.create.sub[oneA]',
              '$branch.append[oneA]',
              'oneE^ ',
            ']',
            '$branch.write[two]['
              'twoB^ '
              '$branch.create.sub[twoA]',
              '$branch.append[twoA]',
              'twoE^ ',
            ']',
            '$branch.write[oneA][oneI^ ]',
            '$branch.write[twoA][twoI^ ]',
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


class CaseTest(ExecutionTestCase):

  def testLower(self):
    self.assertExecution("$case.lower[Ôô! ça Ç'était]", "ôô! ça ç'était")

  def testUpper(self):
    self.assertExecution("$case.upper[Ôô! ça Ç'était]", "ÔÔ! ÇA Ç'ÉTAIT")


class AlphaLatinTest(ExecutionTestCase):

  def testValidArabicNumber(self):
    self.assertExecution('$alpha.latin[1] $alpha.latin[5] $alpha.latin[26]',
                         'A E Z')

  def testInvalidArabicNumber(self):
    self.assertExecution(
        '$alpha.latin[nan]',
        messages=['/root:1: $alpha.latin: invalid Arabic number: nan'])

  def test0(self):
    self.assertExecution(
        '$alpha.latin[0]',
        messages=[
            '/root:1: $alpha.latin: unsupported number for conversion to '
            'latin letter: 0',
        ])

  def test27(self):
    self.assertExecution(
        '$alpha.latin[27]',
        messages=[
            '/root:1: $alpha.latin: unsupported number for conversion to '
            'latin letter: 27',
        ])


class ArabicToRomanTest(TestCase):

  def testZeroUnsupported(self):
    with self.assertRaises(InternalError):
      ArabicToRoman(0)

  def testNegativeUnsupported(self):
    with self.assertRaises(InternalError):
      ArabicToRoman(-1)

  def testTooLargeUnsupported(self):
    with self.assertRaises(InternalError):
      ArabicToRoman(5000)

  def testSmallValues(self):
    values = ((1, 'I'), (2, 'II'), (3, 'III'), (4, 'IV'), (5, 'V'), (6, 'VI'),
              (7, 'VII'), (8, 'VIII'), (9, 'IX'), (10, 'X'))
    for arabic, roman in values:
      self.assertEqualExt(ArabicToRoman(arabic), roman,
                          'ArabicToRoman mismatch for ' + str(arabic))

  def testLargeValues(self):
    values = ((20, 'XX'), (50, 'L'), (42, 'XLII'), (99, 'XCIX'),
              (399, 'CCCXCIX'), (499, 'CDXCIX'), (1000, 'M'), (1999, 'MCMXCIX'),
              (3789, 'MMMDCCLXXXIX'), (3999, 'MMMCMXCIX'))
    for arabic, roman in values:
      self.assertEqualExt(ArabicToRoman(arabic), roman,
                          'ArabicToRoman mismatch for ' + str(arabic))

  def testAllValues(self):  # pylint: disable=no-self-use
    for arabic in range(1, 4000):
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


class IfDefTest(ExecutionTestCase):

  def testDef_builtin(self):
    self.assertExecution('$identity[$if.def[identity][yes][no]]', 'yes')

  def testDef_custom(self):
    self.assertExecution(
        (
            '$macro.new[dummy][]',
            '$identity[$if.def[dummy][yes][no]]',
        ),
        'yes')

  def testDef_noElseBlock(self):
    self.assertExecution('$identity[$if.def[identity][yes]]', 'yes')

  def testUndef(self):
    self.assertExecution('$identity[$if.def[foobar][yes][no]]', 'no')

  def testUndef_noElseBlock(self):
    self.assertExecution('$identity[$if.def[foobar][yes]]', '')


class IfEqTest(ExecutionTestCase):

  def testEq(self):
    self.assertExecution('$identity[$if.eq[test][test][yes][no]]', 'yes')

  def testEq_noElseBlock(self):
    self.assertExecution('$identity[$if.eq[test][test][yes]]', 'yes')

  def testNotEq(self):
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
        ' before: 1 - after: 0')

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
