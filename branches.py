# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

from abc import ABCMeta, abstractmethod
import io

from log import NodeError
from macros import *


class Branch(metaclass=ABCMeta):
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

  type_name = None  # must be set in implementations

  def __init__(self, parent, parent_context=None, name=None, writer=None):
    """
    Args:
      parent: (branch) The parent branch, None for top-level branches.
      parent_context: (ExecutionContext) The parent of the execution context
        of the branch. Defaults to parent.context if parent is set.
      name: (string) The name of the branch; optional.
    """
    from execution import ExecutionContext
    if parent and not parent_context:
      parent_context = parent.context
    self.parent = parent
    self.root = parent.root if parent else self
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
    return '<{}: {}>'.format(self.__class__.__name__, self.name)

  @abstractmethod
  def AppendText(self, text):
    """Appends a block of text to the branch."""

  @abstractmethod
  def CreateSubBranch(self):
    """
    Creates a new sub-branch for this branch.

    Does not insert the sub-branch into this branch.

    Returns:
      (Branch) The new sub-branch, unattached.
    """

  def AppendSubBranch(self, sub_branch):
    """
    Appends an existing sub-branch to this branch.

    Checks that the sub-branch is valid.

    Args:
      sub_branch: (Branch) The sub-branch to insert.

    Raises:
      NodeError if the sub-branch is already attached or has not been created by
        this branch.
    """
    if sub_branch.parent is not self:
      raise NodeError(
          "expected a sub-branch created by branch '{self_branch.name}'; " +
          "got one created by branch '{sub_branch.parent.name}'",
          self_branch=self, sub_branch=sub_branch)

    if sub_branch.attached:
      raise NodeError(
          "the sub-branch '{sub_branch.name}' is already attached",
          sub_branch=sub_branch)

    self._AppendSubBranch(sub_branch)
    sub_branch.attached = True

  @abstractmethod
  def _AppendSubBranch(self, sub_branch):
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

  def Render(self):
    """
    Renders this branch and its sub-branches recursively.

    Can be called on root branches only.

    Throws:
      FatalError
      NodeError
      OSError on output file write error
    """
    writer = self.writer
    if writer is not None:
      self._Render(writer)
      writer.flush()

  @abstractmethod
  def _Render(self, writer):
    """
    Renders the branch and its sub-branches recursively.

    Args:
      write: (stream) The stream to render the output text to.
        Must have a write() method.

    Throws:
      FatalError
      NodeError
      OSError on output file write error
    """


class AbstractSimpleBranch(Branch):
  """
  Branch that renders into linear content.

  The branch is a tree of leaves and sub-branches.

  Fields:
    __nodes: (leaf|Branch list) The content leaves and sub-branches of branch.
      Invariant: the last element is always _current_leaf.
    _current_leaf: (leaf) The last leaf of the branch.
  """

  def __init__(self, *args, **kwargs):
    super(AbstractSimpleBranch, self).__init__(*args, **kwargs)
    self.__nodes = []
    self.__AppendLeaf()

  @abstractmethod
  def _CreateLeaf(self):
    """Returns a new, blank leaf node."""

  def __AppendLeaf(self):
    self._current_leaf = self._CreateLeaf()
    self.__nodes.append(self._current_leaf)

  def _AppendSubBranch(self, sub_branch):
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

  def _CreateLeaf(self):
    return io.StringIO()

  def AppendText(self, text):
    self._current_leaf.write(text)

  def CreateSubBranch(self):
    return TextBranch(parent=self)

  def _Render(self, writer):
    for leaf in self._IterLeaves():
      writer.write(leaf.getvalue())
      # Safety check: prevent future access to the leaf.
      leaf.close()
