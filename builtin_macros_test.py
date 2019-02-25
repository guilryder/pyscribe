#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

from builtin_macros import *
from execution import *
from testutils import *


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
    with self.assertRaises(NodeError):
      ArabicToRoman(0)

  def testNegativeUnsupported(self):
    with self.assertRaises(NodeError):
      ArabicToRoman(-1)

  def testTooLargeUnsupported(self):
    with self.assertRaises(NodeError):
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


class RepeatTest(ExecutionTestCase):

  def testCountInvalid(self):
    self.assertExecution(
        '$repeat[invalid][foo]',
        messages=['/root:1: $repeat: invalid integer value: invalid'])

  def testCountNegative(self):
    self.assertExecution('$repeat[-3][foo]', '')

  def testCountZero(self):
    self.assertExecution('$repeat[0][foo]', '')

  def testCountOne(self):
    self.assertExecution('$repeat[1][foo]', 'foo')

  def testCountMany(self):
    self.assertExecution('$repeat[42][foo]', 'foo' * 42)

  def testTextCompatible(self):
    self.assertExecution('$eval.text[$repeat[2][foo]]', 'foofoo')

  def testSideEffects(self):
    self.assertExecution(
        (
            '$counter.create[index]',
            '$repeat[3][$index.incr $index]',
        ),
        ' 1 2 3')


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
