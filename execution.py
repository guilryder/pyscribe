# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

import io
import os
import pathlib
import sys

from branches import TextBranch
from log import Filename, FormatMessage, NodeError
from macros import *
from parsing import ParseFile


ENCODING = 'utf-8'
PYSCRIBE_EXT = '.psc'

MAX_NESTED_CALLS = 100
MAX_NESTED_INCLUDES = 25


class ExecutionContext:
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
    assert hasattr(callback, 'args_signature'), (
        'args_signature missing for ' + name)
    self.macros[name] = callback

  def AddMacros(self, macros):
    """
    Adds some macros to this context.

    Args:
      macros: (string -> callable dict) The macros to add.
    """
    for name, callback in macros.items():
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
    # Walk the stack of contexts. A cache does not improve peformance much
    # because most macros are found near the top of the stack:
    # 50% in top context, 20% in second context.
    context = self
    while context:
      callback = context.macros.get(name)
      if callback and (not text_compatible or callback.text_compatible):
        return callback
      context = context.parent
    return None


class AbstractFileSystem:  # pylint: disable=no-member

  @classmethod
  def MakeAbsolute(cls, cur_dir, path):
    """
    Makes a path absolute and normalized.

    Args:
      cur_dir: (cls.Path) The path to the current directory, used if the path is
        relative.
      path: (cls.Path) The path to make absolute.
    """
    return cls.Path(os.path.normpath(cur_dir / path))


class FileSystem(AbstractFileSystem):
  stdout = sys.stdout
  stderr = sys.stderr
  Path = pathlib.PurePath
  basename = staticmethod(os.path.basename)
  getcwd = staticmethod(pathlib.Path.cwd)
  lexists = staticmethod(os.path.lexists)
  makedirs = staticmethod(os.makedirs)
  open = staticmethod(io.open)
  relpath = staticmethod(os.path.relpath)


class Executor:
  """
  Executes input files.

  At any time, the effective execution context is the concatenation of:
  1) the call context: self.context
  2) the branch context: self.current_branch.context

  Fields:
    logger: (Logger) The logger used to print all error messages.
    fs: (FileSystem) The file system abstraction.
    __current_dir: (fs.Path) The absolute path of the current directory.
    __output_path_prefix: (fs.Path) The absolute path prefix of all output
      files; treated as a string prefix, not necessarily a directory.
    opened_paths: (fs.Path set) The absolute paths of the readers and writers
      opened so far.
    system_branch: (Branch) The first branch of the executor, of type text.
    root_branches: (Branch list) All root branches, including the system branch.
    current_branch: (Branch) The currently selected branch.
    call_context: (ExecutionContext) The top of the execution contexts stack.
    __current_text_writer: (None|writer) The writer to send text-only output to.
      If set, the executor is in text-only mode: executing text-incompatible
      macros fails. If None, the executor is in normal mode.
    __call_stack: ((CallNode, callback) list) The current macro call stack,
      pre-allocated to MAX_NESTED_CALLS frames.
    __call_stack_size: (int) The number of frames in __call_stack.
    __include_stack: (Filename list) The stack of included file names.
  """

  def __init__(self, *, logger, fs=FileSystem(),
               current_dir, output_path_prefix):
    assert current_dir.is_absolute()
    assert output_path_prefix.is_absolute(), str(output_path_prefix)
    self.logger = logger
    self.fs = fs
    self.__current_dir = current_dir
    self.__output_path_prefix = output_path_prefix
    self.opened_paths = set()
    self.system_branch = TextBranch(parent=None, name='system')
    self.branches = {}
    self.root_branches = []
    self.current_branch = self.system_branch
    self.call_context = ExecutionContext(parent=None)
    self.__current_text_writer = None
    self.__call_stack = [None] * MAX_NESTED_CALLS
    self.__call_stack_size = 0
    self.__include_stack = []
    self.RegisterBranch(self.system_branch)
    for macros_container in GetPublicMacrosContainers():
      self.system_branch.context.AddMacros(GetPublicMacros(macros_container))

  def AddConstants(self, constants):
    """
    Adds constant macros to the system branch.

    Args:
      constants: ((name, value) dict) The constants to add; values are strings.
    """
    context = self.system_branch.context
    for name, value in constants.items():
      context.AddMacro(name, AppendTextCallback(value))

  def GetOutputWriter(self, filename_suffix):
    """
    Creates a writer for the given output file.

    Args:
      filename_suffix: The path suffix of the file to write, relative to
        __output_path_prefix. Must be empty, or start with a dot and contain no
        directory separator.

    Throws:
      NodeError
    """
    fs = self.fs

    # Compute and validate the absolute path.
    if filename_suffix:
      if not filename_suffix.startswith('.'):
        raise NodeError("invalid output file name suffix: '{suffix}'; "
                        "must be empty or start with a period",
                        suffix=filename_suffix)
      if filename_suffix != fs.basename(filename_suffix):
        raise NodeError(f"invalid output file name suffix: '{filename_suffix}';"
                         " must be a basename (no directory separator)")
    path = fs.Path(str(self.__output_path_prefix) + filename_suffix)
    if path in self.opened_paths:
      raise NodeError("output file already opened: {filename}", filename=path)
    self.logger.LogInfo(f'Writing: {path}')

    # Create the writer.
    try:
      writer = fs.open(path, mode='wt', encoding=ENCODING, newline=None)
    except OSError as e:
      raise NodeError('unable to write to file: {path}\n{cause}',
                      path=path, cause=e) from e
    self.opened_paths.add(path)
    return writer

  def ResolveFilePath(self, path, directory, default_ext=None):
    """
    Normalizes a user-entered, possibly relative file path.

    Args:
        path: (fs.Path) The path to resolve.
        directory: (string|fs.Path) The path of the directory to resolve path
          against if it is relative. Can be relative to current_dir.
        default_ext: (string|None) The extension to append to the path if it has
          none and it refers to a non-existing file.
    Returns: (Path)
      The resolved path, always absolute.
    """
    return self.ResolveFilePathStatic(
        path,
        abs_directory=self.__current_dir / directory,
        default_ext=default_ext,
        fs=self.fs)

  @staticmethod
  def ResolveFilePathStatic(path, *, abs_directory, default_ext=None, fs):
    """
    Normalizes a user-entered, possibly relative file path.

    Args:
        path: (fs.Path) The path to resolve.
        abs_directory: (fs.Path|None) The absolute path of the directory to
          resolve path against if it is relative.
        default_ext: (string|None) The extension to append to the path if it has
          none and it refers to a non-existing file.
    Returns: (fs.Path)
      The resolved path, always absolute.
    """
    assert abs_directory.is_absolute()
    path = fs.MakeAbsolute(abs_directory, path)
    if default_ext is not None and not path.suffix and not fs.lexists(path):
      path = path.with_suffix(default_ext)
    return path

  def ExecuteFile(self, path):
    """
    Executes the given PyScribe file.

    Args:
      path: (Path) The absolute path of the file to execute.

    Throws:
      FatalError on file execution error
      NodeError if too many nested includes
      OSError if unable to open the file
    """
    assert path.is_absolute()
    self.opened_paths.add(path)
    filename = Filename(path, path.parent)
    with self.fs.open(path, encoding=ENCODING) as reader:
      if len(self.__include_stack) >= MAX_NESTED_INCLUDES:
        raise NodeError('too many nested includes')

      self.__include_stack.append(filename)
      try:
        nodes = ParseFile(reader, filename, logger=self.logger)
        self.ExecuteNodes(nodes)
      finally:
        self.__include_stack.pop()

  def RenderBranches(self):
    """Renders all root branches with an output file.

    Do not close the writers: tests need to be able to call StringIO.getvalue(),
    and production closes the files automatically.

    Throws:
      FatalError
      NodeError
      OSError on output file write error
    """
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
        node.Execute(self)
      except NodeError as e:
        raise self.FatalError(node.location, e) from e

  def ExecuteInCallContext(self, nodes, call_context):
    """
    Executes the given nodes in the given call context.

    Args:
      nodes: (node list) The nodes to execute.
      call_context: (ExecutionContext|None)
        The call context to execute the nodes in, None for current.
    """
    if call_context is None:
      self.ExecuteNodes(nodes)
    else:
      old_call_context = self.call_context
      self.call_context = call_context
      try:
        self.ExecuteNodes(nodes)
      finally:
        self.call_context = old_call_context

  def ExecuteInBranchContext(self, nodes, branch_context):
    """
    Executes the given nodes in the given branch context.

    Args:
      nodes: (node list) The nodes to execute.
      call_context: (ExecutionContext)
        The branch context to execute the nodes in.
    """
    old_branch_context = self.current_branch.context
    self.current_branch.context = branch_context
    try:
      self.ExecuteNodes(nodes)
    finally:
      self.current_branch.context = old_branch_context

  def AppendText(self, text):
    """Appends a block of text to the current branch."""
    text_writer = self.__current_text_writer
    if text_writer is None:
      self.current_branch.AppendText(text)
    else:
      text_writer.write(text)

  def RegisterBranch(self, branch):
    """
    Registers a branch and its sub-branches. Gives them a name if necessary.

    Args:
      branch: (Branch) The branch to register.
    """
    for sub_branch in branch.IterBranches():
      if sub_branch.name is None:
        sub_branch.name = f'auto{len(self.branches)}'
      self.branches[sub_branch.name] = sub_branch
      if sub_branch.parent is None:
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
    with io.StringIO() as text_writer:
      old_text_writer = self.__current_text_writer
      self.__current_text_writer = text_writer
      try:
        self.ExecuteNodes(nodes)
      finally:
        self.__current_text_writer = old_text_writer
      return text_writer.getvalue()

  def FatalError(self, location, message, call_frame_skip=0, **kwargs):
    """Logs and raises a fatal error."""
    call_stack = self.__call_stack[
        :max(0, self.__call_stack_size - call_frame_skip)]
    call_stack = [call_node for call_node, callback in reversed(call_stack)]
    return self.logger.LocationError(location, message, call_stack, **kwargs)

  def MacroFatalError(self, call_node, message, **kwargs):
    """Logs and raises a macro fatal error."""
    return self.FatalError(call_node.location, '${call_node.name}: {details}',
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
      if callback is not None:
        return callback
    return None

  def CallMacro(self, call_node):
    """
    Invokes a macro.

    Args:
      call_node: (CallNode) The macro call description.
    """
    text_compatible = (self.__current_text_writer is not None)
    callback = self.LookupMacro(call_node.name, text_compatible=text_compatible)
    if callback is None:
      # Macro not found
      if text_compatible:
        # Show a specific error message if the macro is not found
        # because text-incompatible.
        callback = self.LookupMacro(call_node.name, text_compatible=False)
        if callback is not None:
          raise self.MacroFatalError(call_node, 'text-incompatible macro call',
                                     call_frame_skip=0)
      raise self.FatalError(call_node.location,
                            'macro not found: ${call_node.name}',
                            call_node=call_node)

    # Store the new call stack frame. Enforce the call stack size limit.
    call_stack_size_orig = self.__call_stack_size
    try:
      self.__call_stack[call_stack_size_orig] = (call_node, callback)
      self.__call_stack_size = call_stack_size_orig + 1
    except IndexError as e:
      raise self.MacroFatalError(call_node, 'too many nested macro calls',
                                 call_frame_skip=0) from e

    # Execute the macro.
    try:
      callback(self, call_node)
    except NodeError as e:
      raise self.MacroFatalError(call_node, e) from e
    finally:
      # Pop the call stack frame.
      self.__call_stack_size = call_stack_size_orig

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
    raise self.FatalError(
        call_node.location,
        '{signature}: arguments count mismatch: ' +
            'expected ' + expected_message + ', got {actual}',
         call_frame_skip=1,
         signature=GetMacroSignature(call_node.name, macro_callback),
         min_args_count=min_args_count, max_args_count=max_args_count,
         actual=actual_args_count)
