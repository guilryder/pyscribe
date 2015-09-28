# -*- coding: utf-8 -*-
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

from abc import ABCMeta, abstractmethod
from lxml import etree
import re

import execution
from log import InternalError
from macros import *


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


def GetTagEmptyContents(tag_name):
  """
  Returns the text an empty element of the given tag should have.

  Returns None or '' depending on the tag.
  """
  return _VOID_TAGS_TO_NONE.get(tag_name, '')


class TagLevel:
  """
  Level of a tag, used automatically paragraphs on '\n\n'.
  """

  by_name = {}

  def __init__(self, name, is_para=False, is_auto=False, is_inline=False):
    self.is_para = is_para
    self.is_auto = is_auto
    self.is_inline = is_inline
    if name is not None:
      assert name not in self.by_name
      self.by_name[name] = self

# Block-level element.
# Can contain sub-blocks, paragraphs, and inline tags.
# Example: <body>, <div> sometimes.
TagLevel.BLOCK = TagLevel('block')

# Paragraph element to be closed manually.
# Can contain only inline tags.
# Example: <h1>, <ul>, <hr/>, <div> sometimes.
TagLevel.PARAGRAPH = TagLevel('para', is_para=True)

# Paragraph element that can be closed automatically.
# Can contain only inline tags.
# Example: <p>, <div> sometimes.
TagLevel.AUTO_PARAGRAPH = TagLevel('autopara', is_para=True, is_auto=True)

# Inline-level element. Inside a block or a paragraph.
# Can contain only inline tags.
# Example: <span>, <em>.
TagLevel.INLINE = TagLevel('inline', is_inline=True)


class XhtmlBranch(execution.Branch):
  """
  Branch for plain-text.

  Fields:
    sub_branches: (XhtmlBranch list) The direct sub-branches of this branch.
    __typography: (Typography|None) The typography set for this branch;
      if None, inherits the typography of the parent branch.
    __typography_context: (ExecutionContext) The context containing the macros
      of self.typography.
    __tree: (ElementTree) The tree of the branch. Set for root branches only.
    __root_elem: (Element) The root element of the branch. Cannot be closed by
      the branch. Ancestors and siblings of this element cannot be manipulated.
    __current_elem: (Element) The element currently open.
    __current_elem_info: (ElementInfo) Information about the current element.
    __text_accu: (string list) The current text accumulator of the branch.
      Used to merge consecutive text nodes created by AppendText.
    __line_tail: (string) The last chunk of text appended to the current
      inline tag, empty if the current paragraph has no text.
      Guaranteed to be non-empty if the current paragraph has some text.
    __text_sep: (string) The separator for AppendText to insert before the next
      chunk of non-whitespace text. Expected to be ' ' or NBSP.
      If empty, whitespaces are appended as is.
      If not empty, whitespaces are skipped.
  """

  class ElementInfo:
    """
    parent: (ElementInfo) The ElementInfo of the parent of the element.
    elem: (Element) The element.
    level: (TagLevel) The level of the element.
    auto_para_tag: (string) The tag to use for auto-paragraphs,
      None if the element does not support auto-paragraphs.
      Must be None for non-block elements.
    """
    def __init__(self, parent, elem, level, auto_para_tag=None):
      if auto_para_tag:
        assert level == TagLevel.BLOCK
        assert auto_para_tag not in _VOID_TAGS_TO_NONE
      self.parent = parent
      self.elem = elem
      self.level = level
      self.auto_para_tag = auto_para_tag

  __XML_HEADER = '<?xml version="1.0" encoding="%s"?>\n' % execution.ENCODING
  __XHTML_STUB = bytes("""\
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"
"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html>
<head>
<meta http-equiv="Content-Type"
      content="application/xhtml+xml; charset={encoding}"/>
</head>
</html>
""".format(encoding=execution.ENCODING), encoding='ascii')

  __AUTO_PARA_DELIMITER = re.compile(r'\n{2,}')
  __AUTO_PARA_TAG_DEFAULT = 'p'
  __TAG_TARGET_REGEXP = re.compile(r'\A\<(?P<tag>.+)\>\Z')

  type_name = 'xhtml'

  def __init__(self, *args, **kwargs):
    super(XhtmlBranch, self).__init__(*args, **kwargs)
    parent = self.parent
    self.sub_branches = []

    # Create the contexts tree.
    context = self.context
    if not parent:
      context.AddMacros(GetPublicMacros(Macros))
      context = execution.ExecutionContext(parent=context)
    self.__typography_context = context
    context = execution.ExecutionContext(parent=context)
    self.context = context

    # Set a typography for root branches.
    if parent:
      self.typography = None
    else:
      self.typography = TYPOGRAPHIES['neutral']

    if parent:
      # Sub-branch: create a placeholder element in the DOM.
      self.__root_elem = etree.Element('branch')
    else:
      # Root branch: start from the XHTML stub.
      self.__tree = etree.fromstring(self.__XHTML_STUB).getroottree()

      # Add a <body> element, take it as root.
      self.__root_elem = etree.SubElement(self.__tree.getroot(), 'body')

      # Create a sub-branch for the <head>.
      # TODO: give unique name to <head>
      self.__head_branch = XhtmlBranch(parent=self, name='head')
      self.__tree.find('head').append(self.__head_branch.__root_elem)
      self.__head_branch.attached = True

    self.__current_elem = self.__root_elem
    self.__current_elem_info = self.ElementInfo(
        parent=None, elem=self.__root_elem, level=TagLevel.BLOCK,
        auto_para_tag=self.__AUTO_PARA_TAG_DEFAULT)
    self.__text_accu = []
    self.__line_tail = ''
    self.__text_sep = ''

    self.AutoParaTryOpen()

  def GetTypography(self):
    branch = self
    while branch:
      typography = branch.__typography
      if typography:
        return typography
      branch = branch.parent
    return None  # pragma: no cover

  def SetTypography(self, typography):
    # pylint: disable=attribute-defined-outside-init
    self.__typography = typography
    self.__typography_context.macros = \
        typography and typography.context.macros or {}

  typography = property(GetTypography, SetTypography,
                        doc='(Typography) The typography rules.')

  def AppendText(self, text):
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
        raise InternalError('unable to open a new paragraph')
      if para:
        # Should never happen: at most one paragraph break per chunk of text.
        self.AppendLineText(para)

  __NBSP_TRIM_REGEXP = re.compile(r' *' + NBSP + r' *')
  __MULTIPLE_SPACES = re.compile(r' {2,}')

  def AppendLineText(self, text):
    """
    Appends text to the current line.

    Faster equivalent of AppendText() when the text to append is newlines-free.

    Args:
      text: (string) The non-empty string to append. Must not contain any '\n'.
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

  def AppendNewline(self):
    """
    Appends a line break to the current paragraph.

    Drops pending trailing spaces in the current line.
    Cancels the effect of RequireNonBreakingSpace() if it has just been called.

    This method is a noop after __InlineFlush().
    """
    self.__line_tail = self.__text_sep = ''

  def RequireNonBreakingSpace(self):
    """
    Requests a non-breaking space (NBSP) to be present.

    Inserts a new NBSP only if:
    * not at the beginning of a line
    * not at the end of a line
    * no NBSP is already present
    """
    tail = self.__line_tail
    if tail and tail[-1] != NBSP:
      self.__text_sep = NBSP

  def GetTailChar(self):
    """Returns the tail character of the current line."""
    tail = self.__text_sep or self.__line_tail
    return tail and tail[-1] or None

  def AutoParaTryOpen(self, except_tag=None):
    """
    Opens a new paragraph, if possible.

    Args:
      except_tag: (string) Does not open a new paragraph with this tag.

    Returns:
      (bool) Whether a tag was opened.
    """
    auto_para_tag = self.__current_elem_info.auto_para_tag
    if auto_para_tag and auto_para_tag != except_tag:
      self.OpenTag(auto_para_tag, level=TagLevel.AUTO_PARAGRAPH)
      return True
    else:
      return False

  def AutoParaTryClose(self):
    """
    Closes the current element if is an automatically-closeable paragraph.

    Returns:
      (bool) Whether a tag was closed.
    """
    if self.__current_elem_info.level == TagLevel.AUTO_PARAGRAPH:
      self.__CloseCurrentElement(discard_if_empty=True)
      return True
    else:
      return False

  def __FlushText(self):
    """
    Flushes the text accumulator to the branch.

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

  def OpenTag(self, tag, level, auto_para_tag=None):
    """
    Opens a new child tag in the current element, and makes it current.

    Args:
      tag: (string) The name of the tag, such as 'p' or 'h1'.
      level: (TagLevel) The level of the new element.
      auto_para_tag: (string) The tag to use for auto-paragraphs,
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
        raise InternalError(
            'impossible to open a non-inline tag inside an inline tag')

    elem = etree.SubElement(self.__current_elem, tag)
    self.__current_elem = elem

    # Create an ElementInfo for the new element.
    self.__current_elem_info = self.ElementInfo(
        parent=self.__current_elem_info, elem=elem, level=level,
        auto_para_tag=auto_para_tag)

    self.AutoParaTryOpen()

  def CloseTag(self, tag):
    """
    Closes the first ancestor element with a given tag name.

    Automatically closes intermediate paragraph elements as needed.
    Fails if encounters intermediate non-paragraph elements.

    Discards the paragraph elements closed that are empty.

    Args:
      tag: (string) The name of the tag to close.

    Raises:
      InternalError if the given tag cannot be found or closed.
    """
    while True:
      if self.__current_elem.tag == tag:
        # Tag match: close the element, open a new paragraph if appropriate.
        self.__CloseCurrentElement(discard_if_empty=False)
        self.AutoParaTryOpen(except_tag=tag)
        break
      # Tag mismatch: expect a paragraph, auto-close it.
      elif not self.AutoParaTryClose():
        # Not a pragraph: tag mismatch error.
        raise InternalError(
            'expected current tag to be <{expected_tag}>, got <{actual_tag}>',
            expected_tag=tag, actual_tag=self.__current_elem.tag)

  def __CloseCurrentElement(self, discard_if_empty):
    """
    Closes the current element.

    Args:
      discard_if_empty: (bool) Whether to remove the element if it's empty.

    Raises:
      InternalError if the given tag cannot be found or closed.
    """
    self.__FlushText()
    closed_elem = self.__current_elem
    if closed_elem == self.__root_elem:
      raise InternalError('cannot close the root element of the branch')

    # Pop the element.
    current_elem_info = self.__current_elem_info
    if not current_elem_info.level.is_inline:
      self.__line_tail = ''
    new_elem_info = current_elem_info.parent
    new_elem = new_elem_info.elem
    self.__current_elem_info = new_elem_info
    self.__current_elem = new_elem

    # If requested, discard the element if it's empty.
    if discard_if_empty and self._RemoveElementIfEmpty(closed_elem,
                                                       preserve_tail=False):
      closed_elem = None

    if not current_elem_info.level.is_inline and closed_elem is not None \
        and closed_elem.tail is None:
      closed_elem.tail = '\n'

  def RegisterTargetAction(self, unused_call_node, target, action):
    """
    Executes an action against a target element.

    The action may be executed later, asynchronously.

    Args:
      call_node: (CallNode) The macro being called.
      target: (string) The target given by the user.
      action: (Element -> void) The method to call with the targeted element.

    Raises:
      InternalError on error
    """
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
      elem_info_predicate = \
          lambda elem_info: elem_info != self.__current_elem_info != elem_info
    elif target == 'previous':
      # Previous element.
      elem_info = self.__current_elem_info
      while elem_info and elem_info.parent:
        prev_elem = elem_info.elem.getprevious()
        if prev_elem is not None:
          action(prev_elem)
          return
        elem_info = elem_info.parent
      raise InternalError('no previous element exists')
    elif target == 'para':
      # Deepest paragraph element.
      elem_info_predicate = lambda elem_info: elem_info.level.is_para
    else:
      # Deepest element with the given tag.
      tag = self.__TAG_TARGET_REGEXP.match(target)
      if not tag:
        raise InternalError('invalid target: {target}', target=target)
      tag = tag.group(1)
      elem_info_predicate = lambda elem_info: elem_info.elem.tag == tag

    # Execute the action against the deepest element matching the predicate.
    elem_info = self.__current_elem_info
    while elem_info and not elem_info_predicate(elem_info):
      elem_info = elem_info.parent
    if not elem_info:
      raise InternalError('no element found for target: {target}',
                          target=target)
    action(elem_info.elem)

  def CreateSubBranch(self):
    return XhtmlBranch(parent=self)

  def _AppendSubBranch(self, sub_branch):
    self.__FlushText()
    self.AutoParaTryClose()
    self.__current_elem.append(sub_branch.__root_elem)
    self.AutoParaTryOpen()

  def _Render(self, writer):
    self.__Finalize()

    # Post-process all elements.
    self.__PostProcessElementsRecurse(self.__tree.getroot())

    # Insert line breaks in <body>.
    body_elem = self.__root_elem
    if not body_elem.text:
      body_elem.text = '\n'
    body_elem.tail = '\n'

    writer.write(self.__XML_HEADER)
    writer.write(etree.tostring(self.__tree, encoding=str))
    writer.write('\n')

  def __Finalize(self):
    """
    Prepares the branch for rendering.

    Recurses in sub-branches.

    Raises:
      InternalError if an element is still open.
    """
    # Close paragraphs automatically. Fail if some elements are still open.
    self.__FlushText()
    while self.AutoParaTryClose():
      pass
    if self.__current_elem_info.parent:
      raise InternalError(
          'element not closed in branch "{branch.name}": <{elem.tag}>',
          branch=self, elem=self.__current_elem)

    # Inline the attached branches.
    for branch in self.sub_branches:
      if branch.attached:
        branch.__Finalize()
        self._InlineXmlElement(branch.__root_elem)

  @classmethod
  def __PostProcessElementsRecurse(cls, elem, *, strip_spaces=False):
    """
    Finalizes an element: strips spaces, processes "delete if empty".

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
        elem.text = (elem.text or '').strip(_STRIPPABLE) or \
            GetTagEmptyContents(elem.tag)

    # Process the "delete if empty" attribute.
    if elem.attrib.pop(_DELETE_IF_EMPTY_ATTR_NAME, None) == \
        _DELETE_IF_EMPTY_ATTR_VALUE:
      cls._RemoveElementIfEmpty(elem, preserve_tail=True, ignore_attribs=True)

    # Comment out the contents of <style> tags to disable escaping.
    if elem.tag == 'style' and elem.text:
      elem.append(etree.Comment('\n{}\n'.format(elem.text)))
      elem.text = None

  @classmethod
  def _RemoveElementIfEmpty(cls, elem,
                            preserve_tail, ignore_attribs=False):
    """
    Removes an element if it is empty: no text, no children.

    Args:
      elem: (Element) The element to remove.
      preserve_tail: (bool) Whether to preserve element tail, if any, by
        appending it to the before element.
      ignore_attribs: (bool) Whether to remove the element even if it has
        attributes; fails if false and the element has attributes.

    Returns:
      (bool) Whether the element was empty and has been removed.
    """
    if (elem.text and elem.text.strip(_STRIPPABLE)) or len(elem):
      return False

    # Append the placeholder tail to the before element,
    # then delete the element.
    parent_elem = elem.getparent()
    if preserve_tail:
      cls._AppendTextToXml((elem.tail or '').strip(_STRIPPABLE) or None,
                           tail_elem=elem.getprevious(),
                           text_elem=parent_elem)
    parent_elem.remove(elem)

    # Fail if the element has attributes.
    if not ignore_attribs and elem.attrib and \
        elem.attrib.get(_DELETE_IF_EMPTY_ATTR_NAME, None) != \
            _DELETE_IF_EMPTY_ATTR_VALUE:
      elem.text = ''
      raise InternalError(
          'removing an empty element with attributes: {elem}',
          elem=etree.tostring(elem, encoding='unicode'))
    return True

  @staticmethod
  def _AppendTextToXml(text, tail_elem=None, text_elem=None):
    """
    Appends text to an XML element.

    Appends the text to tail_elem tail if valid, else to text_elem text.

    Args:
      tail_elem: (Element) If not None, appends to this element's tail.
      text_elem: (Element) If tail_elem is None, appends to this element's text.
      text: (string) The text to append, not XML-escaped.
    """
    if text:
      if tail_elem is not None:
        tail_elem.tail = (tail_elem.tail or '') + text
      else:
        text_elem.text = (text_elem.text or '') + text

  @classmethod
  def _InlineXmlElement(cls, elem):
    """
    Replaces an lxml Element with its contents.

    Handles text and tail properly.
    The attributes of the element are lost.

    Args:
      elem: (Element) The element to inline.
    """
    parent_elem = elem.getparent()
    previous_elem = elem.getprevious()

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


class Typography(metaclass=ABCMeta):

  macros_container = None

  def __init__(self):
    super(Typography, self).__init__()
    assert self.name  # pylint: disable=no-member
    if self.macros_container is None:
      self.macros_container = self
    self.context = execution.ExecutionContext(parent=None)
    self.context.AddMacros(GetPublicMacros(self.macros_container))

  @abstractmethod
  def FormatNumber(self, number):  # pragma: no cover
    """
    Formats a number to a string.

    Args:
      number: (string) The number to format. Prefixed with '-' if negative.
        Can use '.' or ',' as decimal separator.

    Returns:
      (string) The formatted number.
    """
    pass


class NeutralTypography(Typography):
  """Language-neutral typography rules."""

  name = 'neutral'
  macros_container = __import__('builtin_macros').SpecialCharacters

  @staticmethod
  def FormatNumber(number):  # pylint: disable=arguments-differ
    return number


class FrenchTypography(Typography):
  """French-specific typography rules."""

  name = 'french'

  @staticmethod
  def FormatNumber(number):  # pylint: disable=arguments-differ
    # Separate thoushands with a non-breaking space.
    (sign, before_decimal, decimal_sep, after_decimal) = \
        _NUMBER_REGEXP.match(number).groups()

    # Use an en-dash as minus sign.
    if sign == '-':
      sign = '–'
    text = sign

    text += NBSP.join(
        reversed([before_decimal[max(0, group_end-3):group_end]
                  for group_end in range(len(before_decimal), 0, -3)]))

    if decimal_sep:
      text += decimal_sep
      text += NBSP.join(
          [after_decimal[group_start:group_start+3]
           for group_start in range(0, len(after_decimal), 3)])

    return text

  TextBacktick = StaticAppendTextCallback("‘", public_name='text.backtick')
  TextApostrophe = StaticAppendTextCallback("’", public_name='text.apostrophe')

  @staticmethod
  @macro(public_name='text.guillemet.open')
  def RuleGuillemetOpen(executor, unused_call_node):
    branch = executor.current_branch
    branch.AppendLineText('«')
    branch.RequireNonBreakingSpace()

  @staticmethod
  @macro(public_name='text.guillemet.close')
  def RuleGuillemetClose(executor, unused_call_node):
    branch = executor.current_branch
    branch.RequireNonBreakingSpace()
    branch.AppendLineText('»')

  @staticmethod
  @macro(public_name='text.punctuation.double', args_signature='contents')
  def RulePunctuationDouble(executor, unused_call_node, contents):
    if not contents:
      return
    branch = executor.current_branch
    if branch.GetTailChar() not in ('…', '.'):
      branch.RequireNonBreakingSpace()
    branch.AppendLineText(contents)


TYPOGRAPHIES = \
    dict((typography_type.name, typography_type())
         for typography_type in (NeutralTypography, FrenchTypography))


class Macros:

  __AUTO_PARA_LEVEL_REGEXP = \
      re.compile(r'\Ablock,autopara=(?P<auto_para_tag>.+)\Z')
  __CLASS_NAME_SEPARATOR_REGEXP = re.compile(r'\s+')

  @staticmethod
  @macro(public_name='par')
  def Par(executor, unused_call_node):
    """Tries to close/open a new automatic paragraph."""
    branch = executor.current_branch
    branch.AutoParaTryClose()
    if not branch.AutoParaTryOpen():
      raise InternalError('unable to open a new paragraph')

  @staticmethod
  @macro(public_name='tag.open', args_signature='tag,level_name')
  def TagOpen(executor, call_node, tag, level_name):
    """
    Opens a new XML tag.

    Args:
      tag: The name of the tag to open, such as 'span' or 'h1'.
      level_name: The name of the level of the tag (see TagLevel).
    """

    # Parse the level name.
    autoparablock_match = Macros.__AUTO_PARA_LEVEL_REGEXP.match(level_name)
    if autoparablock_match:
      level = TagLevel.BLOCK
      auto_para_tag = autoparablock_match.group('auto_para_tag')
      if auto_para_tag in _VOID_TAGS_TO_NONE:
        executor.MacroFatalError(
            call_node, 'cannot use void tag as autopara: <{tag}>',
            tag=auto_para_tag)
    else:
      level = TagLevel.by_name.get(level_name)
      auto_para_tag = None
    if not level:
      executor.MacroFatalError(
          call_node, 'unknown level: {level}; expected one of: {known}.',
          level=level_name, known=', '.join(sorted(TagLevel.by_name)))

    executor.current_branch.OpenTag(tag, level, auto_para_tag)

  @staticmethod
  @macro(public_name='tag.close', args_signature='tag')
  def TagClose(executor, unused_call_node, tag):
    """
    Closes the current XML tag.

    Automatically closes intermediate paragraph elements as needed.
    Fails if encounters intermediate non-paragraph elements.

    Discards the paragraph elements closed that are empty.

    Args:
      tag: The name of the tag to close.
    """
    executor.current_branch.CloseTag(tag)

  @staticmethod
  @macro(public_name='tag.delete.ifempty', args_signature='target')
  def TagDeleteIfEmpty(executor, call_node, target):
    """
    Delete the specified element if it is empty: no text, no children.

    Ignores attributes.

    The check and possible deletion happen at rendering time, not immediately.

    Args:
      target: The element to configure.
    """
    Macros.__TagAttrSet(executor, call_node, target,
                        _DELETE_IF_EMPTY_ATTR_NAME, _DELETE_IF_EMPTY_ATTR_VALUE)

  @staticmethod
  @macro(public_name='tag.attr.set', args_signature='target,attr_name,value')
  def TagAttrSet(executor, call_node, target, attr_name, value):
    """
    Sets an attribute in an element.

    Args:
      target: The element to set the attribute into.
      attr_name: The name of the attribute.
      value: The value of the attribute.
    """
    Macros.__TagAttrSet(executor, call_node, target, attr_name, value)

  @staticmethod
  def __TagAttrSet(executor, call_node, target, attr_name, value):
    if not attr_name.strip():
      executor.MacroFatalError(call_node, 'attribute name cannot be empty')

    def Action(elem):
      elem.set(attr_name, value)

    executor.current_branch.RegisterTargetAction(call_node, target, Action)

  @staticmethod
  @macro(public_name='tag.class.add', args_signature='target,class_name')
  def TagClassAdd(executor, call_node, target, class_name):
    """
    Adds a CSS class to an element.

    Args:
      target: The element to add the class to.
      class_name: The name of the CSS class; does nothing if empty.
    """
    class_names = Macros._ParseClassNames(class_name)

    def Action(elem):
      if not class_names:
        return

      # Append the class name to the 'class' attribute.
      # Preserve ordering (meaningful in CSS).
      final_class_names = Macros._ParseClassNames(elem.get('class', ''))
      for class_name in class_names:
        if class_name not in final_class_names:
          final_class_names.append(class_name)
      elem.set('class', ' '.join(final_class_names))

    executor.current_branch.RegisterTargetAction(call_node, target, Action)

  @staticmethod
  @macro(public_name='typo.name', text_compatible=True)
  def TypoName(executor, unused_call_node):
    """Prints the name of the current typography."""
    executor.AppendText(executor.current_branch.typography.name)

  @staticmethod
  @macro(public_name='typo.set', args_signature='typo_name')
  def TypoSet(executor, call_node, typo_name):
    """
    Sets the typography rules to apply in the current branch.

    Args:
      typo_name: The name of the typography rules, see TYPOGRAPHIES.
    """
    typography = TYPOGRAPHIES.get(typo_name, None)
    if not typography:
      executor.MacroFatalError(
          call_node,
          'unknown typography name: {typo_name}; expected one of: {known}',
          typo_name=typo_name, known=', '.join(sorted(TYPOGRAPHIES)))
    executor.current_branch.typography = typography

  @staticmethod
  @macro(public_name='typo.number', args_signature='number')
  def TypoNumber(executor, call_node, number):
    """
    Formats a number according to the current typography rules.
    """
    # Reject invalid values.
    if not _NUMBER_REGEXP.match(number):
      executor.MacroFatalError(
          call_node, 'invalid integer: {number}', number=number)
    text = executor.current_branch.root.typography.FormatNumber(number)
    executor.AppendText(text)

  @staticmethod
  @macro(public_name='typo.newline')
  def TypoNewline(executor, unused_call_node):
    """
    Prepares the typography engine for a new line.

    Concrete effect: ensures that the typographic spaces required after some
    characters are effectively inserted before the line is broken, instead of
    being dropped.

    Useful when inserting inline elements such as <br/> or <img/>.
    """
    executor.current_branch.AppendNewline()

  @classmethod
  def _ParseClassNames(cls, class_names):
    return [cn for cn in cls.__CLASS_NAME_SEPARATOR_REGEXP.split(class_names)
            if cn]
