# -*- coding: utf-8 -*-
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

from execution import Executor
import log
from macros import macro
from parsing import CallNode, NodesT


# Text operations

def ParseArabic(number: str) -> int:
  try:
    return int(number)
  except ValueError as e:
    raise log.NodeError(f'invalid Arabic number: {number}') from e


@macro(public_name='case.lower', args_signature='text', text_compatible=True)
def CaseLower(executor: Executor, _: CallNode, text: str) -> None:
  """Converts text to lowercase."""
  executor.AppendText(text.lower())


@macro(public_name='case.upper', args_signature='text', text_compatible=True)
def CaseUpper(executor: Executor, _: CallNode, text: str) -> None:
  """Converts text to uppercase."""
  executor.AppendText(text.upper())


@macro(public_name='alpha.latin', args_signature='number', text_compatible=True)
def AlphaLatin(executor: Executor, _: CallNode, number: str) -> None:
  """Prints the uppercase Latin alphabetical representation of an Arabic number.

  Example: 1 -> A, 2 -> B.
  """

  # Validate the input.
  arabic_num = ParseArabic(number)
  if not 1 <= arabic_num <= 26:
    raise log.NodeError(
        f'unsupported number for conversion to latin letter: {number}')

  # Convert the Arabic number to a letter.
  executor.AppendText(chr(ord('A') + arabic_num - 1))


def ArabicToRoman(number: int) -> str:
  """Converts an Arabic number to Roman.

  Args:
    roman: The integer number to convert.

  Returns:
    Its Roman representation in uppercase, for instance 'CLII'.

  Raises:
    log.NodeError: The number has no Roman representation.
  """
  if not 0 < number < 4000:
    raise log.NodeError(f'unsupported number for conversion to Roman: {number}')

  conv_table = ((1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'),
                 (100, 'C'),  (90, 'XC'),  (50, 'L'),  (40, 'XL'),
                  (10, 'X'),   (9, 'IX'),   (5, 'V'),   (4, 'IV'),
                   (1, 'I'))
  roman_text = ''
  for arabic, roman in conv_table:
    count = number // arabic
    number -= arabic * count
    roman_text += roman * count
  return roman_text


@macro(public_name='roman', args_signature='number', text_compatible=True)
def Roman(executor: Executor, _: CallNode, number: str) -> None:
  """Prints the Roman representation of an Arabic number."""
  executor.AppendText(ArabicToRoman(ParseArabic(number)))


# Conditions

@macro(public_name='if.def',
       args_signature='macro_name,*then_block,*else_block?',
       text_compatible=True)
def IfDef(executor: Executor, _: CallNode,
          macro_name: str, then_block: NodesT, else_block: NodesT) -> None:
  if executor.LookupMacro(macro_name, text_compatible=False) is not None:
    executor.ExecuteNodes(then_block)
  elif else_block is not None:
    executor.ExecuteNodes(else_block)

@macro(public_name='if.eq', args_signature='a,b,*then_block,*else_block?',
       text_compatible=True)
def IfEq(executor: Executor, _: CallNode,
         a: str, b: str, then_block: NodesT, else_block: NodesT) -> None:
  if a == b:
    executor.ExecuteNodes(then_block)
  elif else_block is not None:
    executor.ExecuteNodes(else_block)


# Loops

@macro(public_name='repeat', args_signature='count,*contents',
       text_compatible=True)
def Repeat(executor: Executor, _: CallNode,
           count: str, contents: NodesT) -> None:
  for unused_index in range(_ParseInt(count)):
    executor.ExecuteNodes(contents)


# Counters

@macro(public_name='counter.create', args_signature='counter_name')
def CounterCreate(executor: Executor, _: CallNode, counter_name: str) -> None:
  """Creates a new counter initially set to zero.

  Creates the following macros to manipulate the counter:
      $<counter-name> (Arabic value)
      $<counter-name>.if.positive[ifpositive]
      $<counter-name>.set[value]
      $<counter-name>.incr
  """
  counter_value = 0

  @macro(text_compatible=True)
  def ValueCallback(executor: Executor, _: CallNode) -> None:
    """Writes the value of the counter as an arabic number."""
    executor.AppendText(str(counter_value))

  @macro(args_signature='*contents', text_compatible=True)
  def IfPositiveCallback(executor: Executor, _: CallNode,
                         contents: NodesT) -> None:
    """Executes the contents if the counter is strictly positive (1 or more)."""
    if counter_value > 0:
      executor.ExecuteNodes(contents)

  @macro(args_signature='value')
  def SetCallback(unused_executor: Executor, _: CallNode, value: str) -> None:
    """Sets the value of a counter to the given integer."""
    nonlocal counter_value
    counter_value = _ParseInt(value)

  @macro()
  def IncrCallback(unused_executor: Executor, _: CallNode) -> None:
    """Increments the counter."""
    nonlocal counter_value
    counter_value += 1

  macros = {
      '': ValueCallback,
      '.if.positive': IfPositiveCallback,
      '.set': SetCallback,
      '.incr': IncrCallback,
  }
  for name_suffix, callback in macros.items():
    macro_name = f'{counter_name}{name_suffix}'
    executor.current_branch.context.AddMacro(macro_name, callback)


def _ParseInt(text: str) -> int:
  try:
    return int(text)
  except ValueError as e:
    raise log.NodeError(f'invalid integer value: {text}') from e
