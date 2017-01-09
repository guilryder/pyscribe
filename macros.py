# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

from collections import defaultdict
import inspect
import itertools
import operator
import re


MACRO_NAME_PATTERN = r'(?:[\\]|-|[a-zA-Z0-9_.]*[a-zA-Z0-9_])'
VALID_MACRO_NAME_PATTERN = \
    r'(?:[\\_]|-|[a-zA-Z](?:[a-zA-Z0-9_.]*[a-zA-Z0-9_])?)'
VALID_MACRO_NAME_REGEXP = re.compile(r'\A' + VALID_MACRO_NAME_PATTERN + r'\Z')


class macro:
  """Decorator for macro callbacks."""

  def __init__(self, public_name=None, args_signature='',
               auto_args_parser=True, text_compatible=False, builtin=True):
    """
    Args:
      public_name: (string) The name of the macro if it is builtin,
        without '$' prefix.
      args_signature: (string) The signature of the arguments of the macro.
        Should be an empty string for macros with no arguments,
        or a comma-separated list of names for macros with fixed arguments.
        Nodes arguments should be prefixed with '*'.
        Text-only arguments should not be prefixed.
        Optional arguments are suffixed with '?'. Optional arguments must be at
        the end of the arguments list.
      text_compatible: (bool) Whether the macro has no side-effects and can
        produce text-only output.
      builtin: (bool) Whether the macro is builtin as opposed to defined by the
        user via $macro.new; determines if the macro can be wrapped.
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
  def __BuildArgParsers(args_signature):
    """
    Builds argument parsers for the given signature.

    Args:
      args_signature: (string) The signature of the macro.

    Returns:
      (arg parser list, arg parser list) The required and optional argument
      parsers of the macro. Each argument parser is a (name, parser) tuple,
      where 'name' is the parameter name without special prefixes/suffixes,
      and 'parser' is a (Executor, node list) -> object function.
      Parsers for nodes arguments return their argument as is.
      Parsers for text-only arguments call Executor.EvalText.
    """
    if not args_signature:
      return [], []

    def TextArgParser(executor, arg):
      if arg is None:
        return None
      else:
        return executor.EvalText(arg)

    def NodesArgParser(unused_executor, arg):
      return arg

    def ParseArgSignature(arg_signature):
      if arg_signature.startswith('*'):
        args_parser = NodesArgParser
        arg_signature = arg_signature[1:]
      else:
        args_parser = TextArgParser
      optional = arg_signature.endswith('?')
      if optional:
        arg_signature = arg_signature[:-1]
      return (optional, (arg_signature, args_parser))

    # Split the list of arguments in two: first required, then optional.
    parsers_list = [ParseArgSignature(sig) for sig in args_signature.split(',')]
    parsers_grouped_by_optional = \
        [(optional, [parser[1] for parser in parsers])
         for (optional, parsers)
         in itertools.groupby(parsers_list, operator.itemgetter(0))]
    optionals = [parser[0] for parser in parsers_grouped_by_optional]
    assert len(optionals) <= 2 and optionals != [True, False], \
        'Invalid args signature: optional arguments must be grouped at the end'

    parsers_keyed_by_optional = defaultdict(list, parsers_grouped_by_optional)
    return [parsers_keyed_by_optional[optional] for optional in (False, True)]

  def __call__(self, callback):
    # pylint: disable=unpacking-non-sequence
    # If automatic arguments parsing is enabled, wrap the callback.
    # standard_callback takes (executor, call_node) as parameters.
    # callback takes (executor, call_node, **kwargs).
    arg_parsers = self.__arg_parsers
    if arg_parsers is None:
      standard_callback = callback
    else:
      (required_arg_parsers, optional_arg_parsers) = arg_parsers
      min_args_count = len(required_arg_parsers)
      max_args_count = min_args_count + len(optional_arg_parsers)
      arg_parsers = required_arg_parsers + optional_arg_parsers
      def ArgsParsingWrapper(executor, call_node):
        executor.CheckArgumentCount(call_node, ArgsParsingWrapper,
                                    min_args_count=min_args_count,
                                    max_args_count=max_args_count)
        args_iter = iter(call_node.args)
        extra_args = {}
        for name, parser in arg_parsers:
          extra_args[name] = parser(executor, next(args_iter, None))
        return callback(executor, call_node, **extra_args)
      standard_callback = ArgsParsingWrapper

    # Save the @macro attributes in the callback.
    for name, value in self.__attributes.items():
      setattr(standard_callback, name, value)
    return standard_callback


def GetMacroSignature(name, callback):
  """
  Returns the full signature of a macro.

  Args:
    name: (string) The name of the macro, without '$' prefix.
    callback: (callable) The macro callback, with 'args_signature' attribute.

  Returns:
    (string) The full signature of the macro: '$name' (empty args signature)
    or '$name(args signature)'.
  """
  if callback.args_signature:
    return '${name}({args})'.format(name=name, args=callback.args_signature)
  else:
    return '${name}'.format(name=name)


def GetPublicMacros(container):
  """
  Returns the public macros declared by a module or class.

  Caches the result in the object.

  Args:
    container: (object) The module or class that declares the macros

  Returns:
    (string -> callable dict) The public macros, keyed by name.
  """
  if not hasattr(container, 'public_macros'):
    public_macros = {}
    for _, symbol in inspect.getmembers(container):
      public_name = getattr(symbol, 'public_name', None)
      if public_name is not None:
        assert public_name not in public_macros, \
            'duplicate public name "{public_name}" in {container}'.format(
                public_name=public_name, container=container)
        public_macros[public_name] = symbol
    container.public_macros = public_macros
  return container.public_macros


def ExecuteCallback(nodes, call_context=None, **kwargs):
  """
  Creates a macro callback that executes the given nodes.

  The nodes are executed in the current call context of the given executor
  (current when ExecuteCallback is called, not when the returned callback is
  invoked).

  The callback expects no arguments.
  """
  kwargs.setdefault('text_compatible', True)
  @macro(**kwargs)
  def MacroCallback(executor, unused_call_node):
    executor.ExecuteInCallContext(nodes, call_context=call_context)
  return MacroCallback


def AppendTextCallback(text, **kwargs):
  """
  Creates a macro callback that writes the given text.

  The callback expects no arguments.
  """
  kwargs.setdefault('text_compatible', True)
  @macro(**kwargs)
  def MacroCallback(executor, unused_call_node):
    executor.AppendText(text)
  return MacroCallback

def StaticAppendTextCallback(text, **kwargs):
  return staticmethod(AppendTextCallback(text, **kwargs))
