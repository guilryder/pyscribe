# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

from collections import defaultdict
from collections.abc import Callable, Collection
import inspect
import itertools
import operator
from typing import Any, cast, Optional, Protocol, TYPE_CHECKING

from parsing import CallNode, NodesT

if TYPE_CHECKING:
  from execution import ExecutionContext, Executor as _ExecutorT
else:
  _ExecutorT = 'Executor'


_Value = str | NodesT | None

_ArgsParser = Callable[[_ExecutorT, NodesT | None], _Value]

# The first argument is the parameter name without special prefixes/suffixes.
_NamedArgsParser = tuple[str, _ArgsParser]

# Parsers for the required and optional arguments of a macro.
_NamedArgsParsers = tuple[list[_NamedArgsParser], list[_NamedArgsParser]]


class StandardMacroT(Protocol):
  public_name: str
  # 'name1,name2,...,nameN', or '' if the macro has no arguments.
  args_signature: str
  text_compatible: bool
  builtin: bool

  def __call__(self, __executor: _ExecutorT, __call_node: CallNode) -> _Value:
    raise NotImplementedError


# Actual type: Callable[Concatenate[_ExecutorT, CallNode, ...], _Value]
MacroT = Callable[..., _Value]


# Macros keyed by name.
MacrosT = dict[str, StandardMacroT]



class macro:
  """Decorator for macro callbacks."""

  __arg_parsers: _NamedArgsParsers | None
  __attributes: dict[str, Any]

  def __init__(self, public_name: str | None=None, args_signature: str='',
               auto_args_parser: bool=True, text_compatible: bool=False,
               builtin: bool=True):
    """
    Args:
      public_name: The name of the macro if it is builtin, without '$' prefix.
      args_signature: The signature of the arguments of the macro.
        Should be an empty string for macros with no arguments,
        or a comma-separated list of names for macros with fixed arguments.
        Nodes arguments should be prefixed with '*'.
        Text-only arguments should not be prefixed.
        Optional arguments are suffixed with '?'. Optional arguments must be at
        the end of the arguments list.
      text_compatible: (bool) Whether the macro has no side-effects and can
        produce text-only output.
      builtin: Whether the macro is builtin as opposed to defined by the user
        via $macro.new; determines if the macro can be wrapped.
    """
    if auto_args_parser:
      self.__arg_parsers = self.__BuildArgParsers(args_signature)
    else:
      self.__arg_parsers = None

    self.__attributes = dict(
        public_name=public_name,
        args_signature=args_signature,
        text_compatible=text_compatible,
        builtin=builtin,
    )

  @staticmethod
  def __BuildArgParsers(args_signature: str) -> _NamedArgsParsers:
    """Builds argument parsers for the given signature.

    Args:
      args_signature: The signature of the macro.

    Returns:
      The required and optional argument parsers of the macro.
      Parsers for nodes arguments return their argument as is.
      Parsers for text-only arguments call Executor.EvalText.
    """
    if not args_signature:
      return [], []

    def TextArgParser(
        executor: _ExecutorT, arg: NodesT | None) -> str | None:
      if arg is None:
        return None
      else:
        return executor.EvalText(arg)

    def NodesArgParser(
        unused_executor: _ExecutorT, arg: NodesT | None) -> NodesT | None:
      return arg

    def ParseArgSignature(arg_signature: str) -> tuple[bool, _NamedArgsParser]:
      args_parser: _ArgsParser
      if arg_signature.startswith('*'):
        args_parser = NodesArgParser
        arg_signature = arg_signature[1:]
      else:
        args_parser = TextArgParser
      optional = arg_signature.endswith('?')
      if optional:
        arg_signature = arg_signature[:-1]
      return optional, (arg_signature, args_parser)

    # Split the list of arguments in two: first required, then optional.
    parsers_list = [ParseArgSignature(sig) for sig in args_signature.split(',')]
    parsers_grouped_by_optional = [
        (optional, [parser[1] for parser in parsers])
        for optional, parsers
        in itertools.groupby(parsers_list, operator.itemgetter(0))
    ]
    optionals = [parser[0] for parser in parsers_grouped_by_optional]
    assert len(optionals) <= 2 and optionals != [True, False], (
        'Invalid args signature: optional arguments must be grouped at the end')
    parsers_keyed_by_optional = defaultdict(list, parsers_grouped_by_optional)
    return (parsers_keyed_by_optional.get(False, []),
            parsers_keyed_by_optional.get(True, []))

  def __call__(self, callback: MacroT) -> StandardMacroT:
    # If automatic arguments parsing is enabled, wrap the callback.
    arg_parsers = self.__arg_parsers
    if arg_parsers is None:
      # args_signature set later.
      standard_callback = cast(StandardMacroT, callback)
    else:
      required_arg_parsers, optional_arg_parsers = arg_parsers
      min_args_count = len(required_arg_parsers)
      max_args_count = min_args_count + len(optional_arg_parsers)
      named_arg_parsers = required_arg_parsers + optional_arg_parsers
      def ArgsParsingWrapper(
          executor: _ExecutorT, call_node: CallNode) -> _Value:
        executor.CheckArgumentCount(call_node, standard_callback,
                                    min_args_count=min_args_count,
                                    max_args_count=max_args_count)
        args_iter = iter(call_node.args)
        extra_args = {}
        for name, parser in named_arg_parsers:
          extra_args[name] = parser(executor, next(args_iter, None))
        return callback(executor, call_node, **extra_args)
      # args_signature set later.
      standard_callback = cast(StandardMacroT, ArgsParsingWrapper)

    # Save the @macro attributes in the callback.
    for name, value in self.__attributes.items():
      setattr(standard_callback, name, value)
    return standard_callback


def GetMacroSignature(name: str, callback: StandardMacroT) -> str:
  """Returns the full signature of a macro.

  Args:
    name: The name of the macro, without '$' prefix.
    callback: The macro callback, with 'args_signature' attribute.

  Returns:
    The full signature of the macro: '$name' (empty args signature)
    or '$name(args signature)'.
  """
  if callback.args_signature:
    return f'${name}({callback.args_signature})'
  else:
    return f'${name}'


def GetPublicMacros(container: Any) -> MacrosT:
  """
  Returns the public macros declared by a module or class.

  Caches the result in the object.

  Args:
    container: The module or class that declares the macros

  Returns:
    The public macros, keyed by name.
  """
  if not hasattr(container, 'public_macros'):
    public_macros: MacrosT = {}
    for _, symbol in inspect.getmembers(container):
      public_name = getattr(symbol, 'public_name', None)
      if public_name is not None:
        assert public_name not in public_macros, (
            f'duplicate public name "{public_name}" in {container}')
        public_macros[public_name] = symbol
    container.public_macros = public_macros
  return cast(MacrosT, container.public_macros)


def GetPublicMacrosContainers() -> Collection[Any]:
  """Returns all public, built-in macros containers."""
  import core_macros  # pylint: disable=import-outside-toplevel
  return (
      core_macros, core_macros.SpecialCharacters,
      __import__('branch_macros'),
      __import__('builtin_macros'))


def ExecuteCallback(
    # pylint: disable=consider-alternative-union-syntax
    nodes: NodesT, call_context: Optional['ExecutionContext']=None,
    **kwargs: Any) -> StandardMacroT:
  """Creates a macro callback that executes the given nodes.

  The nodes are executed in the current call context of the given executor
  (current when ExecuteCallback is called, not when the returned callback is
  invoked).

  The callback expects no arguments.
  """
  kwargs.setdefault('text_compatible', True)
  @macro(**kwargs)
  def MacroCallback(executor: _ExecutorT, unused_call_node: CallNode) -> None:
    executor.ExecuteInCallContext(nodes, call_context=call_context)
  return MacroCallback


def AppendTextCallback(text: str, **kwargs: Any) -> StandardMacroT:
  """Creates a macro callback that writes the given text.

  The callback expects no arguments.
  """
  kwargs.setdefault('text_compatible', True)
  @macro(**kwargs)
  def MacroCallback(executor: _ExecutorT, unused_call_node: CallNode) -> None:
    executor.AppendText(text)
  return MacroCallback

def AppendTextMacro(public_name: str, text: str) -> StandardMacroT:
  """Creates a method to define a macro that writes the given text."""
  return staticmethod(  # type: ignore[return-value]
      AppendTextCallback(text, public_name=public_name))
