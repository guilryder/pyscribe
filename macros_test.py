#!/usr/bin/env python3
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

import importlib.util

from execution import Executor
import log
import macros
from macros import macro
from parsing import CallNode
import testutils


class MacroTest(testutils.TestCase):
  # pylint: disable=attribute-defined-outside-init

  def setUp(self):
    super().setUp()
    self.logger = testutils.FakeLogger()
    fs = testutils.FakeFileSystem()
    self.executor = Executor(logger=self.logger, fs=fs,
                             current_dir=fs.Path('/cur'),
                             output_path_prefix=fs.Path('/output'))
    self.executor.EvalText = lambda args: 'T' + args

  def __MacroCall(self, macro_callback, args):
    call_node = CallNode(testutils.TEST_LOCATION, 'name', args)
    self.called = False
    macro_callback(self.executor, call_node)

  def __CheckMacroCallback(self, *actual_args):
    self.called = True
    self.assertEqual(list(actual_args), self.expected_args)

  def __CheckMacroCall(self, macro_callback, args, expected_args=None):
    self.expected_args = expected_args
    self.__MacroCall(macro_callback, args)
    self.assertTrue(self.called)

  def __CheckMacroCallFailure(self, macro_callback, args, expected_message):
    expected_message_full = f'{testutils.TEST_LOCATION}: {expected_message}'
    with self.assertRaises(log.FatalError) as ctx:
      self.__MacroCall(macro_callback, args)
    self.logger.LogException(ctx.exception)
    self.assertFalse(self.called, 'expected macro callback not invoked')
    self.assertEqual(self.logger.ConsumeStdErr(), expected_message_full)

  def testDefault(self):
    @macro()
    def MacroCallback():
      raise NotImplementedError
    self.assertEqual(MacroCallback.public_name, None)
    self.assertEqual(MacroCallback.args_signature, '')
    self.assertEqual(MacroCallback.text_compatible, False)
    self.assertEqual(MacroCallback.builtin, True)

  def testCustom(self):
    @macro(public_name='name', args_signature=',,', auto_args_parser=False,
           text_compatible=True, builtin=False)
    def MacroCallback():
      raise NotImplementedError
    self.assertEqual(MacroCallback.public_name, 'name')
    self.assertEqual(MacroCallback.args_signature, ',,')
    self.assertEqual(MacroCallback.text_compatible, True)
    self.assertEqual(MacroCallback.builtin, False)

  def testAutoParser_noArgs(self):
    @macro(public_name='name', args_signature='')
    def MacroCallback(unused_executor, unused_call_node):
      self.called = True

    self.__CheckMacroCall(MacroCallback, [])
    self.__CheckMacroCallFailure(MacroCallback, ['x'],
        '$name: arguments count mismatch: expected 0, got 1')

  def testAutoParser_allRequired(self):
    @macro(public_name='name', args_signature='one,*two,three')
    def MacroCallback(unused_executor, unused_call_node, one, two, three):
      self.__CheckMacroCallback(one, two, three)

    self.__CheckMacroCall(MacroCallback, ['1', '2', '3'], ['T1', '2', 'T3'])
    self.__CheckMacroCallFailure(MacroCallback, ['1', '2'],
        '$name(one,*two,three): arguments count mismatch: expected 3, got 2')
    self.__CheckMacroCallFailure(MacroCallback, ['1', '2', '3', '4'],
        '$name(one,*two,three): arguments count mismatch: expected 3, got 4')

  def testAutoParser_allOptional(self):
    @macro(public_name='name', args_signature='one?,*two?,three?')
    def MacroCallback(unused_executor, unused_call_node, one, two, three):
      self.__CheckMacroCallback(one, two, three)

    self.__CheckMacroCall(MacroCallback, ['1', '2', '3'], ['T1', '2', 'T3'])
    self.__CheckMacroCall(MacroCallback, ['1', '2'], ['T1', '2', None])
    self.__CheckMacroCall(MacroCallback, ['1'], ['T1', None, None])
    self.__CheckMacroCall(MacroCallback, [], [None, None, None])
    self.__CheckMacroCallFailure(MacroCallback, ['1', '2', '3', '4'],
        '$name(one?,*two?,three?): arguments count mismatch: ' +
        'expected 0..3, got 4')

  def testAutoParser_optionalAndRequired(self):
    @macro(public_name='name', args_signature='*one,two,*three?')
    def MacroCallback(unused_executor, unused_call_node, one, two, three):
      self.__CheckMacroCallback(one, two, three)

    self.__CheckMacroCall(MacroCallback, ['1', '2', '3'], ['1', 'T2', '3'])
    self.__CheckMacroCall(MacroCallback, ['1', '2'], ['1', 'T2', None])
    self.__CheckMacroCallFailure(MacroCallback, ['1'],
        '$name(*one,two,*three?): arguments count mismatch: ' +
        'expected 2..3, got 1')
    self.__CheckMacroCallFailure(MacroCallback, [],
        '$name(*one,two,*three?): arguments count mismatch: ' +
        'expected 2..3, got 0')
    self.__CheckMacroCallFailure(MacroCallback, ['1', '2', '3', '4'],
        '$name(*one,two,*three?): arguments count mismatch: ' +
        'expected 2..3, got 4')

  def testAutoParser_requiredThenOptional(self):
    with self.assertRaises(AssertionError):
      @macro(public_name='name', args_signature='one?,two?,three')
      def MacroCallback():  # pragma: no cover
        raise NotImplementedError

  def testAutoParser_requiredThenOptionalThenRequired(self):
    with self.assertRaises(AssertionError):
      @macro(public_name='name', args_signature='one,two?,three')
      def MacroCallback():  # pragma: no cover
        raise NotImplementedError


class GetMacroSignatureTest(testutils.TestCase):

  def testNoArgs(self):
    @macro()
    def MacroCallback():
      raise NotImplementedError
    self.assertEqual(macros.GetMacroSignature('name', MacroCallback), '$name')

  def testSomeArgs(self):
    @macro(args_signature='one,two,three')
    def MacroCallback():
      raise NotImplementedError
    self.assertEqual(macros.GetMacroSignature('name', MacroCallback),
                     '$name(one,two,three)')


class GetPublicMacrosTest(testutils.TestCase):

  class TestClass:
    @staticmethod
    @macro(public_name='public1')
    def PublicMacro1():
      raise NotImplementedError

    @staticmethod
    @macro()
    def Privatemacro():
      raise NotImplementedError

    @staticmethod
    @macro(public_name='public2')
    def PublicMacro2():
      raise NotImplementedError

  def testOnClass(self):
    self.assertEqual(macros.GetPublicMacros(self.TestClass),
                     dict(public1=self.TestClass.PublicMacro1,
                          public2=self.TestClass.PublicMacro2))

  def testOnModule(self):
    module_spec = importlib.util.spec_from_loader('test', loader=None)
    module = importlib.util.module_from_spec(module_spec)
    code = (
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
""")
    exec(code, module.__dict__)  # pylint: disable=exec-used
    self.assertEqual(macros.GetPublicMacros(module),
                     dict(public1=getattr(module, 'PublicMacro1'),
                          public2=getattr(module, 'PublicMacro2')))

  def testMultipleCalls(self):
    self.assertEqual(macros.GetPublicMacros(self.TestClass),
                     macros.GetPublicMacros(self.TestClass))

  def testDuplicatePublicName(self):
    class TestClassDuplicate:
      @staticmethod
      @macro(public_name='same')
      def Same1():
        raise NotImplementedError

      @staticmethod
      @macro(public_name='same')
      def Same2():
        raise NotImplementedError

    with self.assertRaises(AssertionError):
      macros.GetPublicMacros(TestClassDuplicate)


if __name__ == '__main__':
  testutils.unittest.main()
