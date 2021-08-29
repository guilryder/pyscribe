# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'


import io

from branches import AbstractSimpleBranch
from macros import *


_SEPARATOR_CHARS = ' \t\n\r\\[]{}%'


class LatexWriter:
  """
  Wraps a writer with logic to handle $latex.sep.

  Fields:
    __writer: (writer) The wrapped writer. Can be StringIO or any other writer.
    __sep_begin: (bool) Whether $latex.sep was called at the beginning of the
      writer, before any text was appended.
    __sep_end: (bool) Whether $latex.sep was called since the last time text has
      been written. Cannot be true if the writer is empty.
    __last_char: (None|string) The last character written, if any.
  """

  def __init__(self, writer):
    self.__writer = writer
    self.__sep_begin = False
    self.__sep_end = False
    self.__last_char = None

  def AppendText(self, text):
    """Writes text. Writes a space first if requested by AppendSep()."""
    if not text:
      return

    # Write a space if AppendSep() was called and if necessary to avoid LaTeX
    # syntax errors according to __last_char and text[0].
    if self.__sep_end:
      self.__sep_end = False
      previous_char = self.__last_char
      next_char = text[0]
      if ((previous_char == '\\' and next_char == '\\')
          or next_char not in _SEPARATOR_CHARS):
        self.__writer.write(' ')

    # Write the text.
    self.__writer.write(text)
    self.__last_char = text[-1]

  def AppendSep(self):
    """
    Writes a space character if necessary to avoid LaTeX syntax errors.

    Does nothing if followed by a write of one of _SEPARATOR_CHARS.
    Else, writes a space character.
    Special case: inserts a space between consecutive backslashes.
    """
    if self.__writer.tell() == 0:
      self.__sep_begin = True
    else:
      self.__sep_end = True

  def AppendLeafLatexWriter(self, leaf_latex_writer):
    """
    Writes the contents of another LatexWriter backed by a StringIO writer.

    Closes the StringIO of leaf_latex_writer to detect attempts to render the
    same leaf multiple times.
    """
    leaf_text = leaf_latex_writer.__writer.getvalue()
    leaf_latex_writer.__writer.close()

    if leaf_latex_writer.__sep_begin:
      self.AppendSep()

    self.AppendText(leaf_text)

    if leaf_latex_writer.__sep_end:
      self.AppendSep()


class LatexBranch(AbstractSimpleBranch):
  """
  Branch for LaTeX code.
  """

  type_name = 'latex'

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

    if self.parent is None:
      self.context.AddMacros(GetPublicMacros(Macros))

  def _CreateLeaf(self):
    return LatexWriter(io.StringIO())

  def AppendText(self, text):
    self._current_leaf.AppendText(text)

  def AppendSep(self):
    self._current_leaf.AppendSep()

  def CreateSubBranch(self):
    return LatexBranch(parent=self)

  def _Render(self, writer):
    render_latex_writer = LatexWriter(writer)
    for leaf_latex_writer in self._IterLeaves():
      render_latex_writer.AppendLeafLatexWriter(leaf_latex_writer)


class Macros:
  TextPercent = AppendTextMacro('text.percent', r'\%', )
  TextAmpersand = AppendTextMacro('text.ampersand', r'\&')
  TextBackslash = AppendTextMacro('text.backslash', r'\textbackslash{}')
  TextCaret = AppendTextMacro('text.caret', r'\string^')
  TextUnderscore = AppendTextMacro('text.underscore', r'\_')
  TextDollar = AppendTextMacro('text.dollar', r'\$')
  TextHash = AppendTextMacro('text.hash', r'\#')
  TextNbsp = AppendTextMacro('text.nbsp', '~')
  TextSoftHyphen = AppendTextMacro('text.softhyphen', r'\-')
  TextDashEn = AppendTextMacro('text.dash.en', '--')
  TextDashEm = AppendTextMacro('text.dash.em', '---')
  TextEllipsis = AppendTextMacro('text.ellipsis', r'\dots{}')

  @staticmethod
  @macro(public_name='latex.sep')
  def LatexSep(executor, unused_call_node):
    r"""
    Inserts a space after a LaTeX command if necessary to avoid syntax errors.

    Typical usage: \command$latex.sep
    """
    executor.current_branch.AppendSep()
