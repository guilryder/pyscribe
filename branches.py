# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

from __future__ import annotations

__author__ = 'Guillaume Ryder'

from abc import ABC, abstractmethod
from io import StringIO
from typing import ClassVar, Optional

from log import NodeError
from macros import *

class Branch(ABC):
  """Output branch: append-only stream of text nodes and sub-branches.

  Details of sub-branches is an implementation detail of the root branch.
  No method other than the ones declared below can be called on them.

  Fields:
    parent: (Branch) The parent of this branch, None if the branch is root.
    root: (Branch) The root ancestor of this branch, self if the branch is root.
    context: (ExecutionContext) The execution context of the branch.
    sub_branches: (List[Branch]) The direct sub-branches of this branch.
  """

  type_name: ClassVar[str]  # as returned by $branch.type
  name: Optional[str]
  # Whether the branch has been inserted in its parent branch.
  # Always true for root branches.
  attached: bool
  #  The output writer of the root branch. None for child branches.
  writer: Optional[StringIO]

  def __init__(self, *, parent, parent_context=None,
               name: Optional[str]=None, writer: Optional[StringIO]=None):
    """
    Args:
      parent: (branch) The parent branch, None for top-level branches.
      parent_context: (ExecutionContext) The parent of the execution context
        of the branch. Defaults to parent.context if parent is set.
      name: The name of the branch; optional.
      writer: Set if and only if the branch is root.
    """
    from execution import ExecutionContext  # pylint: disable=import-outside-toplevel
    if parent and not parent_context:
      parent_context = parent.context
    self.parent = parent
    self.root = parent.root if parent else self
    self.context = ExecutionContext(parent=parent_context)
    self.name = name
    self.sub_branches: list = []
    self.attached = not parent

    self.context.AddMacro('branch.type', AppendTextCallback(self.type_name))

    if parent:
      parent.sub_branches.append(self)
      assert not writer, 'Child branches cannot have writers'
    else:
      self.writer = writer

  def __repr__(self) -> str:
    return f'<{self.__class__.__name__}: {self.name}>'

  @abstractmethod
  def AppendText(self, text: str) -> None:
    """Appends a block of text to the branch."""

  @abstractmethod
  def CreateSubBranch(self):
    """
    Creates a new sub-branch for this branch.

    Does not insert the sub-branch into this branch.

    Returns:
      (Branch) The new sub-branch, unattached.
    """

  def AppendSubBranch(self, sub_branch) -> None:
    """
    Appends an existing sub-branch to this branch.

    Checks that the sub-branch is valid.

    Args:
      sub_branch: (Branch) The sub-branch to insert, must have self as parent.

    Raises:
      NodeError if the sub-branch is already attached or has not been created by
        this branch.
    """
    if sub_branch.parent is not self:
      assert sub_branch.parent
      raise NodeError(
          f"expected a sub-branch created by branch '{self.name}'; "
          f"got one created by branch '{sub_branch.parent.name}'")

    if sub_branch.attached:
      raise NodeError(f"the sub-branch '{sub_branch.name}' is already attached")

    self._AppendSubBranch(sub_branch)
    sub_branch.attached = True

  @abstractmethod
  def _AppendSubBranch(self, sub_branch) -> None:
    """
    Appends an existing sub-branch to this branch.

    Does not need to check that the sub-branch is valid.

    Args:
      sub_branch: (Branch) The sub-branch to insert.
    """

  def IterBranches(self):
    """
    Iterates over the branch and all its sub-branches.

    Yields:
      (Branch) A branch.
    """
    yield self
    for sub_branch in self.sub_branches:
      yield from sub_branch.IterBranches()

  def Render(self) -> None:
    """
    Renders this branch and its sub-branches recursively.

    Can be called on root branches only.

    Raises:
      FatalError
      NodeError
      OSError: Output file write error.
    """
    writer = self.writer
    if writer is not None:
      self._Render(writer)
      writer.flush()

  @abstractmethod
  def _Render(self, writer: StringIO) -> None:
    """Renders the branch and its sub-branches recursively.

    Args:
      writer: The stream to render the output text to.

    Raises:
      FatalError
      NodeError
      OSError: Output file write error.
    """


class AbstractSimpleBranch(Branch):
  """
  Branch that renders into linear content.

  The branch is a tree of leaves and sub-branches.

  Fields:
    __nodes: (List[leaf|Branch]) The content leaves and sub-branches of branch.
      Invariant: the last element is always _current_leaf.
    _current_leaf: (leaf) The last leaf of the branch.
  """

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.__nodes = []
    self.__AppendLeaf()

  @abstractmethod
  def _CreateLeaf(self):
    """Returns a new, blank leaf node."""

  def __AppendLeaf(self) -> None:
    self._current_leaf = self._CreateLeaf()
    self.__nodes.append(self._current_leaf)

  def _AppendSubBranch(self, sub_branch) -> None:
    self.__nodes.append(sub_branch)
    self.__AppendLeaf()

  def _IterLeaves(self):
    for node in self.__nodes:
      if isinstance(node, AbstractSimpleBranch):
        yield from node._IterLeaves()
      else:
        yield node


class TextBranch(AbstractSimpleBranch):
  """
  Branch for plain-text.
  """

  type_name = 'text'

  def _CreateLeaf(self) -> StringIO:
    return StringIO()

  def AppendText(self, text: str) -> None:
    self._current_leaf.write(text)

  def CreateSubBranch(self) -> TextBranch:
    return TextBranch(parent=self)

  def _Render(self, writer: StringIO) -> None:
    for leaf in self._IterLeaves():
      writer.write(leaf.getvalue())
      # Safety check: prevent future access to the leaf.
      leaf.close()
