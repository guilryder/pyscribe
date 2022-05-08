# -*- coding: utf-8 -*-
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

from collections.abc import Callable, Sequence
from pathlib import PurePath
import re
from typing import Optional

from execution import ExecutionContext, Executor, PYSCRIBE_EXT
from log import FatalError, NodeError
from macros import *
from parsing import CallNode, NodesT


class SpecialCharacters:

  TextPercent = AppendTextMacro('text.percent', '%')
  TextAmpersand = AppendTextMacro('text.ampersand', '&')
  TextBackslash = AppendTextMacro('text.backslash', '\\')
  TextCaret = AppendTextMacro('text.caret', '^')
  TextUnderscore = AppendTextMacro('text.underscore', '_')
  TextDollar = AppendTextMacro('text.dollar', '$')
  TextHash = AppendTextMacro('text.hash', '#')
  TextNbsp = AppendTextMacro('text.nbsp', '\xa0')
  TextSoftHyphen = AppendTextMacro('text.softhyphen', '­')
  TextDashEn = AppendTextMacro('text.dash.en', '–')
  TextDashEm = AppendTextMacro('text.dash.em', '—')
  TextEllipsis = AppendTextMacro('text.ellipsis', '…')
  TextGuillemetOpen = AppendTextMacro('text.guillemet.open', '«')
  TextGuillemetClose = AppendTextMacro('text.guillemet.close', '»')
  TextBacktick = AppendTextMacro('text.backtick', "`")
  TextApostrophe = AppendTextMacro('text.apostrophe', "'")
  TextQuoteOpen = AppendTextMacro('text.quote.open', '“')
  TextQuoteClose = AppendTextMacro('text.quote.close', '”')
  Newline = AppendTextMacro('newline', '\n')

  @staticmethod
  @macro(public_name='text.punctuation.double', args_signature='contents',
         text_compatible=True)
  def TextPunctuationDouble(executor: Executor, _: CallNode,
                            contents: str) -> None:
    executor.AppendText(contents)

  @staticmethod
  @macro(public_name='-', text_compatible=True)
  def TextSoftHyphenAlias(executor: Executor, call_node: CallNode) -> None:
    called_node = CallNode(call_node.location, 'text.softhyphen', [])
    executor.CallMacro(called_node)


@macro(public_name='empty', text_compatible=True)
def Empty(unused_executor: Executor, _: CallNode) -> None:
  pass


@macro(public_name='eval.text', args_signature='text', text_compatible=True)
def EvalText(executor: Executor, _: CallNode, text: str) -> None:
  executor.AppendText(text)


@macro(public_name='log', args_signature='message', text_compatible=True)
def Log(executor: Executor, _: CallNode, message: str) -> None:
  """Logs the given information message."""
  executor.logger.LogInfo(message)


@macro(public_name='include', args_signature='path')
def Include(executor: Executor, call_node: CallNode, path: str) -> None:
  """Includes and executes the given PyScribe file.

  Args:
    path: The path of the file, relative to the current file.
      Automatically appends the '.psc' extension to the file name if the given
      file name has no extension.
  """
  _IncludeFile(executor.ExecuteFile,
               executor, call_node, path, default_ext=PYSCRIBE_EXT)


@macro(public_name='include.text', args_signature='path', text_compatible=True)
def IncludeText(executor: Executor, call_node: CallNode, path: str) -> None:
  """Includes the given UTF-8 text file.

  Args:
    path: The path of the file, relative to the current file, with extension.
  """
  def Run(resolved_path: PurePath) -> None:
    with executor.fs.open(resolved_path, mode='rt') as reader:
      executor.AppendText(reader.read())
  _IncludeFile(Run, executor, call_node, path, default_ext=None)


def _IncludeFile(resolved_path_handler: Callable[[PurePath], None],
                 executor: Executor, call_node: CallNode,
                 path: str, default_ext: Optional[str]) -> None:
  try:
    directory = call_node.location.filename.dir_path
    resolved_path = executor.ResolveFilePath(path,
                                             directory=directory,
                                             default_ext=default_ext)
    resolved_path_handler(resolved_path)
  except FatalError:
    raise
  except Exception as e:
    raise NodeError(f'unable to include "{path}": {e}') from e


__SIGNATURE_REGEX = re.compile(
    r'^ \s*' +
    r'(?P<name>' + VALID_MACRO_NAME_PATTERN + r') \s*' +
    r'(?:' +
        r'\( \s* (' +
            '(?:' + VALID_MACRO_NAME_PATTERN + r'\s*,\s* )*' +
            VALID_MACRO_NAME_PATTERN +
        r'\s* )? \)' +
    r')?' +
    r'\s* $',
    re.VERBOSE)

@macro(public_name='macro.new', args_signature='signature,*body')
def MacroNew(executor: Executor, _: CallNode,
             signature: str, body: NodesT) -> None:
  """Defines a new macro in the branch context.

  See the signature format specification in ParseMacroSignature.

  When invoked, the body of the macro is executed in a call context containing
  a macro for each argument, set to the value provided by the caller.
  """
  macro_name, macro_arg_names = ParseMacroSignature(signature)
  callback = MacroNewCallback(executor.call_context, macro_arg_names, body)
  executor.current_branch.context.AddMacro(macro_name, callback)

def ParseMacroSignature(signature: str) -> tuple[str, list[str]]:
  """Parses the given macro signature.

  Accepted formats:
  - with arguments: 'name(arg1,...,argN)'
  - with no arguments: 'name' or 'name()'
  Spaces between tokens are ignored.

  Returns:
    The macro name and list of arguments.
  """

  # Parse the macro name and arguments.
  signature_match = __SIGNATURE_REGEX.match(signature)
  if not signature_match:
    raise NodeError(f'invalid signature: {signature}')
  macro_name = signature_match.group(1)
  macro_arg_names_text = signature_match.group(2)
  if macro_arg_names_text is None:
    macro_arg_names = []
  else:
    macro_arg_names = [name.strip() for name in macro_arg_names_text.split(',')]

  # Check that the macro arguments are unique.
  macro_arg_names_set = frozenset(macro_arg_names)
  if len(macro_arg_names_set) != len(macro_arg_names):
    for macro_arg_name in macro_arg_names:
      macro_arg_names.remove(macro_arg_name)
    raise NodeError(f'duplicate argument in signature: {macro_arg_names[0]}')
  return macro_name, macro_arg_names

def MacroNewCallback(
    macro_call_context: ExecutionContext, macro_arg_names: Sequence[str],
    body: NodesT):
  """The callback of a macro defined by MacroNew.

  Allows $macro.wrap to add head and tail hooks to the initial macro body.

  Defined outside of MacroNew to avoid using the wrong variables.
  """
  @macro(args_signature=','.join(macro_arg_names), auto_args_parser=False,
         text_compatible=True, builtin=False)
  def MacroCallback(executor: Executor, call_node: CallNode) -> None:
    executor.CheckArgumentCount(call_node, MacroCallback, len(macro_arg_names))

    # Execute the arguments in the current context.
    arg_call_context = executor.call_context

    # Execute the head hooks, if any.
    for hook in MacroCallback.head_hooks:
      hook(executor)

    # Execute the body in the macro definition context augmented with arguments.
    # Using the macro definition context instead of the current context allows
    # partial macro definitions such as $inner[y] below: it depends on the
    # argument $x of the enclosing macro definition $outer[x]:
    # $macro.new[outer(x)][$macro.new[inner(y)][$x $y]]
    body_call_context = ExecutionContext(parent=macro_call_context)
    for macro_arg_name, arg in zip(macro_arg_names, call_node.args):
      body_call_context.AddMacro(macro_arg_name,
                                 ExecuteCallback(arg, arg_call_context))
    executor.ExecuteInCallContext(body, body_call_context)

    # Execute the tail hooks, if any.
    for hook in MacroCallback.tail_hooks:
      hook(executor)

  MacroCallback.head_hooks = []
  MacroCallback.tail_hooks = []
  return MacroCallback


@macro(public_name='macro.override', args_signature='signature,original,*body')
def MacroOverride(executor: Executor, _: CallNode,
                  signature: str, original: str, body: NodesT) -> None:
  """Overrides the definition of an existing macro.

  Args:
    signature: Same syntax as in $macro.new. The new macro may have a different
      signature than the original.
    original: The name of the variable to set with the original macro.
      Allows the new macro to call the original one.
    body: The body of the new macro.

  When invoked, the body of the macro is executed in a call context containing:
  * a macro for each argument, set to the value provided by the caller
  * $original set to the overridden macro
  """
  macro_name, macro_arg_names = ParseMacroSignature(signature)
  if VALID_MACRO_NAME_REGEXP.match(original) is None:
    raise NodeError(f'invalid original macro name: {original}')
  if original in macro_arg_names:
    raise NodeError('original macro name conflicts with signature: '
                    f'{original} vs. {signature}')
  macro_callback = _LookupNonBuiltinMacro(executor, macro_name, 'override')

  # Create the override execution context: map the original macro to $original.
  body_call_context = ExecutionContext(parent=executor.call_context)
  body_call_context.AddMacro(original, macro_callback)

  callback = MacroNewCallback(body_call_context, macro_arg_names, body)
  executor.current_branch.context.AddMacro(macro_name, callback)


@macro(public_name='macro.wrap', args_signature='macro_name,*head,*tail')
def MacroWrap(executor: Executor, _: CallNode,
              macro_name: str, head: NodesT, tail: NodesT) -> None:
  """Wraps an existing non-builtin macro with head and tail contents.

  The head and tail are executed in a context that does not contain the
  arguments of the wrapped macro.
  """

  # Check that the macro exists and is not builtin.
  macro_callback = _LookupNonBuiltinMacro(executor, macro_name, 'wrap')

  # Add the hooks.
  if head is not None:
    macro_callback.head_hooks.insert(
        0, _MakeHook(head, executor.call_context))
  if tail is not None:
    macro_callback.tail_hooks.append(
        _MakeHook(tail, executor.call_context))

def _MakeHook(nodes: NodesT, call_context: ExecutionContext):
  def Hook(executor: Executor) -> None:
    executor.ExecuteInCallContext(nodes, call_context=call_context)
  return Hook


@macro(public_name='macro.call', args_signature='macro_name,arg1,...,argN',
       text_compatible=True, auto_args_parser=False)
def MacroCall(executor: Executor, call_node: CallNode) -> None:
  """
  Calls a macro dynamically, by reflection.

  Args:
    macro_name: The name of the macro to call.
    arg1..N: The arguments to pass to the macro.
  """
  executor.CheckArgumentCount(call_node, MacroCall,
                              min_args_count=1, max_args_count=-1)

  macro_name_nodes = call_node.args[0]
  macro_name = executor.EvalText(macro_name_nodes)
  if not (macro_name and macro_name_nodes):
    raise NodeError('expected non-empty macro name')

  called_node = CallNode(macro_name_nodes[0].location, macro_name,
                         call_node.args[1:])
  executor.CallMacro(called_node)


@macro(public_name='macro.context.new', args_signature='*body')
def MacroContextNew(executor: Executor, _: CallNode, body: NodesT) -> None:
  """
  Executes code in a new execution context.

  Allows to define temporary macros in the new context.

  Args:
    body: The code to execute in the new context.
  """
  new_branch_context = ExecutionContext(parent=executor.current_branch.context)
  executor.ExecuteInBranchContext(body, new_branch_context)


def _LookupNonBuiltinMacro(
    executor: Executor, macro_name: str, verb: str):
  """Looks up a non-built-in macro by name."""
  macro_callback = executor.LookupMacro(macro_name, text_compatible=False)
  if macro_callback is None:
    raise NodeError(f'cannot {verb} a non-existing macro: {macro_name}')
  if macro_callback.builtin:
    raise NodeError(f'cannot {verb} a built-in macro: {macro_name}')
  return macro_callback
