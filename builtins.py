# -*- coding: utf-8 -*-
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

from abc import ABCMeta, abstractmethod
import re
import sys

from executor import ExecutionContext, TextBranch
from log import *
from macros import *
from parsing import CallNode, TextNode, VALID_MACRO_NAME_PATTERN


# Special characters

class SpecialCharacters(object):

  TextPercent = StaticAppendTextCallback('%', public_name='text.percent')
  TextAmpersand = StaticAppendTextCallback('&', public_name='text.ampersand')
  TextUnderscore = StaticAppendTextCallback('_', public_name='text.underscore')
  TextDollar = StaticAppendTextCallback('$', public_name='text.dollar')
  TextHash = StaticAppendTextCallback('#', public_name='text.hash')
  TextNbsp = StaticAppendTextCallback(u'\xa0', public_name='text.nbsp')
  TextSoftHyphen = StaticAppendTextCallback('', public_name='text.softhyphen')
  TextDashEn = StaticAppendTextCallback(u'–', public_name='text.dash.en')
  TextDashEm = StaticAppendTextCallback(u'—', public_name='text.dash.em')
  TextEllipsis = StaticAppendTextCallback(u'…', public_name='text.ellipsis')
  TextGuillemetOpen = \
      StaticAppendTextCallback(u'«', public_name='text.guillemet.open')
  TextGuillemetClose = \
      StaticAppendTextCallback(u'»', public_name='text.guillemet.close')
  TextBacktick = StaticAppendTextCallback(u"`", public_name='text.backtick')
  TextApostrophe = StaticAppendTextCallback(u"'", public_name='text.apostrophe')
  Newline = StaticAppendTextCallback('\n', public_name='newline')

  @staticmethod
  @macro(public_name='text.punctuation.double', args_signature='contents',
         text_compatible=True)
  def TextPunctuationDouble(executor, call_node, contents):
    executor.AppendText(contents)

  @staticmethod
  @macro(public_name='-', text_compatible=True)
  def TextSoftHyphenAlias(executor, call_node):
    called_node = CallNode(call_node.location, 'text.softhyphen', [])
    executor.CallMacro(called_node)


# Core

@macro(public_name='empty', text_compatible=True)
def Empty(executor, call_node):
  pass


@macro(public_name='include', args_signature='path')
def Include(executor, call_node, path):
  """
  Includes the given file.

  Args:
    path: The path of the file, relative to the current file.
      Automatically appends the '.psc' extension to the file name if the given
      file name has no extension.
  """
  try:
    executor.ExecuteFile(path, cur_dir=call_node.location.filename.dir_path)
  except IOError, e:
    raise InternalError('unable to include "{path}": {reason}',
                       path=path, reason=e.strerror)
  except InternalError, e:
    raise InternalError('unable to include "{path}": {reason}',
                        path=path, reason=e)


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
def MacroNew(executor, call_node, signature, body):
  """
  Defines a new macro in the branch context.

  The signature has the following format:
  - with arguments: 'name(arg1,...,argN)'
  - with no arguments: 'name' or 'name()'
  Spaces between tokens are ignored.

  When invoked, the body of the macro is executed in a call context containing
  a macro for each argument, set to the value provided by the caller.
  """

  # Parse the signature.
  signature_match = __SIGNATURE_REGEX.match(signature)
  if not signature_match:
    raise InternalError('invalid signature: {signature}', signature=signature)
  macro_name = signature_match.group(1)
  macro_arg_names = signature_match.group(2)
  if macro_arg_names:
    macro_arg_names = [name.strip() for name in macro_arg_names.split(',')]
  else:
    macro_arg_names = []

  # Check that the macro arguments are unique.
  macro_arg_names_set = set(macro_arg_names)
  if len(macro_arg_names_set) != len(macro_arg_names):
    map(macro_arg_names.remove, macro_arg_names_set)
    raise InternalError('duplicate argument in signature: {argument}',
                        argument=macro_arg_names[0])

  callback = MacroNewCallback(executor.call_context, macro_arg_names, body)
  executor.current_branch.context.AddMacro(macro_name, callback)

def MacroNewCallback(macro_call_context, macro_arg_names, body):
  """
  The callback of a macro defined by MacroNew.

  Defined outside of MacroNew to avoid using the wrong variables.
  """
  @macro(args_signature=','.join(macro_arg_names), text_compatible=True,
         auto_args_parser=False)
  def MacroCallback(executor, call_node):
    executor.CheckArgumentCount(call_node, MacroCallback, len(macro_arg_names))

    # Execute the arguments in the current context.
    arg_call_context = executor.call_context

    # Execute the body in the macro definition context augmented with arguments.
    # Using the macro definition context instead of the current context allows
    # partial macro definitions such as $inner[y] below that depends on the
    # argument $x of the enclosing macro definition $outer[x]:
    # $macro.new[outer(x)][$macro.new[inner(y)][$x $y]]
    body_call_context = ExecutionContext(parent=macro_call_context)
    for macro_arg_name, arg in zip(macro_arg_names, call_node.args):
      body_call_context.AddMacro(macro_arg_name,
                                 ExecuteCallback(arg, arg_call_context))
    executor.ExecuteInCallContext(body, body_call_context)

  return MacroCallback


@macro(public_name='macro.call', args_signature='macro_name,arg1,...,argN',
       text_compatible=True, auto_args_parser=False)
def MacroCall(executor, call_node):
  """
  Calls a macro dynamically.

  Args:
    macro_name: The name of the macro to call.
    arg1..N: The arguments to pass to the macro.
  """
  executor.CheckArgumentCount(call_node, MacroCall,
                              min_args_count=1, max_args_count=-1)

  macro_name_nodes = call_node.args[0]
  macro_name = executor.EvalText(macro_name_nodes)
  if not (macro_name and macro_name_nodes):
    raise InternalError('expected non-empty macro name')

  called_node = CallNode(macro_name_nodes[0].location, macro_name,
                         call_node.args[1:])
  executor.CallMacro(called_node)


# Branches

import epub
import latex

__BRANCH_CLASSES = (
    TextBranch,
    epub.XhtmlBranch,
    latex.LatexBranch,
)
__BRANCH_TYPES = dict((branch_class.type_name, branch_class)
                      for branch_class in __BRANCH_CLASSES)

@macro(public_name='branch.write', args_signature='branch_name,*contents')
def BranchWrite(executor, call_node, branch_name, contents):
  """
  Writes contents into the given branch.
  """
  branch = __ParseBranchName(executor, branch_name)

  old_branch = executor.current_branch
  executor.current_branch = branch
  try:
    executor.ExecuteNodes(contents)
  finally:
    executor.current_branch = old_branch


@macro(public_name='branch.create.root',
       args_signature='branch_type,name_or_ref,filename')
def BranchCreateRoot(executor, call_node, branch_type, name_or_ref, filename):
  """
  Creates a new root branch.

  The new branch starts with a context containing only the builtin macros.

  Args:
    branch_type: The name of the type of branch to create, see __BRANCH_TYPES.
    name_or_ref: The name of the branch to create, or, if prefixed with '!', the
      name of the macro to store the automatically generated branch name into.
    filename: The name of the file to save the branch to, relative to the output
      directory.
  """

  # Parse the branch type.
  branch_class = __BRANCH_TYPES.get(branch_type)
  if not branch_class:
    raise InternalError(
        'unknown branch type: {branch_type}; expected one of: {known}',
        branch_type=branch_type, known=', '.join(sorted(__BRANCH_TYPES)))

  # Create the branch.
  __CreateBranch(
      executor, call_node, name_or_ref,
      lambda: branch_class(parent=None,
                           parent_context=executor.current_branch.context,
                           writer=executor.GetOutputWriter(filename)))


@macro(public_name='branch.create.sub', args_signature='name_or_ref')
def BranchCreateSub(executor, call_node, name_or_ref):
  """
  Creates a new sub-branch in the current branch.

  Does not insert it yet.

  Args:
    name_or_ref: The name of the branch to create, or, if prefixed with '!', the
      name of the macro to store the automatically generated branch name into.
  """
  __CreateBranch(executor, call_node, name_or_ref,
                 executor.current_branch.CreateSubBranch)


@macro(public_name='branch.append', args_signature='branch_name')
def BranchAppend(executor, call_node, branch_name):
  """
  Appends a previously created sub-branch to the current branch.

  The sub-branch must have been created by the current branch.
  A sub-branch can be appended only once.

  Args:
    branch_name: The name of the branch to insert.
  """
  current_branch = executor.current_branch
  sub_branch = __ParseBranchName(executor, branch_name)
  executor.current_branch.AppendSubBranch(sub_branch)


def __ParseBranchName(executor, branch_name):
  """
  Parses a branch name.

  Args:
    name: (string) The name of the branch to parse.

  Returns:
    (Branch) The branch having the given name.
  """
  branch = executor.branches.get(branch_name)
  if not branch:
    raise InternalError('branch not found: {branch_name}',
                        branch_name=branch_name)
  return branch


def __CreateBranch(executor, call_node, name_or_ref, branch_factory):
  """
  Creates a new root branch or sub-branch.

  Args:
    call_node: (CallNode) The branch creation macro being executed.
      Given to the created branch name macro, if any,
    name_or_ref: (string) The name of the branch to create, or, if prefixed
      with '!', the name of the macro to store the automatically generated
      branch name into.
    branch_factory: (() -> Branch function) The function to call to create
      the branch. The factory should not name or register the branch.
  """
  is_reference = name_or_ref.startswith('!')

  branch = branch_factory()
  if not is_reference:
    if name_or_ref in executor.branches:
      raise InternalError('a branch of this name already exists: {name}',
                          name=name_or_ref)
    branch.name = name_or_ref

  executor.RegisterBranch(branch)

  if is_reference:
    executor.current_branch.context.AddMacro(
        name_or_ref[1:],
        ExecuteCallback([TextNode(call_node.location, branch.name)]))


# Text operations

@macro(public_name='case.lower', args_signature='text', text_compatible=True)
def CaseLower(executor, call_node, text):
  """Converts text to lowercase."""
  executor.AppendText(text.lower())


@macro(public_name='case.upper', args_signature='text', text_compatible=True)
def CaseUpper(executor, call_node, text):
  """Converts text to uppercase."""
  executor.AppendText(text.upper())


def ArabicToRoman(number):
  """
  Converts an Arabic number to Roman.

  Args:
    roman: (int) The integer number to convert.

  Returns:
    (string) Its Roman equivalent.

  Raises:
    InternalError if the number cannot be converted.
  """
  if not 0 < number < 4000:
    raise InternalError('unsupported number for conversion to Roman: {number}',
                        number=number)

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
def Roman(executor, call_node, number):
  """
  Prints the Roman representation of an Arabic number.
  """

  # Parse the Arabic number. Reject invalid values.
  try:
    arabic_value = int(number)
  except ValueError:
    raise InternalError('invalid Arabic number: {number}', number=number)

  # Convert the Arabic number to Roman.
  executor.AppendText(ArabicToRoman(arabic_value))


# Conditions

@macro(public_name='if.def',
       args_signature='macro_name,*then_block,*else_block?',
       text_compatible=True)
def IfDef(executor, call_node, macro_name, then_block, else_block):
  if executor.LookupMacro(macro_name, text_compatible=False):
    executor.ExecuteNodes(then_block)
  elif else_block:
    executor.ExecuteNodes(else_block)

@macro(public_name='if.eq', args_signature='a,b,*then_block,*else_block?',
       text_compatible=True)
def IfEq(executor, call_node, a, b, then_block, else_block):
  if a == b:
    executor.ExecuteNodes(then_block)
  elif else_block:
    executor.ExecuteNodes(else_block)


# Counters

@macro(public_name='counter.create', args_signature='counter_name')
def CounterCreate(executor, call_node, counter_name):
  """
  Creates a new counter initially set to zero.

  Creates the following macros to manipulate the counter:
      $<counter-name> (Arabic value)
      $<counter-name>.if.positive[ifpositive]
      $<counter-name>.set[value]
      $<counter-name>.incr
  """
  value_holder = [0]

  @macro(text_compatible=True)
  def ValueCallback(executor, call_node):
    """Writes the value of the counter as an arabic number."""
    executor.AppendText(str(value_holder[0]))

  @macro(args_signature='*contents', text_compatible=True)
  def IfPositiveCallback(executor, call_node, contents):
    """Executes the contents if the counter is strictly positive (1 or more)."""
    if value_holder[0] > 0:
      executor.ExecuteNodes(contents)

  @macro(args_signature='value')
  def SetCallback(executor, call_node, value):
    """Sets the value of a counter to the given integer."""
    try:
      value_holder[0] = int(value)
    except ValueError:
      raise InternalError('invalid integer value: {value}', value=value)

  @macro()
  def IncrCallback(executor, call_node):
    """Increments the counter."""
    value_holder[0] += 1

  macros = {
      '': ValueCallback,
      '.if.positive': IfPositiveCallback,
      '.set': SetCallback,
      '.incr': IncrCallback,
  }
  for name_suffix, callback in macros.iteritems():
    macro_name = '{counter_name}{suffix}'.format(counter_name=counter_name,
                                                  suffix=name_suffix)
    executor.current_branch.context.AddMacro(macro_name, callback)
