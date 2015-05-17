#!/usr/bin/env python
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

import imp

from macros import *
from parsing import *
from testutils import *


class MacroTest(TestCase):

  def setUp(self):
    super(MacroTest, self).setUp()
    self.logger = FakeLogger()
    self.executor = Executor(output_dir='output', logger=self.logger,
                             fs=FakeFileSystem())
    self.executor.EvalText = lambda args: 'T' + args

  def __MacroCall(self, macro_callback, args):
    call_node = CallNode(test_location, 'name', args)
    self.called = False
    macro_callback(self.executor, call_node)

  def __CheckMacroCallback(self, *actual_args):
    self.called = True
    self.assertEqual(self.expected_args, list(actual_args))

  def __CheckMacroCall(self, macro_callback, args, expected_args=None):
    self.expected_args = expected_args
    self.__MacroCall(macro_callback, args)
    self.assertTrue(self.called)

  def __CheckMacroCallFailure(self, macro_callback, args, expected_message):
    expected_message = u'{location}: {message}'.format(
        location=test_location, message=expected_message)
    try:
      self.__MacroCall(macro_callback, args)
      self.fail('expected error: ' + expected_message)  # pragma: no cover
    except FatalError, e:
      self.assertFalse(self.called, 'expected macro callback not invoked')
      self.assertEqual(expected_message, self.logger.GetOutput())
      self.logger.Clear()

  def testDefault(self):
    @macro()
    def MacroCallback():
      pass  # pragma: no cover
    self.assertEqual(None, MacroCallback.public_name)
    self.assertEqual('', MacroCallback.args_signature)
    self.assertEqual(False, MacroCallback.text_compatible)
    self.assertEqual(True, MacroCallback.builtin)

  def testCustom(self):
    @macro(public_name='name', args_signature=',,', auto_args_parser=False,
           text_compatible=True, builtin=False)
    def MacroCallback():
      pass  # pragma: no cover
    self.assertEqual('name', MacroCallback.public_name)
    self.assertEqual(',,', MacroCallback.args_signature)
    self.assertEqual(True, MacroCallback.text_compatible)
    self.assertEqual(False, MacroCallback.builtin)

  def testAutoParser_noArgs(self):
    @macro(public_name='name', args_signature='')
    def MacroCallback(executor, call_node):
      self.called = True

    self.__CheckMacroCall(MacroCallback, [])
    self.__CheckMacroCallFailure(MacroCallback, ['x'],
        '$name: arguments count mismatch: expected 0, got 1')

  def testAutoParser_allRequired(self):
    @macro(public_name='name', args_signature='one,*two,three')
    def MacroCallback(executor, call_node, one, two, three):
      self.__CheckMacroCallback(one, two, three)

    self.__CheckMacroCall(MacroCallback, ['1', '2', '3'], ['T1', '2', 'T3'])
    self.__CheckMacroCallFailure(MacroCallback, ['1', '2'],
        '$name(one,*two,three): arguments count mismatch: expected 3, got 2')
    self.__CheckMacroCallFailure(MacroCallback, ['1', '2', '3', '4'],
        '$name(one,*two,three): arguments count mismatch: expected 3, got 4')

  def testAutoParser_allOptional(self):
    @macro(public_name='name', args_signature='one?,*two?,three?')
    def MacroCallback(executor, call_node, one, two, three):
      self.__CheckMacroCallback(one, two, three)

    self.__CheckMacroCall(MacroCallback, ['1', '2', '3'], ['T1', '2', 'T3'])
    self.__CheckMacroCall(MacroCallback, ['1', '2'], ['T1', '2', None])
    self.__CheckMacroCall(MacroCallback, ['1'], ['T1', None, None])
    self.__CheckMacroCall(MacroCallback, [], [None, None, None])
    self.__CheckMacroCallFailure(MacroCallback, ['1', '2', '3', '4'],
        '$name(one?,*two?,three?): arguments count mismatch: expected 0..3, got 4')

  def testAutoParser_optionalAndRequired(self):
    @macro(public_name='name', args_signature='*one,two,*three?')
    def MacroCallback(executor, call_node, one, two, three):
      self.__CheckMacroCallback(one, two, three)

    self.__CheckMacroCall(MacroCallback, ['1', '2', '3'], ['1', 'T2', '3'])
    self.__CheckMacroCall(MacroCallback, ['1', '2'], ['1', 'T2', None])
    self.__CheckMacroCallFailure(MacroCallback, ['1'],
        '$name(*one,two,*three?): arguments count mismatch: expected 2..3, got 1')
    self.__CheckMacroCallFailure(MacroCallback, [],
        '$name(*one,two,*three?): arguments count mismatch: expected 2..3, got 0')
    self.__CheckMacroCallFailure(MacroCallback, ['1', '2', '3', '4'],
        '$name(*one,two,*three?): arguments count mismatch: expected 2..3, got 4')

  def testAutoParser_requiredThenOptional(self):
    def Try():
      @macro(public_name='name', args_signature='one?,two?,three')
      def MacroCallback():
        pass  # pragma: no cover
    self.assertRaises(AssertionError, Try)

  def testAutoParser_requiredThenOptionalThenRequired(self):
    def Try():
      @macro(public_name='name', args_signature='one,two?,three')
      def MacroCallback():
        pass  # pragma: no cover
    self.assertRaises(AssertionError, Try)


class GetMacroSignatureTest(TestCase):

  def testNoArgs(self):
    @macro()
    def MacroCallback():
      pass  # pragma: no cover
    self.assertEqual('$name', GetMacroSignature('name', MacroCallback))

  def testSomeArgs(self):
    @macro(args_signature='one,two,three')
    def MacroCallback():
      pass  # pragma: no cover
    self.assertEqual('$name(one,two,three)',
                     GetMacroSignature('name', MacroCallback))


class GetPublicMacrosTest(TestCase):

  class TestClass(object):
    @staticmethod
    @macro(public_name='public1')
    def PublicMacro1():
      pass  # pragma: no cover

    @staticmethod
    @macro()
    def Privatemacro():
      pass  # pragma: no cover

    @staticmethod
    @macro(public_name='public2')
    def PublicMacro2():
      pass  # pragma: no cover

  def testOnClass(self):
    self.assertEqual(dict(public1=self.TestClass.PublicMacro1,
                          public2=self.TestClass.PublicMacro2),
                     GetPublicMacros(self.TestClass))

  def testOnModule(self):
    module = imp.new_module('test')
    code = \
"""
from macros import macro

@macro(public_name='public1')
def PublicMacro1():
  pass

@macro()
def PrivateMacro():
  pass

@macro(public_name='public2')
def PublicMacro2():
  pass
"""
    exec code in module.__dict__
    self.assertEqual(dict(public1=module.PublicMacro1,
                          public2=module.PublicMacro2),
                     GetPublicMacros(module))

  def testMultipleCalls(self):
    self.assertEqual(GetPublicMacros(self.TestClass),
                     GetPublicMacros(self.TestClass))

  def testDuplicatePublicName(self):
    class TestClassDuplicate(object):
      @staticmethod
      @macro(public_name='same')
      def Same1():
        pass  # pragma: no cover

      @staticmethod
      @macro(public_name='same')
      def Same2():
        pass  # pragma: no cover

    try:
      GetPublicMacros(TestClassDuplicate)
      exception = False  # pragma: no cover
    except AssertionError:
      exception = True
    self.assertEqual(True, exception, 'expected: AssertionError')


if __name__ == '__main__':
  unittest.main()
