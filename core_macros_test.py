#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

from branches import TextBranch
from builtin_macros import *
from execution import *
from testutils import *


class SpecialCharsTest(ExecutionTestCase):

  def testRawSpecialChars(self):
    self.assertExecution(SPECIAL_CHARS, SPECIAL_CHARS_AFTER_TEXT_MACROS)

  def testTextMacros(self):
    self.assertExecution(OTHER_TEXT_MACROS, OTHER_TEXT_MACROS_AS_TEXT)

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

  def testTextCompatible(self):
    self.assertExecution('$eval.text[$empty]', '')


class EvalTextTest(ExecutionTestCase):

  def testText(self):
    self.assertExecution('$eval.text[inside $text.hash]', 'inside #')

  def testNotText(self):
    self.assertExecution(
        '$eval.text[$identity[foo]]',
        messages=['/root:1: $identity: text-incompatible macro call',
                  '  /root:1: $eval.text'])

  def testTextCompatibleRecursively(self):
    self.assertExecution('$eval.text[$eval.text[inside]]', 'inside')


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
                  "[Errno 2] File not found: '/404.psc'"])

  def testFileNotReadable(self):
    self.assertExecution(
        {
            '/root': '$include[not_readable.psc]',
            '/not_readable.psc': None,
        },
        messages=['/not_readable.psc:1: unable to read the input file:'
                  ' /not_readable.psc',
                  'Fake read error'])

  def testAutoExtension(self):
    self.assertExecution(
        {
            '/root': '$include[other]',
            '/other.psc': 'OK',
        },
        'OK')

  def testMaxNestedIncludes(self):
    self.assertExecution(
        'test$include[/root]',
        messages=['/root:1: $include: unable to include "/root": ' +
                  'too many nested includes'] +
                 ['  /root:1: $include'] * 24)


class IncludeTextTest(ExecutionTestCase):

  def testBasic(self):
    self.assertExecution(
        {
            '/root': 'roota $include.text[hello.txt] rootb',
            '/hello.txt': 'Hello, World!',
        },
        'roota Hello, World! rootb')

  def testDoesNotInterpretSpecialCharacters(self):
    included = '\n'.join((
        '$$invalid',
        '$foo',
        '^',
        TEST_UNICODE,
        SPECIAL_CHARS,
    ))
    self.assertExecution(
        {
            '/root': 'roota $include.text[hello.txt] rootb',
            '/hello.txt': included,
        },
        f'roota {included} rootb')

  def testFileNotFound(self):
    self.assertExecution(
        '$include.text[404.txt]',
        messages=['/root:1: $include.text: unable to include "404.txt": ' +
                  "[Errno 2] File not found: '/404.txt'"])

  def testNoAutoExtension(self):
    self.assertExecution(
        {
            '/root': '$include.text[hello]',
            '/hello.txt': 'Hello, World!',
        },
        messages=['/root:1: $include.text: unable to include "hello": ' +
                  "[Errno 2] File not found: '/hello'"])

  def testTextCompatible(self):
    self.assertExecution(
        {
            '/root': '$eval.text[$include.text[hello.txt]]',
            '/hello.txt': 'Hello, World!',
        },
        'Hello, World!')


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
        {
            '/system': 'BEFORE INSIDE modified AFTER original',
            '/output/other': 'BEFORE original INSIDE original AFTER original',
        })


if __name__ == '__main__':
  unittest.main()
