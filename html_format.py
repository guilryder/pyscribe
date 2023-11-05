# -*- coding: utf-8 -*-
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

from __future__ import annotations

__author__ = 'Guillaume Ryder'

from collections.abc import Callable
from abc import ABC, abstractmethod
import enum
import re
from typing import Any, ClassVar, override, TextIO

from lxml import etree
from lxml.etree import _Element
# pylint: disable=len-as-condition

from branches import Branch
from execution import ENCODING, ExecutionContext, Executor
from log import NodeError
from macros import *
from parsing import CallNode


NBSP = '\xa0'

# Groups:
# 0: sign (possibly empty)
# 1: digits before decimal separator (possibly empty)
# 2: decimal separator (optional)
# 3: digits after the decinal separator (optional)
_NUMBER_REGEXP = re.compile(r'^([-+]?)([0-9]*)(?:([.,])([0-9]+))?$')

# Name and value of the element attribute that marks its element for deletion
# if the element is empty: no text, no children.
_DELETE_IF_EMPTY_ATTR_NAME = '__delete_if_empty'
_DELETE_IF_EMPTY_ATTR_VALUE = '1'

# Tags that have no contents therefore render as <tag/>.
# Source: http://www.w3.org/TR/html-markup/syntax.html#void-element
_VOID_TAGS_TO_NONE = {
  tag: None
  for tag in 'area,base,br,col,command,embed,hr,img,input,keygen,link,meta,'
             'param,source,track,wbr'.split(',')
}

# Characters to strip around tag text contents.
_STRIPPABLE = ' \r\n\t'


def GetTagEmptyContents(tag_name: str) -> str | None:
  """Returns the text an empty element of the given tag should have.

  Returns None or '' depending on the tag.
  """
  return _VOID_TAGS_TO_NONE.get(tag_name, '')


@enum.unique
class TagLevel(str, enum.Enum):
  """Level of a tag, used automatically paragraphs on '\n\n'."""

  is_para: bool
  is_auto: bool
  is_inline: bool

  def __new__(cls, name: str, flags: frozenset[str]=frozenset()) -> TagLevel:
    level = str.__new__(cls, name)
    level._value_ = name
    level.is_para = 'para' in flags
    level.is_auto = 'auto' in flags
    level.is_inline = 'inline' in flags
    return level

  # Block-level element.
  # Can contain sub-blocks, paragraphs, and inline tags.
  # Example: <body>, <div> sometimes.
  BLOCK = 'block'

  # Paragraph element to be closed manually.
  # Can contain only inline tags.
  # Example: <h1>, <ul>, <hr/>, <div> sometimes.
  PARAGRAPH = ('para', {'para'})

  # Paragraph element that can be closed automatically.
  # Can contain only inline tags.
  # Example: <p>, <div> sometimes.
  AUTO_PARAGRAPH = ('autopara', {'para', 'auto'})

  # Inline-level element. Inside a block or a paragraph.
  # Can contain only inline tags.
  # Example: <span>, <em>.
  INLINE = ('inline', {'inline'})


class HtmlBranch(Branch['HtmlBranch']):
  """Branch for HTML."""

  class ElementInfo:
    """
    parent: The ElementInfo of the parent of the element.
    elem: The element.
    level: The level of the element.
    auto_para_tag: The tag to use for auto-paragraphs,
      None if the element does not support auto-paragraphs.
      Must be None for non-block elements.
    """
    def __init__(self, parent: HtmlBranch.ElementInfo | None,
                 elem: _Element, level: TagLevel,
                 auto_para_tag: str | None=None):
      if auto_para_tag:
        assert level == TagLevel.BLOCK
        assert auto_para_tag not in _VOID_TAGS_TO_NONE
      self.parent = parent
      self.elem = elem
      self.level = level
      self.auto_para_tag = auto_para_tag

  __XML_HEADER = f'<?xml version="1.0" encoding="{ENCODING}"?>\n'
  __XHTML_STUB = bytes(f"""\
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"
"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html>
<head>
<meta http-equiv="Content-Type"
      content="application/xhtml+xml; charset={ENCODING}"/>
</head>
</html>
""", encoding='ascii')

  __AUTO_PARA_DELIMITER = re.compile(r'\n{2,}')
  __AUTO_PARA_TAG_DEFAULT = 'p'
  __TAG_TARGET_REGEXP = re.compile(r'\A\<(?P<tag>.+)\>\Z')

  type_name = 'html'

  # The typography set for this branch.
  # If None, inherits the typography of the parent branch.
  __typography: Typography | None

  #  The context containing the macros of self.typography.
  __typography_context: ExecutionContext

  # The tree of the branch. Set for root branches only.
  __tree: etree._ElementTree | None

  # The root element of the branch. Cannot be closed by the branch.
  # Ancestors and siblings of this element cannot be manipulated.
  __root_elem: _Element

  __current_elem: _Element  # # The element currently open.
  __current_elem_info: ElementInfo  # Information about the current element.

  # The current text accumulator of the branch.
  # Used to merge consecutive text nodes created by AppendText.
  __text_accu: list[str]

  # The last chunk of text appended to the current
  # inline tag, empty if the current paragraph has no text.
  # Guaranteed to be non-empty if the current paragraph has some text.
  __line_tail: str

  # The separator for AppendText to insert before the next
  # chunk of non-whitespace text. Expected to be ' ' or NBSP.
  # If empty, whitespaces are appended as is.
  # If not empty, whitespaces are skipped.
  __text_sep: str

  def __init__(self, *args: Any, **kwargs: Any):
    super().__init__(*args, **kwargs)
    parent = self.parent
    self.sub_branches = []

    # Create the contexts tree.
    context = self.context
    if parent is None:
      context.AddMacros(GetPublicMacros(Macros))
      context = ExecutionContext(parent=context)
    self.__typography_context = context
    context = ExecutionContext(parent=context)
    self.context = context

    # Set a typography for root branches.
    self.typography = TYPOGRAPHIES['neutral'] if parent is None else None

    if parent is None:
      # Root branch: start from the XHTML stub.
      self.__tree = etree.fromstring(self.__XHTML_STUB).getroottree()

      # Add a <body> element, take it as root.
      self.__root_elem = etree.SubElement(self.__tree.getroot(), 'body')

      # Create a sub-branch for the <head>.
      self.__head_branch = HtmlBranch(parent=self, name='head')
      head_elem = self.__tree.find('head')
      assert head_elem is not None
      head_elem.append(self.__head_branch.__root_elem)
      self.__head_branch.attached = True
    else:
      # Sub-branch: create a placeholder element in the DOM.
      self.__root_elem = etree.Element('branch')

    self.__current_elem = self.__root_elem
    self.__current_elem_info = self.ElementInfo(
        parent=None, elem=self.__root_elem, level=TagLevel.BLOCK,
        auto_para_tag=self.__AUTO_PARA_TAG_DEFAULT)
    self.__text_accu = []
    self.__line_tail = ''
    self.__text_sep = ''

    self.AutoParaTryOpen()

  def GetTypography(self) -> Typography:
    branch = self
    while branch is not None:
      typography = branch.__typography
      if typography:
        return typography
      branch = branch.parent  # type: ignore[assignment]
    return None  # pragma: no cover

  def SetTypography(self, typography: Typography) -> None:
    self.__typography = typography
    self.__typography_context.macros = (
        typography.context.macros if typography else {})

  typography = property(GetTypography, SetTypography,
                        doc='(Typography) The typography rules.')

  def AppendRawText(self, text: str) -> None:
    """Appends plain text.

    Ignores typography and paragraph detection.
    """
    self.__text_accu.append(self.__text_sep)
    self.__text_accu.append(text)
    self.__line_tail = self.__text_sep = ''

  @override
  def AppendText(self, text: str) -> None:
    paras = self.__AUTO_PARA_DELIMITER.split(text)

    # Write the tail of the previous paragraph.
    first_para = paras[0]
    if first_para:
      self.AppendLineText(first_para)
    if len(paras) == 1:
      return

    # Flush then write the paragraphs without the buffer.
    for para in paras[1:]:
      self.AutoParaTryClose()
      if not self.AutoParaTryOpen():
        raise NodeError('unable to open a new paragraph')
      if para:  # pragma: no cover
        # Should never happen: at most one paragraph break per chunk of text.
        self.AppendLineText(para)

  __NBSP_TRIM_REGEXP = re.compile(r' *' + NBSP + r' *')
  __MULTIPLE_SPACES = re.compile(r' {2,}')

  def AppendLineText(self, text: str) -> None:
    """Appends text to the current line.

    Faster equivalent of AppendText() when the text to append is newlines-free.

    Args:
      text: The non-empty string to append. Must not contain any '\n'.
    """
    text = self.__NBSP_TRIM_REGEXP.sub(NBSP, text)
    text = self.__MULTIPLE_SPACES.sub(' ', text)
    assert text

    sep = self.__text_sep
    if sep:
      if text == ' ':
        # AppendText(' ') is a NOOP if there is a separator.
        return
      if text[0] == ' ':
        # The text starts with a space:
        # insert the separator if it is not a space (i.e. NBSP),
        # then skip the space of the text.
        if sep != ' ':
          text = sep + text[1:]
      elif text[0] != NBSP:
        # The text does not start with whitespace: insert the separator.
        text = sep + text
      # Separator dropped if the text starts with NBSP.

    # At this point the separator has been consumed.
    # Compute the new separator.
    last_char = text[-1]
    if last_char == ' ':
      # The text ends with a space: move it to a new separator.
      self.__text_sep = last_char
      text = text[:-1]
    elif sep:
      # No more separator.
      self.__text_sep = ''

    # Drop space prefixes after whitespace.
    if text.startswith(' ') and self.__line_tail.endswith(NBSP):
      text = text[1:]

    # Append the remaining text.
    if text:
      self.__text_accu.append(text)
      self.__line_tail = text

  def AppendNewline(self) -> None:
    """Appends a line break to the current paragraph.

    Drops pending trailing spaces in the current line.
    Cancels the effect of RequireNonBreakingSpace() if it has just been called.

    This method is a noop after __InlineFlush().
    """
    self.__line_tail = self.__text_sep = ''

  def RequireNonBreakingSpace(self) -> None:
    """Requests a non-breaking space (NBSP) to be present.

    Inserts a new NBSP only if:
    * not at the beginning of a line
    * not at the end of a line
    * no NBSP is already present
    """
    tail = self.__line_tail
    if tail and tail[-1] != NBSP:
      self.__text_sep = NBSP

  def GetTailChar(self) -> str | None:
    """Returns the tail character of the current line."""
    tail = self.__text_sep or self.__line_tail
    return tail[-1] if tail else None

  def AutoParaTryOpen(self, *, except_tag: str | None=None) -> bool:
    """Opens a new paragraph, if possible.

    Args:
      except_tag: Does not open a new paragraph with this tag.

    Returns:
      Whether a tag was opened.
    """
    auto_para_tag = self.__current_elem_info.auto_para_tag
    if auto_para_tag and auto_para_tag != except_tag:
      self.OpenTag(auto_para_tag, level=TagLevel.AUTO_PARAGRAPH)
      return True
    else:
      return False

  def AutoParaTryClose(self) -> bool:
    """Closes the current element if is an automatically-closeable paragraph.

    Returns:
      Whether a tag was closed.
    """
    if self.__current_elem_info.level == TagLevel.AUTO_PARAGRAPH:
      self.__CloseCurrentElement(discard_if_empty=True)
      return True
    else:
      return False

  def __FlushText(self) -> None:
    """Flushes the text accumulator to the branch.

    Drops the pending separator, if any.
    """
    text_accu = self.__text_accu
    if text_accu:
      text = ''.join(text_accu)
      del self.__text_accu[:]
      elem = self.__current_elem
      if len(elem):
        # Append to the tail of the last child of the current element.
        self._AppendTextToXml(text, tail_elem=elem[-1])
      else:
        # Append to the text of the current, childless element.
        self._AppendTextToXml(text, text_elem=elem)
      self.__line_tail = text
    self.__text_sep = ''

  def OpenTag(self, tag: str, level: TagLevel, *,
              auto_para_tag: str | None=None) -> None:
    """Opens a new child tag in the current element, and makes it current.

    Args:
      tag: The name of the tag, such as 'p' or 'h1'.
      level: The level of the new element.
      auto_para_tag: The tag to use for auto-paragraphs,
        None if the element does not support auto-paragraphs.
        Must be None for non-block elements.
    """
    # Close the current paragraph if we are creating a new block or paragraph.
    if level.is_inline:
      # Flush the separator.
      sep = self.__text_sep
      if sep and (sep != ' ' or not self.__line_tail.endswith(NBSP)):
        self.__text_accu.append(sep)
        self.__line_tail = sep
      self.__FlushText()
    else:
      self.__line_tail = ''
      self.__FlushText()
      self.AutoParaTryClose()
      if self.__current_elem_info.level.is_inline:
        raise NodeError(
            'impossible to open a non-inline tag inside an inline tag')

    elem = etree.SubElement(self.__current_elem, tag)
    self.__current_elem = elem

    # Create an ElementInfo for the new element.
    self.__current_elem_info = self.ElementInfo(
        parent=self.__current_elem_info, elem=elem, level=level,
        auto_para_tag=auto_para_tag)

    self.AutoParaTryOpen()

  def CloseTag(self, tag: str) -> None:
    """Closes the first ancestor element with a given tag name.

    Automatically closes intermediate paragraph elements as needed.
    Fails if encounters intermediate non-paragraph elements.

    Discards the paragraph elements closed that are empty.

    Args:
      tag: The name of the tag to close.

    Raises:
      NodeError: The given tag cannot be found or closed.
    """
    while True:
      if self.__current_elem.tag == tag:
        # Tag match: close the element, open a new paragraph if appropriate.
        self.__CloseCurrentElement(discard_if_empty=False)
        self.AutoParaTryOpen(except_tag=tag)
        break
      # Tag mismatch: expect a paragraph, auto-close it.
      if not self.AutoParaTryClose():
        # Not a pragraph: tag mismatch error.
        raise NodeError(
            f'expected current tag to be <{tag}>, '
            f'got <{self.__current_elem.tag}>')

  def __CloseCurrentElement(self, *, discard_if_empty: bool) -> None:
    """Closes the current element.

    Args:
      discard_if_empty: Whether to remove the element if it's empty.

    Raises:
      NodeError if the given tag cannot be found or closed.
    """
    self.__FlushText()
    closed_elem = self.__current_elem
    if closed_elem == self.__root_elem:
      raise NodeError('cannot close the root element of the branch')

    # Pop the element.
    current_elem_info = self.__current_elem_info
    if not current_elem_info.level.is_inline:
      self.__line_tail = ''
    new_elem_info = current_elem_info.parent
    assert new_elem_info is not None
    new_elem = new_elem_info.elem
    self.__current_elem_info = new_elem_info
    self.__current_elem = new_elem

    # If requested, discard the element if it's empty.
    new_closed_elem: _Element | None = closed_elem
    if discard_if_empty and self._RemoveElementIfEmpty(closed_elem,
                                                       preserve_tail=False):
      new_closed_elem = None

    if (not current_elem_info.level.is_inline and new_closed_elem is not None
        and new_closed_elem.tail is None):
      new_closed_elem.tail = '\n'

  def RegisterTargetAction(self, unused_call_node: CallNode, target: str,
                           action: Callable[[_Element], None]) -> None:
    """Executes an action against a target element.

    The action may be executed later, asynchronously.

    Args:
      call_node: The macro being called.
      target: The target given by the user.
      action: The method to call with the targeted element.

    Raises:
      NodeError
    """
    # pylint: disable=unnecessary-lambda-assignment
    elem_info_predicate: Callable[[HtmlBranch.ElementInfo], bool]
    if target == 'current':
      # Current element, possibly automatically created.
      elem_info_predicate = lambda elem_info: True
    elif target == 'auto':
      # Current automatically created element, fails if none.
      elem_info_predicate = lambda elem_info: elem_info.level.is_auto
    elif target == 'nonauto':
      # First non-automatically created ancestor element.
      elem_info_predicate = lambda elem_info: not elem_info.level.is_auto
    elif target == 'parent':
      # Parent element.
      elem_info_predicate = (
          lambda elem_info: elem_info != self.__current_elem_info)
    elif target == 'previous':
      # Previous element.
      elem_info: HtmlBranch.ElementInfo | None = self.__current_elem_info
      while elem_info and elem_info.parent:
        prev_elem = elem_info.elem.getprevious()
        if prev_elem is not None:
          action(prev_elem)
          return
        elem_info = elem_info.parent
      raise NodeError('no previous element exists')
    elif target == 'para':
      # Deepest paragraph element.
      elem_info_predicate = lambda elem_info: elem_info.level.is_para
    else:
      # Deepest element with the given tag.
      tag_match = self.__TAG_TARGET_REGEXP.match(target)
      if tag_match is None:
        raise NodeError(f'invalid target: {target}')
      tag = tag_match.group(1)
      elem_info_predicate = lambda elem_info: elem_info.elem.tag == tag

    # Execute the action against the deepest element matching the predicate.
    elem_info = self.__current_elem_info
    while elem_info and not elem_info_predicate(elem_info):
      elem_info = elem_info.parent
    if elem_info is None:
      raise NodeError(f'no element found for target: {target}')
    action(elem_info.elem)

  @override
  def CreateSubBranch(self) -> HtmlBranch:
    return HtmlBranch(parent=self)

  @override
  def _AppendSubBranch(self, sub_branch: HtmlBranch) -> None:
    self.__FlushText()
    self.AutoParaTryClose()
    self.__current_elem.append(sub_branch.__root_elem)
    self.AutoParaTryOpen()

  @override
  def _Render(self, writer: TextIO) -> None:
    self.__Finalize()

    # Post-process all elements.
    assert self.__tree
    self.__PostProcessElementsRecurse(self.__tree.getroot())

    # Insert line breaks in <body>.
    body_elem = self.__root_elem
    if not body_elem.text:
      body_elem.text = '\n'
    body_elem.tail = '\n'

    writer.write(self.__XML_HEADER)
    writer.write(etree.tostring(self.__tree, encoding=str))
    writer.write('\n')

  def __Finalize(self) -> None:
    """Prepares the branch for rendering.

    Recurses in sub-branches.

    Raises:
      NodeError: An element is still open.
    """
    # Close paragraphs automatically. Fail if some elements are still open.
    self.__FlushText()
    while self.AutoParaTryClose():
      pass
    if self.__current_elem_info.parent:
      raise NodeError(
          f'element not closed in branch "{self.name}": '
          f'<{self.__current_elem.tag}>')

    # Inline the attached branches.
    for branch in self.sub_branches:
      if branch.attached:
        branch.__Finalize()
        self._InlineXmlElement(branch.__root_elem)

  @classmethod
  def __PostProcessElementsRecurse(
      cls, elem: _Element, *, strip_spaces: bool=False) -> None:
    """Finalizes an element: strips spaces, processes "delete if empty".

    Strips spaces on <body> children only.

    Recurses in children.
    """
    # Recurse.
    strip_spaces_child = strip_spaces or elem.tag == 'body'
    for child_elem in list(elem):
      cls.__PostProcessElementsRecurse(child_elem,
                                       strip_spaces=strip_spaces_child)

    # Strip spaces.
    if strip_spaces:
      if len(elem):
        elem.text = (elem.text or '').lstrip(_STRIPPABLE) or None
        tail_elem = elem[-1]
        tail_elem.tail = (tail_elem.tail or '').rstrip(_STRIPPABLE) or None
      else:
        elem.text = ((elem.text or '').strip(_STRIPPABLE) or
                     GetTagEmptyContents(elem.tag))

    # Process the "delete if empty" attribute.
    if (elem.attrib.pop(
            _DELETE_IF_EMPTY_ATTR_NAME, None)  # type: ignore[arg-type]
        == _DELETE_IF_EMPTY_ATTR_VALUE):
      cls._RemoveElementIfEmpty(elem, preserve_tail=True, ignore_attribs=True)

    # Comment out the contents of <style> tags to disable escaping.
    if elem.tag == 'style' and elem.text:
      elem.append(etree.Comment(f'\n{elem.text}\n'))
      elem.text = None

  @classmethod
  def _RemoveElementIfEmpty(
      cls, elem: _Element, *,
      preserve_tail: bool, ignore_attribs: bool=False) -> bool:
    """Removes an element if it is empty: no text, no children.

    Args:
      elem: The element to remove.
      preserve_tail: Whether to preserve element tail, if any, by appending it
        to the before element.
      ignore_attribs: Whether to remove the element even if it has attributes;
        fails if false and the element has attributes.

    Returns:
      Whether the element was empty and has been removed.
    """
    if (elem.text and elem.text.strip(_STRIPPABLE)) or len(elem):
      return False

    # Append the placeholder tail to the before element,
    # then delete the element.
    parent_elem = elem.getparent()
    assert parent_elem is not None
    if preserve_tail:
      cls._AppendTextToXml((elem.tail or '').strip(_STRIPPABLE) or None,
                           tail_elem=elem.getprevious(),
                           text_elem=parent_elem)
    parent_elem.remove(elem)

    # Fail if the element has attributes.
    if (not ignore_attribs and elem.attrib and
        elem.attrib.get(
            _DELETE_IF_EMPTY_ATTR_NAME, None)  # type: ignore[arg-type]
            != _DELETE_IF_EMPTY_ATTR_VALUE):
      elem.text = ''
      raise NodeError(
          'removing an empty element with attributes: ' +
              etree.tostring(elem, encoding='unicode'))
    return True

  @staticmethod
  def _AppendTextToXml(text: str | None, *,
                       tail_elem: _Element | None=None,
                       text_elem: _Element | None=None) -> None:
    """Appends text to an XML element.

    Appends the text to tail_elem tail if valid, else to text_elem text.

    Args:
      text: The text to append, not XML-escaped.
      tail_elem: If not None, appends to this element's tail.
      text_elem: If tail_elem is None, appends to this element's text.
    """
    if text:
      if tail_elem is not None:
        tail_elem.tail = (tail_elem.tail or '') + text
      else:
        assert text_elem is not None
        text_elem.text = (text_elem.text or '') + text

  @classmethod
  def _InlineXmlElement(cls, elem: _Element) -> None:
    """Replaces an lxml Element with its contents.

    Handles text and tail properly.
    The attributes of the element are lost.
    """
    parent_elem = elem.getparent()
    previous_elem = elem.getprevious()
    assert parent_elem is not None

    # Append the head text of the branch to the before element
    # (previous element if any, else parent element).
    cls._AppendTextToXml(elem.text, tail_elem=previous_elem,
                                    text_elem=parent_elem)

    # Append the placeholder tail to the last child or the before element.
    if len(elem):
      previous_elem = elem[-1]
    cls._AppendTextToXml(elem.tail, tail_elem=previous_elem,
                                    text_elem=parent_elem)

    # Replace the placeholder element with its children.
    for child in elem:
      elem.addprevious(child)
    del elem[:]
    elem.text = elem.tail = None
    assert cls._RemoveElementIfEmpty(elem, preserve_tail=False)

    # Render the parent element as <tag></tag> instead of <tag/> if necessary.
    if not parent_elem.text and not len(parent_elem):
      parent_elem.text = GetTagEmptyContents(parent_elem.tag)


class Typography(ABC):

  name: ClassVar[str]
  macros_container: Any = None

  def __init__(self) -> None:
    super().__init__()
    assert self.name
    if self.macros_container is None:
      self.macros_container = self
    self.context = ExecutionContext(parent=None)
    self.context.AddMacros(GetPublicMacros(self.macros_container))

  @staticmethod
  @abstractmethod
  def FormatNumber(number: str) -> str:
    """Formats a number to a string.

    Args:
      number: The number to format. Prefixed with '-' if negative.
        Can use '.' or ',' as decimal separator.

    Returns:
      The formatted number.
    """

  @staticmethod
  def FormatNumberCustom(number: str, thousands_sep: str) -> str:
    number_match = _NUMBER_REGEXP.match(number)
    if number_match is None:
      return number
    sign, before_decimal, decimal_sep, after_decimal = number_match.groups()

    # Use an en-dash as minus sign.
    if sign == '-':
      sign = '–'
    text = sign

    text += thousands_sep.join(
        reversed([before_decimal[max(0, group_end-3):group_end]
                  for group_end in range(len(before_decimal), 0, -3)]))

    if decimal_sep:
      text += decimal_sep
      text += thousands_sep.join(
          [after_decimal[group_start:group_start+3]
           for group_start in range(0, len(after_decimal), 3)])

    return text


class NeutralTypography(Typography):
  """Language-neutral typography rules."""

  name = 'neutral'
  macros_container = __import__('core_macros').SpecialCharacters

  @staticmethod
  @override
  def FormatNumber(number: str) -> str:
    return number


class EnglishTypography(Typography):
  """English-specific typography rules."""

  name = 'english'

  @staticmethod
  @override
  def FormatNumber(number: str) -> str:
    return Typography.FormatNumberCustom(number, ',')

  TextBacktick = AppendTextMacro('text.backtick', "‘")
  TextApostrophe = AppendTextMacro('text.apostrophe', "’")


class FrenchTypography(Typography):
  """French-specific typography rules."""

  name = 'french'

  @staticmethod
  @override
  def FormatNumber(number: str) -> str:
    return Typography.FormatNumberCustom(number, NBSP)

  TextBacktick = AppendTextMacro('text.backtick', "‘")
  TextApostrophe = AppendTextMacro('text.apostrophe', "’")

  @staticmethod
  @macro(public_name='text.guillemet.open')
  def TextGuillemetOpen(executor: Executor, _: CallNode) -> None:
    branch: HtmlBranch = executor.current_branch  # type: ignore[assignment]
    branch.AppendLineText('«')
    branch.RequireNonBreakingSpace()

  @staticmethod
  @macro(public_name='text.guillemet.close')
  def TextGuillemetClose(executor: Executor, _: CallNode) -> None:
    branch: HtmlBranch = executor.current_branch  # type: ignore[assignment]
    branch.RequireNonBreakingSpace()
    branch.AppendLineText('»')

  @staticmethod
  @macro(public_name='text.punctuation.double', args_signature='contents')
  def TextPunctuationDouble(executor: Executor, _: CallNode,
                            contents: str) -> None:
    if not contents:
      return
    branch: HtmlBranch = executor.current_branch  # type: ignore[assignment]
    if branch.GetTailChar() not in ('…', '.'):
      branch.RequireNonBreakingSpace()
    branch.AppendLineText(contents)


TYPOGRAPHIES = {
    typography.name: typography
    for typography in (
        NeutralTypography(), EnglishTypography(), FrenchTypography())
}


class Macros:

  __AUTO_PARA_LEVEL_REGEXP = (
      re.compile(r'\Ablock,autopara=(?P<auto_para_tag>.+)\Z'))
  __CLASS_NAME_SEPARATOR_REGEXP = re.compile(r'\s+')

  @staticmethod
  @macro(public_name='par')
  def Par(executor: Executor, _: CallNode) -> None:
    """Tries to close/open a new automatic paragraph."""
    branch: HtmlBranch = executor.current_branch  # type: ignore[assignment]
    branch.AutoParaTryClose()
    if not branch.AutoParaTryOpen():
      raise NodeError('unable to open a new paragraph')

  @staticmethod
  @macro(public_name='tag.open', args_signature='tag,level_name')
  def TagOpen(executor: Executor, call_node: CallNode,
              tag: str, level_name: str) -> None:
    """Opens a new XML tag.

    Args:
      tag: The name of the tag to open, such as 'span' or 'h1'.
      level_name: The name of the level of the tag (see TagLevel).
    """
    branch: HtmlBranch = executor.current_branch  # type: ignore[assignment]

    # Parse the level name.
    autoparablock_match = Macros.__AUTO_PARA_LEVEL_REGEXP.match(level_name)
    if autoparablock_match:
      level = TagLevel.BLOCK
      auto_para_tag = autoparablock_match.group('auto_para_tag')
      if auto_para_tag in _VOID_TAGS_TO_NONE:
        raise executor.MacroFatalError(
            call_node, f'cannot use void tag as autopara: <{auto_para_tag}>')
    else:
      try:
        level = TagLevel(level_name)
      except ValueError as e:
        known = ', '.join(sorted(TagLevel))
        raise executor.MacroFatalError(
            call_node,
            f'unknown level: {level_name}; expected one of: {known}.') from e
      auto_para_tag = None
    branch.OpenTag(tag, level, auto_para_tag=auto_para_tag)

  @staticmethod
  @macro(public_name='tag.close', args_signature='tag')
  def TagClose(executor: Executor, _: CallNode, tag: str) -> None:
    """Closes the current XML tag.

    Automatically closes intermediate paragraph elements as needed.
    Fails if encounters intermediate non-paragraph elements.

    Discards the paragraph elements closed that are empty.

    Args:
      tag: The name of the tag to close.
    """
    branch: HtmlBranch = executor.current_branch  # type: ignore[assignment]
    branch.CloseTag(tag)

  @staticmethod
  @macro(public_name='tag.body.raw', args_signature='text')
  def TagBodyRaw(executor: Executor, _: CallNode, text: str) -> None:
    """Appends raw text to the current tag body.

    Ignores typography and paragraph detection.
    """
    branch: HtmlBranch = executor.current_branch  # type: ignore[assignment]
    branch.AppendRawText(text)

  @staticmethod
  @macro(public_name='tag.delete.ifempty', args_signature='target')
  def TagDeleteIfEmpty(executor: Executor, call_node: CallNode,
                       target: str) -> None:
    """Delete the specified element if it is empty: no text, no children.

    Ignores attributes.

    The check and possible deletion happen at rendering time, not immediately.

    Args:
      target: The element to configure.
    """
    Macros.__TagAttrSet(executor, call_node, target,
                        _DELETE_IF_EMPTY_ATTR_NAME, _DELETE_IF_EMPTY_ATTR_VALUE)

  @staticmethod
  @macro(public_name='tag.attr.set', args_signature='target,attr_name,value')
  def TagAttrSet(executor: Executor, call_node: CallNode,
                 target: str, attr_name: str, value: str) -> None:
    """Sets an attribute in an element.

    Args:
      target: The element to set the attribute into.
      attr_name: The name of the attribute.
      value: The value of the attribute.
    """
    Macros.__TagAttrSet(executor, call_node, target, attr_name, value)

  @staticmethod
  def __TagAttrSet(executor: Executor, call_node: CallNode,
                   target: str, attr_name: str, value: str) -> None:
    if not attr_name.strip():
      raise executor.MacroFatalError(call_node,
                                     'attribute name cannot be empty')

    def Action(elem: _Element) -> None:
      elem.set(attr_name, value)

    branch: HtmlBranch = executor.current_branch  # type: ignore[assignment]
    branch.RegisterTargetAction(call_node, target, Action)

  @staticmethod
  @macro(public_name='tag.class.add', args_signature='target,class_name')
  def TagClassAdd(executor: Executor, call_node: CallNode,
                  target: str, class_name: str) -> None:
    """Adds a CSS class to an element.

    Args:
      target: The element to add the class to.
      class_name: The name of the CSS class; does nothing if empty.
    """
    branch: HtmlBranch = executor.current_branch  # type: ignore[assignment]
    class_names = Macros._ParseClassNames(class_name)

    def Action(elem: _Element) -> None:
      if not class_names:
        return

      # Append the class name to the 'class' attribute.
      # Preserve ordering (meaningful in CSS).
      final_class_names = Macros._ParseClassNames(elem.get('class', ''))
      for class_name in class_names:
        if class_name not in final_class_names:
          final_class_names.append(class_name)
      elem.set('class', ' '.join(final_class_names))

    branch.RegisterTargetAction(call_node, target, Action)

  @staticmethod
  @macro(public_name='typo.name', text_compatible=True)
  def TypoName(executor: Executor, _: CallNode) -> None:
    """Prints the name of the current typography."""
    branch: HtmlBranch = executor.current_branch  # type: ignore[assignment]
    executor.AppendText(branch.typography.name)

  @staticmethod
  @macro(public_name='typo.set', args_signature='typo_name')
  def TypoSet(executor: Executor, call_node: CallNode, typo_name: str) -> None:
    """Sets the typography rules to apply in the current branch.

    Args:
      typo_name: The name of the typography rules, see TYPOGRAPHIES.
    """
    branch: HtmlBranch = executor.current_branch  # type: ignore[assignment]

    typography = TYPOGRAPHIES.get(typo_name, None)
    if not typography:
      known = ', '.join(sorted(TYPOGRAPHIES))
      raise executor.MacroFatalError(
          call_node,
          f'unknown typography name: {typo_name}; expected one of: {known}')
    branch.typography = typography

  @staticmethod
  @macro(public_name='typo.number', args_signature='number')
  def TypoNumber(executor: Executor, call_node: CallNode, number: str) -> None:
    """Formats a number according to the current typography rules."""
    branch: HtmlBranch = executor.current_branch  # type: ignore[assignment]
    root: HtmlBranch = branch.root  # type: ignore[assignment]

    # Reject invalid values.
    if _NUMBER_REGEXP.match(number) is None:
      raise executor.MacroFatalError(call_node, f'invalid integer: {number}')
    executor.AppendText(root.typography.FormatNumber(number))

  @staticmethod
  @macro(public_name='typo.newline')
  def TypoNewline(executor: Executor, _: CallNode) -> None:
    """Prepares the typography engine for a new line.

    Concrete effect: ensures that the typographic spaces required after some
    characters are effectively inserted before the line is broken, instead of
    being dropped.

    Useful when inserting inline elements such as <br/> or <img/>.
    """
    branch: HtmlBranch = executor.current_branch  # type: ignore[assignment]
    branch.AppendNewline()

  @classmethod
  def _ParseClassNames(cls, class_names: str) -> list[str]:
    return [cn for cn in cls.__CLASS_NAME_SEPARATOR_REGEXP.split(class_names)
            if cn]
