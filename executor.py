#!/usr/bin/env python
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

from abc import ABCMeta, abstractmethod
import io
import os
import sys
from StringIO import StringIO

from log import *
from macros import *
from parsing import CallNode, TextNode, ParseFile


ENCODING = 'utf8'

MAX_NESTED_CALLS = 25
MAX_NESTED_INCLUDES = 25


class ExecutionContext(object):
  """
  Entry of an execution context stack.

  Each node inherits the symbols of its ancestors.

  Fields:
    parent: (ExecutionContext) The parent of the context, if any.
    macros: (string -> callable dict) The symbols of this context.
      Symbols of the parent entries are not duplicated in this dictionary.
      Each macro symbol has a name and a callback. See AddMacro for details.
  """

  def __init__(self, parent=None):
    """
    Args:
      parent: (ExecutionContext) The parent of the context to create, or None.
    """
    self.parent = parent
    self.macros = {}

  def AddMacro(self, name, callback):
    """
    Adds a macro to this context.

    The macro callback is a Python callable with the following signature:
    callable(executor, call_node)

    where:
      executor: (Executor) The executor to run the macro against.
      location: (Location) The location of the caller of the macro.
      args: (node list list) The arguments passed to the macro.

    The callable has 'args_signature' attribute containing the signature
    of the macro arguments as a string: '' if the macro has no arguments,
    else 'name1,name2,...,nameN'.

    Args:
      name: (string) The name of the symbol, without '$' prefix.
      callback: (runnable) The macro callback.
    """
    assert hasattr(callback, 'args_signature'), \
        'args_signature missing for ' + name
    self.macros[name] = callback

  def AddMacros(self, macros):
    """
    Adds some macros to this context.

    Args:
      macros: (string -> callable dict) The macros to add.
    """
    for name, callback in macros.iteritems():
      self.AddMacro(name, callback)

  def LookupMacro(self, name, text_compatible):
    """
    Finds the macro with the given name in this context.

    If several macros have the same name, gives the priority to the macro
    defined in the deeper call stack entry.

    If the macro must be text-compatible, skips text-incompatible matches.

    Args:
      name: (string) The name of the macro to find.
      text_compatible: (bool) Whether the macro must be text-compatible.

    Returns:
      (callable) The macro callback, None if no macro has been found.
    """
    context = self
    while context:
      callback = context.macros.get(name)
      if callback and (not text_compatible or callback.text_compatible):
        return callback
      context = context.parent
    return None


class Branch(object):
  """
  Output branch: append-only stream of text nodes and sub-branches.

  Details of sub-branches is an implementation detail of the root branch.
  No method other than the ones declared below can be called on them.

  Fields:
    type_name: (string) The name of the type of the branch,
      as returned by $branch.type.
    parent: (Branch) The parent of this branch, None if the branch is root.
    root: (Branch) The root ancestor of this branch, self if the branch is root.
    context: (ExecutionContext) The execution context of the branch.
    name: (string) The name of the branch.
    sub_branches: (Branch list) The direct sub-branches of this branch.
    attached: (bool) Whether the branch has been inserted in its parent branch;
      always true for root branches.
    writer: (stream) The output writer of the branch (root branch only).
      Must have a write() method.
  """

  __metaclass__ = ABCMeta

  def __init__(self, parent, parent_context=None, name=None, writer=None):
    """
    Args:
      parent: (branch) The parent branch, None for top-level branches.
      parent_context: (ExecutionContext) The parent of the execution context
        of the branch. Defaults to parent.context if parent is set.
      name: (string) The name of the branch; optional.
    """
    if parent and not parent_context:
      parent_context = parent.context
    self.parent = parent
    self.root = parent and parent.root or self
    self.context = ExecutionContext(parent=parent_context)
    self.name = name
    self.sub_branches = []
    self.attached = not parent

    self.context.AddMacro('branch.type', AppendTextCallback(self.type_name))

    if parent:
      parent.sub_branches.append(self)
      assert not writer, 'Child branches cannot have writers'
    else:
      self.writer = writer

  def __repr__(self):
    return '<%s: %s>' % (self.__class__.__name__, self.name)

  @abstractmethod
  def AppendText(self, text):  # pragma: no cover
    """Appends a block of text to the branch."""
    pass

  @abstractmethod
  def CreateSubBranch(self):  # pragma: no cover
    """
    Creates a new sub-branch for this branch.

    Does not insert the sub-branch into this branch.

    Returns:
      (Branch) The new sub-branch, unattached.
    """
    pass

  def AppendSubBranch(self, sub_branch):
    """
    Appends an existing sub-branch to this branch.

    Checks that the sub-branch is valid.

    Args:
      sub_branch: (Branch) The sub-branch to insert.

    Raises:
      InternalError if the sub-branch is already attached or has not been
        created by this branch.
    """
    if sub_branch.parent != self:
      raise InternalError(
          "expected a sub-branch created by branch '{self_branch.name}'; " +
          "got one created by branch '{sub_branch.parent.name}'",
          self_branch=self, sub_branch=sub_branch)

    if sub_branch.attached:
      raise InternalError(
          "the sub-branch '{sub_branch.name}' is already attached",
          sub_branch=sub_branch)

    self._AppendSubBranch(sub_branch)
    sub_branch.attached = True

  @abstractmethod
  def _AppendSubBranch(self, sub_branch):  # pragma: no cover
    """
    Appends an existing sub-branch to this branch.

    Does not need to check that the sub-branch is valid.

    Args:
      sub_branch: (Branch) The sub-branch to insert.
    """
    pass

  def IterBranches(self):
    """
    Iterates over the branch and all its sub-branches.

    Yields:
      (Branch) A branch.
    """
    yield self
    for sub_branch in self.sub_branches:
      for sub_sub_branch in sub_branch.IterBranches():
        yield sub_sub_branch

  def Render(self):
    """
    Renders this branch and its sub-branches recursively.

    Can be called on root branches only.
    """
    writer = self.writer
    if writer:
      self._Render(writer)
      writer.flush()

  @abstractmethod
  def _Render(self, writer):  # pragma: no cover
    """
    Renders the branch and its sub-branches recursively.

    Args:
      write: (stream) The stream to render the output text to.
        Must have a write() method.
    """
    pass


class TextBranch(Branch):
  """
  Branch for plain-text.

  Fields:
    text_hook: (string -> string function) The hook applied to all text passed
      to AppendText(); defaults to the identity function (no transformation).
    __outputs: (string|Branch list) The text nodes and sub-branches of branch.
    __text_accu: (StringIO) The current text accumulator of the branch.
      Used to merge consecutive text nodes created by AppendText.
  """

  type_name = 'text'

  def __init__(self, *args, **kwargs):
    super(TextBranch, self).__init__(*args, **kwargs)
    self.text_hook = lambda text: text
    self.__outputs = []
    self.__text_accu = StringIO()
    # TODO: consider using cStringIO + codecs.getwriter(ENCODING)(buffer)

  def AppendText(self, text):
    text = self.text_hook(text)
    self.__text_accu.write(text)

  def __FlushText(self):
    """Flushes the text accumulator to the branch."""
    text = self.__text_accu.getvalue()
    if text:
      self.__outputs.append(text)
      self.__text_accu.truncate(0)

  def CreateSubBranch(self):
    return TextBranch(parent=self)

  def _AppendSubBranch(self, sub_branch):
    self.__FlushText()
    self.__outputs.append(sub_branch)

  def _Render(self, writer):
    self.__FlushText()
    for output in self.__outputs:
      if isinstance(output, basestring):
        writer.write(unicode(output))
      else:
        output._Render(writer)


class FileSystem(object):
  dirname = staticmethod(os.path.dirname)
  getcwd = staticmethod(os.getcwd)
  join = staticmethod(os.path.join)
  normpath = staticmethod(os.path.normpath)
  open = staticmethod(io.open)


class Executor(object):
  """
  Executes input files.

  At any time, the effective execution context is the concatenation of:
  1) the call context: self.context
  2) the branch context: self.current_branch.context

  Fields:
    __output_dir: (string) The parent directory of all output files
    __logger: (Logger) The logger used to print all error messages.
    fs: (FileSystem) The file system abstraction.
    system_branch: (Branch) The first branch of the executor, of type text.
    root_branches: (Branch list) All root branches, including the system branch.
    current_branch: (Branch) The currently selected branch.
    call_context: (ExecutionContext) The top of the execution contexts stack.
    __current_text_writer: (None|writer) The writer to send text-only output to.
      If set, the executor is in text-only mode: executing text-incompatible
      macros fails. If None, the executor is in normal mode.
    __call_stack: ((CallNode, callback) list) The current macro call stack.
    __include_stack: (Filename list) The stack of included file names.
  """

  def __init__(self, output_dir, logger, fs=FileSystem()):
    self.__output_dir = fs.normpath(output_dir)
    self.__logger = logger
    self.fs = fs
    self.system_branch = TextBranch(parent=None, name='system')
    self.branches = {}
    self.root_branches = []
    self.current_branch = self.system_branch
    self.call_context = ExecutionContext(parent=None)
    self.__current_text_writer = None
    self.__call_stack = []
    self.__include_stack = []
    self.RegisterBranch(self.system_branch)

    import builtins
    for macros_container in (builtins, builtins.SpecialCharacters):
      self.system_branch.context.AddMacros(GetPublicMacros(macros_container))

  def AddConstants(self, constants):
    """
    Adds constant macros to the system branch.

    Args:
      constants: ((name, value) dict) The constants to add; values are strings.
    """
    context = self.system_branch.context
    for name, value in constants.iteritems():
      context.AddMacro(name, AppendTextCallback(value))

  def GetOutputWriter(self, filename):
    """
    Creates a writer for the given output file.

    Args:
      filename: (string) The name of the output file, relative to the output
        directory. Cannot be absolute.
    """
    fs = self.fs
    abs_filename = fs.normpath(fs.join(self.__output_dir, filename))
    if not abs_filename.startswith(fs.join(self.__output_dir, '')):
      raise InternalError("invalid output file name: '{filename}'; " +
                          "must be below the output directory",
                          filename=filename)
    return fs.open(abs_filename, mode='wt', encoding=ENCODING, newline=None)

  def ExecuteFile(self, path, cur_dir):
    """
    Executes the given input file.

    Args:
      path: (string) The path of the file to execute.
      cur_dir: (string|None) The full path of the current directory.
        Used if filename is relative.
    """
    fs = self.fs
    path = fs.normpath(fs.join(cur_dir, path))
    filename = Filename(path, fs.dirname(path))
    reader = fs.open(path, encoding=ENCODING)

    if len(self.__include_stack) >= MAX_NESTED_INCLUDES:
      raise InternalError('too many nested includes')

    self.__include_stack.append(filename)
    try:
      nodes = ParseFile(reader, filename, logger=self.__logger)
      self.ExecuteNodes(nodes)
    finally:
      self.__include_stack.pop()

  def RenderBranches(self):
    """Renders all root branches with an output file."""
    for branch in self.root_branches:
      branch.Render()

  def ExecuteNodes(self, nodes):
    """
    Executes the given nodes in the current call context.

    Args:
      nodes: (node list) The nodes to execute.

    Throws:
      FatalError
    """
    for node in nodes:
      try:
        if isinstance(node, TextNode):
          self.AppendText(node.text)
        else:
          self.CallMacro(node)
      except InternalError, e:
        self.FatalError(node.location, e)

  def ExecuteInCallContext(self, nodes, call_context):
    """
    Executes the given nodes in the given call context.

    Args:
      nodes: (node list) The nodes to execute.
      call_context: (ExecutionContext|None)
        The call context to execute the nodes in, None for current.
    """
    if call_context:
      old_call_context = self.call_context
      self.call_context = call_context
      try:
        self.ExecuteNodes(nodes)
      finally:
        self.call_context = old_call_context
    else:
      self.ExecuteNodes(nodes)

  def AppendText(self, text):
    """Appends a block of text to the current branch."""
    text_writer = self.__current_text_writer
    if text_writer:
      text_writer.write(text)
    else:
      self.current_branch.AppendText(text)

  def RegisterBranch(self, branch):
    """
    Registers a branch and its sub-branches. Gives them a name if necessary.

    Args:
      branch: (Branch) The branch to register.
    """
    for sub_branch in branch.IterBranches():
      if not sub_branch.name:
        sub_branch.name = 'auto{index}'.format(index=len(self.branches))
      self.branches[sub_branch.name] = sub_branch
      if not sub_branch.parent:
        self.root_branches.append(sub_branch)

  def EvalText(self, nodes):
    """
    Evaluates the given nodes into text.

    Does not add the text to the current branch.
    Fails if text-incompatible macros are executed.

    Args:
      nodes: (node list) The text nodes to evaluate.

    Returns:
      (string) The nodes execution result.

    Throws:
      FatalError
    """
    text_writer = StringIO()
    old_text_writer = self.__current_text_writer
    self.__current_text_writer = text_writer
    try:
      self.ExecuteNodes(nodes)
    finally:
      self.__current_text_writer = old_text_writer
    return text_writer.getvalue()

  def FatalError(self, location, message, call_frame_skip=0, **kwargs):
    """Logs and raises a fatal error."""
    call_stack = self.__call_stack
    if call_frame_skip > 0:
      call_stack = call_stack[:-call_frame_skip]
    call_stack = [call_node for call_node, callback in reversed(call_stack)]
    raise self.__logger.Log(location, message, call_stack, **kwargs)

  def MacroFatalError(self, call_node, message, **kwargs):
    """Logs and raises a macro fatal error."""
    self.FatalError(call_node.location, '${call_node.name}: {details}',
                    call_node=call_node,
                    call_frame_skip=kwargs.get('call_frame_skip', 1),
                    details=FormatMessage(message, **kwargs))

  def LookupMacro(self, name, text_compatible):
    """
    Finds the macro with the given name in the active contexts.

    Looks for the macro:
    1) in the call context
    2) in the context of the current branch.

    Args:
      name: (string) The name of the macro to retrieve.
      text_compatible: (bool) Whether the macro must be text-compatible.

    Returns:
      (callable) The macro callback, None if no macro has been found.
    """
    for context in (self.call_context, self.current_branch.context):
      callback = context.LookupMacro(name, text_compatible)
      if callback:
        return callback
    return None

  def CallMacro(self, call_node):
    """
    Invokes a macro.

    Args:
      call_node: (CallNode) The macro call description.
    """
    text_compatible = bool(self.__current_text_writer)
    callback = self.LookupMacro(call_node.name, text_compatible=text_compatible)
    if not callback:
      # Macro not found
      if text_compatible:
        # Show a specific error message if the macro is not found
        # because text-incompatible.
        callback = self.LookupMacro(call_node.name, text_compatible=False)
        if callback:
          self.MacroFatalError(call_node, 'text-incompatible macro call',
                               call_frame_skip=0)
      self.FatalError(call_node.location, 'macro not found: ${call_node.name}',
                      call_node=call_node)

    if len(self.__call_stack) >= MAX_NESTED_CALLS:
      self.MacroFatalError(call_node, 'too many nested macro calls',
                           call_frame_skip=0)

    self.__call_stack.append((call_node, callback))
    try:
      callback(self, call_node)
    except InternalError, e:
      self.MacroFatalError(call_node, e)
    finally:
      self.__call_stack.pop()

  def CheckArgumentCount(self, call_node, macro_callback,
                         min_args_count, max_args_count=None):
    """
    Raises an exception if a macro call has an invalid number of arguments.

    Args:
      call_node: (CallNode) The macro call.
      macro_callback: (callback) The callback of the macro called.
      min_args_count: (int) The minimum number of arguments of the macro.
      max_args_count: (int|None) The maximum number of arguments of the macro,
        same as min_args_count if None, unlimited if < 0.

    Raises:
      FatalError if len(call_node.args) != expected_args_count
    """

    # Ensure max_args_count is set.
    if max_args_count is None:
      max_args_count = min_args_count

    # Check the number of arguments against the range.
    actual_args_count = len(call_node.args)
    ok = min_args_count <= actual_args_count
    if max_args_count >= 0:
      ok &= actual_args_count <= max_args_count
    if ok:
      return

    # Raise the error message.
    expected_message = ''
    if max_args_count < 0:
      expected_message += 'at least '
    expected_message += '{min_args_count}'
    if min_args_count < max_args_count:
      expected_message += '..{max_args_count}'
    self.FatalError(
        call_node.location,
        '{signature}: arguments count mismatch: ' +
            'expected ' + expected_message + ', got {actual}',
         call_frame_skip=1,
         signature=GetMacroSignature(call_node.name, macro_callback),
         min_args_count=min_args_count, max_args_count=max_args_count,
         actual=actual_args_count)
