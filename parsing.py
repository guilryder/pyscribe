#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

import inspect
import itertools
import re
import sys

from macros import MACRO_NAME_PATTERN, VALID_MACRO_NAME_PATTERN
from log import *
import yacc


VALID_MACRO_NAME_REGEXP = re.compile(r'\A' + VALID_MACRO_NAME_PATTERN + r'\Z')


class Token(object):
  """
  Token generated by Lexer.

  Exposes the fields used by yacc:
    type: (String) The type of the token, must be one of TYPES elements.
    lineno: (int) The line index of the first character of the token.
    value: (String) The contents of the token.
  """

  TYPES = (
    'LBRACKET',  # value: ignored
    'RBRACKET',  # value: ignored
    'TEXT',      # value: unescaped text
    'MACRO',     # value: macro name without '$' prefix
  )

  def __init__(self, type, lineno, value):
    self.type = type
    self.lineno = lineno
    self.value = value

  def __repr__(self):
    return '({0.type} l{0.lineno} {0.value!r})'.format(self)


class TextNode(object):
  """Plain text node; may contain line breaks."""

  def __init__(self, location, text):
    self.location = location
    self.text = unicode(text)

  def __str__(self):
    return repr(self.text)[1:]

  def __repr__(self):
    return "{0.location!r}{0}".format(self)

  def __eq__(self, other):
    return isinstance(other, TextNode) and repr(self) == repr(other)


class CallNode(object):
  """
  Macro call node.

  Fields:
    location: (Location) The location of the call node.
    name: (string) The name of the macro called, without '$' prefix.
    args: (node list list) The arguments of the macro, each as a list of nodes.
  """

  def __init__(self, location, name, args):
    self.location = location
    self.name = name
    self.args = args

  def __str__(self):
    return '${name}{args}'.format(
        name=self.name,
        args=''.join('[%s]' % FormatNodes(param) for param in self.args))

  def __repr__(self):
    return '${name}{args}'.format(
        name=self.name,
        args=''.join('[%s]' % ReprNodes(param) for param in self.args))

  def __eq__(self, other):
    return isinstance(other, CallNode) and \
           self.location == other.location and \
           self.name == other.name and \
           self.args == other.args


def CompactTextNodes(nodes):
  """
  Merges consecutive text nodes located on the same line.

  Args:
    nodes: (Node iter) The nodes to process.

  Yields: (Node) The input nodes with consecutive text nodes merged.
    The location of a merged text node is the location of the first original
    text node.
  """
  def GroupingKey(node):
    return (type(node), node.location)
  for (node_type, location), nodes in itertools.groupby(nodes, GroupingKey):
    if issubclass(node_type, TextNode):
      nodes = list(nodes)
      yield TextNode(location, ''.join(node.text for node in nodes))
    else:
      for node in nodes:
        yield node


def FormatNodes(nodes):
  """Formats the given text nodes into a human-readable string."""
  return ''.join(str(node) for node in CompactTextNodes(nodes))


def ReprNodes(nodes):
  """Formats the given text nodes into a representation string."""
  return ''.join(repr(node) for node in nodes)


class ParsingContext(object):
  """
  Context for parsing an input file.

  Fields:
    filename: (Filename) The name of the file parsed.
    logger: (Logger) The logger to use to report errors
    fatal_error: (bool) Whether a fatal error has been encountered.
  """

  def __init__(self, filename, logger):
    assert isinstance(filename, Filename)
    self.filename = filename
    self.logger = logger
    self.fatal_error = False

  def Location(self, lineno):
    """Builds a Location object for this context."""
    return Location(self.filename, lineno)

  def FatalError(self, *args, **kwargs):
    """
    Records a fatal error.

    See Logger.Log() for parameters.
    """
    self.fatal_error = True
    return self.logger.Log(*args, **kwargs)


class RegexpParser(object):
  """
  Regexp-based parser.

  Creates a parsing rule for each method starting with 'Rule' in an object.
  The docstring of the method is expected to be a regexp.
  """

  def __init__(self, rules_container):
    """
    Args:
      rules_container: (object) The object that contains the rules.
        Each rule must be prefixed with 'Rule' and have a regexp as docstring.
    """

    # Retrieve the rules from the container.
    self.__rules = {}
    rules = []  # (name, pattern) list
    rule_pattern = re.compile('Rule(?P<name>.+)')
    for symbol_name, symbol in inspect.getmembers(rules_container):
      rule_match = rule_pattern.match(symbol_name)
      if rule_match:
        rule_name = rule_match.group('name')
        rule_regexp = symbol.__doc__
        assert rule_regexp is not None, 'Regexp missing in ' + symbol_name
        rules.append((rule_name, rule_regexp))
        self.__rules[rule_name] = symbol

    # Compute the aggregate regexp for all rules.
    full_pattern = '|'.join(
        u'(?P<{name}>{pattern})'.format(name=name, pattern=pattern)
        for name, pattern in rules)
    self.__regexp = re.compile(full_pattern, re.MULTILINE)

  def Parse(self, input_text):
    """
    Parses the given input text.

    Args:
      input_text: (string) The text to parse.

    Yields:
      (string, callable|None, string|None) The non-overlapping matches of the
      rules, each as a (text_before, rule_callable, matched_text) tuple.
      'text_before' is the text between the previous match (or the beginning of
      the string for the first match) and the current match.
      'rule_callable' and 'matched_text' are the rule and the text that matched,
      None after the last match if there is text after it.
    """
    rules = self.__rules
    last_end = 0

    for match in self.__regexp.finditer(input_text):
      (match_begin, match_end) = match.span()
      rule_name = match.lastgroup
      yield (input_text[last_end:match_begin],
             rules[rule_name], match.group(rule_name))
      last_end = match_end

    if last_end < len(input_text):
      yield (input_text[last_end:], None, None)


class Lexer(object):

  __GLOBAL_STRIP_REGEXP = re.compile(r'(?:|`|\s*(.*?)(?<=[^`])\s*`?)\Z',
                              re.MULTILINE | re.DOTALL)
  __LINE_REGEXP = re.compile(r'[ \t]*(\n+)[ \t]*')

  def __init__(self, context, input_text):
    # Strip whitespace around the input text.
    input_text_match = self.__GLOBAL_STRIP_REGEXP.match(input_text)
    self.__lineno = 1 + input_text[:input_text_match.start(1)].count('\n')
    self.__skip_spaces = True
    self.__input_text = input_text_match.group(1) or ''

    self.context = context
    self.__filename = context.filename
    self.__parser = RegexpParser(self)
    self.__tokens = self.__MergeTextTokensSameLine(self.__Parse())
    self.__preproc_instr_callbacks = {
        'whitespace.preserve': self.__PreprocessWhitespacePreserve,
        'whitespace.skip': self.__PreprocessWhitespaceSkip,
    }
    self.__text_processor = self.__TextProcessorPreserveWhitespace

  def __iter__(self):
    """Returns the tokens iterator."""
    return self.__tokens

  def token(self):
    """Returns the next token, None if the input is exhausted."""
    return next(iter(self), None)

  def __MergeTextTokensSameLine(self, tokens):
    """
    Merges the consecutive text tokens that have the same line.

    Args:
      nodes: (Token iter) The tokens to process.

    Yields: (Token)
    """
    text_token_accu = None
    for token in tokens:
      if token.type == 'TEXT':
        # Text token
        if text_token_accu:
          if text_token_accu.lineno == token.lineno:
            # Same line: append the text token to the accumulator.
            text_token_accu.value += token.value
            continue
          yield text_token_accu
          text_token_accu = None
          yield token
        else:
          # Start a new text accumulator.
          text_token_accu = token
      else:
        # Not a text token: flush the text accumulator (if any) then the token.
        if text_token_accu:
          yield text_token_accu
          text_token_accu = None
        yield token

    if text_token_accu:
      yield text_token_accu

  def __Parse(self):
    """
    Parses the tokens.

    Yields: (Token) The parsed tokens.
    """
    from collections import Iterable
    for text_before, rule_callable, matched_text in \
        self.__parser.Parse(self.__input_text):
      if text_before:
        if self.__skip_spaces:
          text_before = text_before.lstrip(' \t')
        for token in self.__text_processor(text_before):
          yield token
        self.__skip_spaces = (text_before and text_before[-1] == '\n')
      if rule_callable:
        token = rule_callable(matched_text)
        if isinstance(token, Iterable):
          for single_token in token:
            yield single_token
        elif token:
          yield token

  def __TextProcessorPreserveWhitespace(self, text):
    """
    Yields tokens for a block of text, preserving whitespace.

    Ensures that line returns are always at the end of a token.
    Strips spaces around each line.
    """
    lineno = self.__lineno

    # Yield the text before each sequence of newlines,
    # including the newlines themselves but without surrounding spaces.
    last_end = 0
    for match in self.__LINE_REGEXP.finditer(text):
      (match_begin, match_end) = match.span()
      newlines = match.group(1)
      yield Token('TEXT', lineno, text[last_end:match_begin] + newlines)
      lineno += len(newlines)
      last_end = match_end

    # Yield the last chunk of text.
    if last_end < len(text):
      yield Token('TEXT', lineno, text[last_end:])

    self.__lineno = lineno
    self.__skip_spaces = False
  __TextProcessorPreserveWhitespace.skip_whitespace_after_macro = False

  def __TextProcessorSkipWhitespace(self, text):
    """
    Sames as __TextProcessorPreserveWhitespace, but skips more whitespace.

    Skips newlines and whitespace after macros.
    """
    lineno = self.__lineno

    # Yield the text before each sequence of newlines.
    last_end = 0
    for match in self.__LINE_REGEXP.finditer(text):
      (match_begin, match_end) = match.span()
      if last_end < match_begin:
        yield Token('TEXT', lineno, text[last_end:match_begin])
      lineno += len(match.group(1))
      last_end = match_end

    # Yield the last chunk of text.
    if last_end < len(text):
      yield Token('TEXT', lineno, text[last_end:])

    self.__lineno = lineno
    self.__skip_spaces = False
  __TextProcessorSkipWhitespace.skip_whitespace_after_macro = True

  def __Location(self):
    return Location(self.__filename, self.__lineno)

  def __UpdateLineno(self, text):
    if text:
      self.__lineno += text.count('\n')
      self.__skip_spaces = (text[-1] == '\n')

  def RuleComment(self, value):
    r'[ \t]*\#.*(?:\n\s*|\Z)'
    self.__UpdateLineno(value)
    return None

  def RuleEscape(self, value):
    r'`.'
    self.__skip_spaces = False
    return Token('TEXT', self.__lineno, value[1:])

  def RuleLbracket(self, value):
    r'\[\s*'
    token = Token('LBRACKET', self.__lineno, '[')
    self.__UpdateLineno(value)
    return token

  def RuleRbracket(self, value):
    r'\s*\]'
    token = Token('RBRACKET', self.__lineno, value)
    self.__UpdateLineno(value)
    return token

  # Pre-processing statement

  def RulePreProcessingInstruction(self, value):
    r'\$\$[a-zA-Z0-9._]*\n?'
    preproc_instr_name = value[2:].strip()
    preproc_instr_callback = self.__preproc_instr_callbacks.get(preproc_instr_name)
    if preproc_instr_callback:
      preproc_instr_callback()
    else:
      self.context.FatalError(
          self.__Location(),
          u"unknown pre-processing instruction: '{name}'\n" +
          u"known instructions: {known}",
          name='$$' + preproc_instr_name,
          known=', '.join(sorted((
              '$$' + name for name in self.__preproc_instr_callbacks))))
    self.__UpdateLineno(value)
    self.__skip_spaces = True
    return None

  def __PreprocessWhitespacePreserve(self):
    self.__text_processor = self.__TextProcessorPreserveWhitespace

  def __PreprocessWhitespaceSkip(self):
    self.__text_processor = self.__TextProcessorSkipWhitespace

  # Macro

  def RuleMacro(self, value):
    macro_name = value[1:]
    if not VALID_MACRO_NAME_REGEXP.match(macro_name):
      return self.RuleMacroInvalid(value)
    token = self.__MacroToken(value[1:])
    self.__skip_spaces |= self.__text_processor.skip_whitespace_after_macro
    return token
  RuleMacro.__doc__ = r'\$' + MACRO_NAME_PATTERN

  def RuleMacroInvalid(self, value):
    r'\$(?:[^$]\S{,9}|\Z)'
    self.context.FatalError(self.__Location(),
                            u"invalid macro name: '{name}'",
                            name=value)
    return None

  # Special characters

  def RulePercent(self, _):
    r'%'
    return self.__MacroToken('text.percent')

  def RuleAmpersand(self, _):
    r'&'
    return self.__MacroToken('text.ampersand')

  def RuleUnderscore(self, _):
    r'_'
    return self.__MacroToken('text.underscore')

  def RuleNonBreakingSpace(self, _):
    r'~'
    return self.__MacroToken('text.nbsp')

  def RuleDashes(self, value):
    r'-{2,}'
    length = len(value)
    if length == 2:
      dash_name = 'en'
    elif length == 3:
      dash_name = 'em'
    else:
      return Token('TEXT', self.__lineno, value)
    return self.__MacroToken('text.dash.' + dash_name)

  def RuleEllipsis(self, value):
    r'\.{3,}'
    if len(value) == 3:
      return self.__MacroToken('text.ellipsis')
    else:
      return Token('TEXT', self.__lineno, value)

  def RuleGuillemetOpen(self, value):
    ur'«|\<{2,}'
    if len(value) <= 2:
      return self.__MacroToken('text.guillemet.open')
    else:
      return Token('TEXT', self.__lineno, value)

  def RuleGuillemetClose(self, value):
    ur'»|\>{2,}'
    if len(value) <= 2:
      return self.__MacroToken('text.guillemet.close')
    else:
      return Token('TEXT', self.__lineno, value)

  def RuleApostrophe(self, value):
    r"'"
    return self.__MacroToken('text.apostrophe')

  def RuleDoublePunctuation(self, value):
    r'[!:;?]+'
    return (
        self.__MacroToken('text.punctuation.double'),
        self.RuleLbracket('['),
        Token('TEXT', self.__lineno, value),
        self.RuleRbracket(']'))

  # Helpers

  def __MacroToken(self, macro_name):
    self.__skip_spaces = False
    return Token('MACRO', self.__lineno, macro_name)


class Parser(object):
  """
  Parses a stream of tokens into nodes.

  Fields:
    __last_lineno: (int) The line of the last successfully parsed node, if any.
  """

  tokens = Token.TYPES
  start = 'nodes'

  @staticmethod
  def p_nodes_empty(p):
    'nodes :'
    p[0] = []

  @staticmethod
  def p_nodes_append(p):
    'nodes : nodes node'
    result = p[0] = p[1]
    result.append(p[2])

  def p_node(self, p):
    """
    node : text
         | call
    """
    p[0] = p[1]

  def p_TEXT(self, p):
    'text : TEXT'
    p[0] = TextNode(self.__TokenLocation(p, 1), p[1])

  def p_call(self, p):
    'call : MACRO arguments'
    p[0] = CallNode(self.__TokenLocation(p, 1), p[1], p[2])

  @staticmethod
  def p_argments_empty(p):
    'arguments :'
    p[0] = []

  @staticmethod
  def p_argments_append(p):
    'arguments : arguments LBRACKET nodes RBRACKET'
    result = p[0] = p[1]
    result.append(p[3])

  def p_error(self, p):
    if p:
      # Location available.
      self.__context.FatalError(self.__context.Location(p.lineno),
                                "syntax error: '{token.value}'".format(token=p))
    else:
      # No location available: end of file reached.
      # Likely explanation is an unclosed '[': find the first open '[', if any.
      unclosed_lbrackets = \
          itertools.ifilter(lambda token: token.type == 'LBRACKET',
                            self.__parser.symstack)
      first_unclosed_lbracket = next(unclosed_lbrackets, None)
      if first_unclosed_lbracket:
        self.__context.FatalError(
            self.__context.Location(first_unclosed_lbracket.lineno),
            "syntax error: macro argument not closed")
      else:  # should never happen
        self.__context.FatalError(self.__context.Location(-1),
                                  "unexpected syntax error at end of file")

  def __init__(self, lexer):
    self.__context = lexer.context
    self.__lexer = lexer
    self.__parser = yacc.yacc(module=self, method='SLR')

  def Parse(self):
    """
    Parses the input file into a list of nodes.

    Return: (node list)
      The parsed nodes, None on fatal error.
    """
    lexer = self.__lexer
    nodes = self.__parser.parse(lexer=lexer)
    if self.__context.fatal_error:
      raise FatalError()
    return nodes

  def __TokenLocation(self, p, index):
    return self.__context.Location(p.lineno(index))


def ParseFile(reader, filename, logger):
  """
  Parses a file into a list of nodes.

  Args:
    filename: (Filename) The file to parse.
    logger: (Logger) The logger to use to report errors.

  Returns:
    (node list) The parsed nodes.

  Throws:
    FatalError
  """
  assert isinstance(filename, Filename)
  context = ParsingContext(filename, logger)

  # Read the file entirely.
  try:
    input_text = reader.read()
    reader.close()
  except Exception as e:
    raise context.FatalError(
        context.Location(1),
        'unable to read the input file: {filename}\n{error}'.format(
            filename=filename, error=e))

  # Parse the file contents.
  lexer = Lexer(context, input_text)
  parser = Parser(lexer)
  return parser.Parse()
