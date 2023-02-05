# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

from __future__ import annotations

__author__ = 'Guillaume Ryder'

import io
import os
from os import PathLike
import pathlib
from pathlib import PurePath
import sys
from typing import Any, Mapping, Optional, TextIO, Union

from branches import Branch, TextBranch
from log import FatalError as FatalErrorT, Filename, FormatMessage, Location, \
  Logger, MessageT, NodeError
from macros import AppendTextCallback, GetMacroSignature, GetPublicMacros, \
  GetPublicMacrosContainers, MacrosT, StandardMacroT
from parsing import CallNode, ParseFile, NodesT


ENCODING = 'utf-8'
PYSCRIBE_EXT = '.psc'

MAX_NESTED_CALLS = 100
MAX_NESTED_INCLUDES = 25


class ExecutionContext:
  """Entry of an execution context stack.

  Each node inherits the symbols of its ancestors.
  """

  parent: Optional[ExecutionContext]

  # The symbols of this context.
  # Symbols of the parent entries are not duplicated in this dictionary.
  # Each macro symbol has a name and a callback. See AddMacro for details.
  macros: MacrosT

  def __init__(self, parent: Optional[ExecutionContext]=None):
    self.parent = parent
    self.macros = {}

  def AddMacro(self, name: str, callback: StandardMacroT) -> None:
    """Adds a macro to this context.

    Args:
      name: The name of the symbol, without '$' prefix.
      callback: The macro callback.
    """
    assert hasattr(callback, 'args_signature'), (
        f'args_signature missing for {name}')
    self.macros[name] = callback

  def AddMacros(self, macros: MacrosT) -> None:
    """Adds some macros to this context.

    Args:
      macros: The macros to add.
    """
    for name, callback in macros.items():
      self.AddMacro(name, callback)

  def LookupMacro(self, name: str, text_compatible: bool) -> (
      Optional[StandardMacroT]):
    """Finds the macro with the given name in this context.

    If several macros have the same name, gives the priority to the macro
    defined in the deeper call stack entry.

    If the macro must be text-compatible, skips text-incompatible matches.

    Args:
      name: The name of the macro to find.
      text_compatible: Whether the macro must be text-compatible.

    Returns:
      The macro callback, None if no macro has been found.
    """
    # Walk the stack of contexts. A cache does not improve peformance much
    # because most macros are found near the top of the stack:
    # 50% in top context, 20% in second context.
    context: Optional[ExecutionContext] = self
    while context:
      callback = context.macros.get(name)
      if callback and (not text_compatible or callback.text_compatible):
        return callback
      context = context.parent
    return None


PathLikeT = Union[str, PathLike[str]]

class FileSystem:
  stdout = sys.stdout
  stderr = sys.stderr
  Path = PurePath

  @classmethod
  def basename(cls, path: PathLikeT) -> str:
    return os.path.basename(path)

  def getcwd(self) -> PurePath:
    return pathlib.Path.cwd()

  @staticmethod
  def lexists(path: PathLikeT) -> bool:
    return os.path.lexists(path)

  def makedirs(self, path: PathLikeT, exist_ok: bool=False) -> None:
    return os.makedirs(path, exist_ok=exist_ok)

  @staticmethod
  def open(file: PathLikeT, *, mode: str) -> TextIO:
    return io.open(
        file, mode=mode, encoding=ENCODING)  # type: ignore[return-value]

  @classmethod
  def relpath(cls, path: PathLikeT, start: PathLikeT) -> str:
    return os.path.relpath(path, start)

  @classmethod
  def MakeAbsolute(cls, cur_dir: PurePath, path: PathLikeT) -> PurePath:
    """Makes a path absolute and normalized.

    Removes '.' and resolves '..' path parts.

    Args:
      cur_dir: The path to the current directory, used if the path is
        relative.
      path: The path to make absolute.
    """
    return cls.Path(os.path.normpath(cur_dir / path))


class Executor:
  """Executes input files.

  At any time, the effective execution context is the concatenation of:
  1) the call context: self.context
  2) the branch context: self.current_branch.context
  """

  logger: Logger
  fs: FileSystem
  __current_dir: PurePath  # The absolute path of the current directory.

  # The absolute path prefix of all output files; treated as a string prefix,
  # not necessarily a directory.
  __output_path_prefix: PurePath

  # The absolute paths of the readers and writers opened so far.
  opened_paths: set[PurePath]

  system_branch: TextBranch  # # The first branch of the executor, of type text.
  root_branches: list[Branch[Any]]  # All root branches, including system.
  branches: dict[str, Branch[Any]]  # All branches by name.
  current_branch: Branch[Any]  # The currently selected branch.

  # The top of the execution contexts stack.
  call_context: ExecutionContext

  #  The writer to send text-only output to.
  # If set, the executor is in text-only mode: executing text-incompatible
  # macros fails. If None, the executor is in normal mode.
  __current_text_writer: Optional[TextIO]

  # The current macro call stack, pre-allocated to MAX_NESTED_CALLS frames.
  __call_stack: list[Optional[tuple[CallNode, StandardMacroT]]]
  __call_stack_size: int  # The number of frames in __call_stack.
  __include_stack: list[Filename]  # The stack of included file names.

  def __init__(self, *, logger: Logger, fs: FileSystem=FileSystem(),
               current_dir: PurePath, output_path_prefix: PurePath):
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

  def AddConstants(self, constants: Mapping[str, str]) -> None:
    """Adds constant macros to the system branch.

    Args:
      constants: The constants to add, keyed by name.
    """
    context = self.system_branch.context
    for name, value in constants.items():
      context.AddMacro(name, AppendTextCallback(value))

  def GetOutputWriter(self, filename_suffix: str) -> TextIO:
    """Creates a writer for the given output file.

    Args:
      filename_suffix: The path suffix of the file to write, relative to
        __output_path_prefix. Must be empty, or start with a dot and contain no
        directory separator.

    Raises:
      NodeError
    """
    fs = self.fs

    # Compute and validate the absolute path.
    if filename_suffix:
      if not filename_suffix.startswith('.'):
        raise NodeError(f"invalid output file name suffix: '{filename_suffix}';"
                         " must be empty or start with a period")
      if filename_suffix != fs.basename(filename_suffix):
        raise NodeError(f"invalid output file name suffix: '{filename_suffix}';"
                         " must be a basename (no directory separator)")
    path = fs.Path(str(self.__output_path_prefix) + filename_suffix)
    if path in self.opened_paths:
      raise NodeError(f'output file already opened: {path}')
    self.logger.LogInfo(f'Writing: {path}')

    # Create the writer.
    try:
      writer = fs.open(path, mode='wt')
    except OSError as e:
      raise NodeError(f'unable to write to file: {path}\n{e}') from e
    self.opened_paths.add(path)
    return writer

  def ResolveFilePath(self, path: str, directory: PathLikeT,
                      default_ext: Optional[str]=None) -> PurePath:
    """Normalizes a user-entered, possibly relative file path.

    Args:
      path: The path to resolve.
      directory: The path of the directory to resolve path against if it is
        relative. Can be relative to current_dir.
      default_ext: The extension to append to the path if it has none and it
        refers to a non-existing file.

    Returns:
      The resolved path, always absolute.
    """
    return self.ResolveFilePathStatic(
        path,
        abs_directory=self.__current_dir / directory,
        default_ext=default_ext,
        fs=self.fs)

  @staticmethod
  def ResolveFilePathStatic(path: str, *,
                            abs_directory: PurePath,
                            default_ext: Optional[str]=None,
                            fs: FileSystem) -> PurePath:
    """Normalizes a user-entered, possibly relative file path.

    Args:
      path: The path to resolve.
      abs_directory: The absolute path of the directory to resolve path against
        if it is relative.
      default_ext: The extension to append to the path if it has none and it
        refers to a non-existing file.

    Returns:
      The resolved path, always absolute.
    """
    assert abs_directory.is_absolute()
    abs_path = fs.MakeAbsolute(abs_directory, path)
    if (default_ext is not None and not abs_path.suffix and
        not fs.lexists(abs_path)):
      abs_path = abs_path.with_suffix(default_ext)
    return abs_path

  def ExecuteFile(self, path: PurePath) -> None:
    """Executes the given PyScribe file.

    Args:
      path: The absolute path of the file to execute.

    Raises:
      FatalError: File execution error
      NodeError: Too many nested includes
      OSError: Unable to open the file
    """
    assert path.is_absolute()
    self.opened_paths.add(path)
    filename = Filename(path, path.parent)
    with self.fs.open(path, mode='rt') as reader:
      if len(self.__include_stack) >= MAX_NESTED_INCLUDES:
        raise NodeError('too many nested includes')

      self.__include_stack.append(filename)
      try:
        nodes = ParseFile(reader, filename, logger=self.logger)
        self.ExecuteNodes(nodes)
      finally:
        self.__include_stack.pop()

  def RenderBranches(self) -> None:
    """Renders all root branches with an output file.

    Do not close the writers: tests need to be able to call StringIO.getvalue(),
    and production closes the files automatically.

    Raises:
      FatalError
      NodeError
      OSError: Output file write error
    """
    for branch in self.root_branches:
      branch.Render()

  def ExecuteNodes(self, nodes: NodesT) -> None:
    """Executes the given nodes in the current call context.

    Args:
      nodes: The nodes to execute.

    Raises:
      FatalError
    """
    for node in nodes:
      try:
        node.Execute(self)
      except NodeError as e:
        raise self.FatalError(node.location, e) from e

  def ExecuteInCallContext(
      self, nodes: NodesT, call_context: Optional[ExecutionContext]) -> None:
    """Executes the given nodes in the given call context.

    Args:
      nodes: The nodes to execute.
      call_context: The call context to execute the nodes in, None for current.
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

  def ExecuteInBranchContext(self, nodes: NodesT,
                             branch_context: ExecutionContext) -> None:
    """Executes the given nodes in the given branch context.

    Args:
      nodes: The nodes to execute.
      call_context: The branch context to execute the nodes in.
    """
    old_branch_context = self.current_branch.context
    self.current_branch.context = branch_context
    try:
      self.ExecuteNodes(nodes)
    finally:
      self.current_branch.context = old_branch_context

  def AppendText(self, text: str) -> None:
    """Appends a block of text to the current branch."""
    text_writer = self.__current_text_writer
    if text_writer is None:
      self.current_branch.AppendText(text)
    else:
      text_writer.write(text)

  def RegisterBranch(self, branch: Branch[Any]) -> None:
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

  def EvalText(self, nodes: NodesT) -> str:
    """
    Evaluates the given nodes into text.

    Does not add the text to the current branch.
    Fails if text-incompatible macros are executed.

    Args:
      nodes: (List[node]) The text nodes to evaluate.

    Returns:
      (str) The nodes execution result.

    Raises:
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

  def FatalError(self, location: Location, message: MessageT, *,
                 call_frame_skip: int=0) -> FatalErrorT:
    """Logs and raises a fatal error."""
    frame_count = max(0, self.__call_stack_size - call_frame_skip)
    call_stack: list[tuple[CallNode, StandardMacroT]] = (
        self.__call_stack[:frame_count])  # type: ignore[assignment]
    call_nodes = [call_node for call_node, callback in reversed(call_stack)]
    return self.logger.LocationError(location, message, call_stack=call_nodes)

  def MacroFatalError(self, call_node: CallNode, message: MessageT, *,
                      call_frame_skip: int=1) -> FatalErrorT:
    """Logs and raises a macro fatal error."""
    return self.FatalError(call_node.location,
                           f'${call_node.name}: {FormatMessage(message)}',
                           call_frame_skip=call_frame_skip)

  def LookupMacro(
      self, name: str, text_compatible: bool) -> Optional[StandardMacroT]:
    """Finds the macro with the given name in the active contexts.

    Looks for the macro:
    1) in the call context
    2) in the context of the current branch.

    Args:
      name: The name of the macro to retrieve.
      text_compatible: Whether the macro must be text-compatible.

    Returns:
      The macro callback, None if no macro has been found.
    """
    for context in (self.call_context, self.current_branch.context):
      callback = context.LookupMacro(name, text_compatible)
      if callback is not None:
        return callback
    return None

  def CallMacro(self, call_node: CallNode) -> None:
    """Invokes a macro.

    Args:
      call_node: The macro call description.
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
                            f'macro not found: ${call_node.name}')

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

  def CheckArgumentCount(self, call_node: CallNode,
                         macro_callback: StandardMacroT,
                         min_args_count: int,
                         max_args_count: Optional[int]=None) -> None:
    """
    Raises an exception if a macro call has an invalid number of arguments.

    Args:
      call_node: The macro call.
      macro_callback: The callback of the macro called.
      min_args_count: The minimum number of arguments of the macro.
      max_args_count: The maximum number of arguments of the macro,
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
    expected_message += f'{min_args_count}'
    if min_args_count < max_args_count:
      expected_message += f'..{max_args_count}'
    signature = GetMacroSignature(call_node.name, macro_callback)
    raise self.FatalError(
        call_node.location,
        f'{signature}: arguments count mismatch: '
        f'expected {expected_message}, got {actual_args_count}',
        call_frame_skip=1)
