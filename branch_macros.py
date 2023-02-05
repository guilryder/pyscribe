# -*- coding: utf-8 -*-
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

from collections.abc import Callable, Iterable
from typing import Any, Type

from branches import Branch, TextBranch
from execution import Executor
from html_format import HtmlBranch
from latex import LatexBranch
from log import NodeError
from macros import *
from parsing import CallNode, NodesT, TextNode


__BRANCH_CLASSES: Iterable[Type[Branch[Any]]] = (
    HtmlBranch,
    LatexBranch,
    TextBranch,
)
BRANCH_TYPES = {branch_class.type_name: branch_class
                for branch_class in __BRANCH_CLASSES}

@macro(public_name='branch.write', args_signature='branch_name,*contents')
def BranchWrite(executor: Executor, _: CallNode,
                branch_name: str, contents: NodesT) -> None:
  """Writes contents into the given branch."""
  branch = __ParseBranchName(executor, branch_name)

  old_branch = executor.current_branch
  executor.current_branch = branch
  try:
    executor.ExecuteNodes(contents)
  finally:
    executor.current_branch = old_branch


@macro(public_name='branch.create.root',
       args_signature='branch_type,name_or_ref,filename_suffix')
def BranchCreateRoot(executor: Executor, call_node: CallNode,
                     branch_type: str, name_or_ref: str,
                     filename_suffix: str) -> None:
  """Creates a new root branch.

  The new branch starts with a context containing only the builtin macros.

  Args:
    branch_type: The name of the type of branch to create, see BRANCH_TYPES and
      Branch.type_name.
    name_or_ref: The name of the branch to create, or, if prefixed with '!', the
      name of the macro to store the automatically generated branch name into.
    filename_suffix: The path suffix of the file to save the branch to, relative
      to the output directory concatenated with --output-basename-prefix.
      Must be empty, or start with a dot and contain no directory separator.
  """

  # Parse the branch type.
  branch_class = BRANCH_TYPES.get(branch_type)
  if branch_class is None:
    known = ', '.join(sorted(BRANCH_TYPES))
    raise NodeError(
        f'unknown branch type: {branch_type}; expected one of: {known}')
  branch_class_safe = branch_class  # mypy workaround

  # Create the branch.
  def branch_factory() -> Branch[Any]:
    return branch_class_safe(
        parent=None,
        parent_context=executor.current_branch.context,
        writer=executor.GetOutputWriter(filename_suffix))
  __CreateBranch(executor, call_node, name_or_ref, branch_factory)


@macro(public_name='branch.create.sub', args_signature='name_or_ref')
def BranchCreateSub(
    executor: Executor, call_node: CallNode, name_or_ref: str) -> None:
  """Creates a new sub-branch in the current branch.

  Does not insert it yet.

  Args:
    name_or_ref: The name of the branch to create, or, if prefixed with '!', the
      name of the macro to store the automatically generated branch name into.
  """
  __CreateBranch(executor, call_node, name_or_ref,
                 executor.current_branch.CreateSubBranch)


@macro(public_name='branch.append', args_signature='branch_name')
def BranchAppend(executor: Executor, _: CallNode, branch_name: str) -> None:
  """Appends a previously created sub-branch to the current branch.

  The sub-branch must have been created by the current branch.
  A sub-branch can be appended only once.

  Args:
    branch_name: The name of the branch to insert.
  """
  sub_branch = __ParseBranchName(executor, branch_name)
  executor.current_branch.AppendSubBranch(sub_branch)


def __ParseBranchName(executor: Executor, branch_name: str) -> Branch[Any]:
  """Parses a branch name.

  Args:
    branch_name: The name of the branch to parse.

  Returns:
    The branch having the given name.
  """
  branch = executor.branches.get(branch_name)
  if branch is None:
    raise NodeError(f'branch not found: {branch_name}')
  return branch


def __CreateBranch(executor: Executor, call_node: CallNode, name_or_ref: str,
                   branch_factory: Callable[[], Branch[Any]]) -> None:
  """Creates a new root branch or sub-branch.

  Args:
    call_node: The branch creation macro being executed.
      Given to the created branch name macro, if any,
    name_or_ref: The name of the branch to create, or, if prefixed with
      '!', the name of the macro to store the automatically generated branch
      name into.
    branch_factory: The function to call to create the branch. The factory
      should not name or register the branch.
  """
  is_reference = name_or_ref.startswith('!')

  branch = branch_factory()
  if not is_reference:
    if name_or_ref in executor.branches:
      raise NodeError(f'a branch of this name already exists: {name_or_ref}')
    branch.name = name_or_ref

  executor.RegisterBranch(branch)

  if is_reference:
    assert branch.name
    executor.current_branch.context.AddMacro(
        name_or_ref[1:],
        ExecuteCallback([TextNode(call_node.location, branch.name)]))
