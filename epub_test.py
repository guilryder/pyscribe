#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

from lxml import etree

from epub import *
from testutils import *


def ParseXml(xml_string):
  return etree.fromstring(xml_string.encode('utf8')).getroottree()

def XmlToString(elem_or_tree):
  # Strip out '\n' tails from all nodes.
  root_elem = elem_or_tree
  if hasattr(root_elem, 'getroot'):
    root_elem = root_elem.getroot()
  for elem in root_elem.iterdescendants():
    if elem.tail == '\n':
      elem.tail = None
  # Convert the tree to an XML string.
  return etree.tostring(elem_or_tree, pretty_print=True)

def CanonicalizeXml(xml_string):
  return XmlToString(ParseXml(xml_string))

def MakeExpectedXmlString(expected_body):
  return CanonicalizeXml(''.join((
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" ',
            '"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">',
        '<html xmlns="http://www.w3.org/1999/xhtml">',
          '<head>',
            '<meta http-equiv="Content-Type" ',
                  'content="application/xhtml+xml; charset=utf-8"/>',
          '</head>',
          '<body>',
            expected_body,
          '</body>',
        '</html>'
    )))


class AppendTextToXmlTest(TestCase):

  def check(self, text, initial_xml_string, expected_xml_string):
    initial_xml_string = '<root>' + initial_xml_string + '</root>'
    expected_xml_string = '<root>' + expected_xml_string + '</root>'
    tree = ParseXml(initial_xml_string)
    XhtmlBranch._AppendTextToXml(text, tree.find('//tail'), tree.find('//text'))
    self.assertTextEqual(CanonicalizeXml(expected_xml_string),
                         XmlToString(tree), 'output mismatch')

  def testNoText(self):
    self.check(None, 'text', 'text')

  def testEmptyText(self):
    self.check('', 'text', 'text')

  def testTailAndText(self):
    self.check('more',
               'before <tail>tail</tail> between <text>text</text> after',
               'before <tail>tail</tail> between more<text>text</text> after')

  def testTailOnly(self):
    self.check('more',
               'before <tail>tail</tail> after <tag/> last',
               'before <tail>tail</tail> after more<tag/> last')

  def testTextOnly(self):
    self.check('more',
               'before <text>text</text> after <tag/> last',
               'before <text>textmore</text> after <tag/> last')


class InlineXmlElementTest(TestCase):

  def check(self, initial_xml_string, expected_xml_string):
    tree = ParseXml(initial_xml_string)
    XhtmlBranch(parent=None)._InlineXmlElement(tree.find('//inline'))
    self.assertTextEqual(CanonicalizeXml(expected_xml_string),
                         XmlToString(tree))

  def testEmptyAlone(self):
    self.check('<root><inline></inline></root>',
               '<root></root>')

  def testEmptyNoPrevious(self):
    self.check('<root>before <inline></inline> after</root>',
               '<root>before  after</root>')

  def testEmptyWithPrevious(self):
    self.check('<root>first <prev>p</prev> before <inline></inline> after</root>',
               '<root>first <prev>p</prev> before  after</root>')

  def testOnlyText(self):
    self.check('<root>before <inline>inside</inline> after</root>',
               '<root>before inside after</root>')

  def testOneChildNoPrevious(self):
    self.check('<root>before <inline>1 <sub>2</sub> 3</inline> after</root>',
               '<root>before 1 <sub>2</sub> 3 after</root>')

  def testAttributesLost(self):
    self.assertRaises(
        InternalError,
        self.check, '<root><inline attr="value">inside</inline></root>', '')


class XhtmlBranchTest(BranchTestCase):

  def setUp(self):
    super(XhtmlBranchTest, self).setUp()
    self.branch = XhtmlBranch(parent=None)

  def assertRender(self, expected_xml_string):
    writer = self.FakeOutputFile(encoding='utf8')
    self.branch.writer = writer
    self.branch._Render(writer)
    self.assertTextEqual(
        MakeExpectedXmlString(expected_xml_string),
        CanonicalizeXml(writer.getvalue()))

  def testRender_empty(self):
    self.assertRender('')

  def testRender_text(self):
    self.branch.AppendText('one ')
    self.branch.AppendText('two ')
    self.branch.AppendText('three')
    self.assertRender('<p>one two three</p>')

  def testRender_htmlEscape(self):
    self.branch.AppendText('test " \' & <tag>')
    self.assertRender('<p>test " \' &amp; &lt;tag&gt;</p>')

  def testRender_unicode(self):
    self.branch.AppendText(test_unicode)
    self.assertRender(u'<p>{0}</p>'.format(test_unicode))

  def testRender_mix(self):
    self.PrepareMix(self.branch)
    self.assertRender(
        '<p>one</p><p>sub1</p><p>sub12</p><p>two</p><p>sub21</p><p>three</p>')

  def testRender_unattachedBranch(self):
    self.branch.CreateSubBranch()
    self.branch.AppendText('test')
    self.assertRender('<p>test</p>')


class EpubExecutionTestCase(ExecutionTestCase):

  def GetExecutionBranch(self, executor):
    return self.CreateBranch(executor, XhtmlBranch)

  def assertExecutionOutput(self, expected, actual, msg):
    actual_tree = ParseXml(actual)
    expected_text = MakeExpectedXmlString(expected)
    actual_text = XmlToString(actual_tree)

    if expected_text != actual_text:  # pragma: no cover
      # Mismatch: try to narrow the error message to <body>.
      namespace = 'http://www.w3.org/1999/xhtml'
      actual_body = actual_tree.find('//{' + namespace + '}body')
      if actual_body is not None:
        body_expected_tree = ParseXml(
            u'<body xmlns="{namespace}">{xml}</body>'.format(
                namespace=namespace, xml=expected))
        def FormatBody(node_or_tree):
          lines = XmlToString(node_or_tree).split('\n')
          if len(lines) >= 3:
            lines = lines[1:-1]
          return '\n'.join(lines)
        body_expected_text = FormatBody(body_expected_tree)
        body_actual_text = FormatBody(actual_body)
        if body_expected_text != body_actual_text:
          # The <body> elements differ: we have a discrepancy to show.
          (expected_text, actual_text) = (body_expected_text, body_actual_text)

    self.assertTextEqual(expected_text, actual_text, msg)


class GlobalExecutionTest(EpubExecutionTestCase):

  def testBranchType(self):
    self.assertExecution('$identity[$branch.type]', '<p>xhtml</p>')

  def testPara_simple(self):
    self.assertExecution(
        (
            'one\n\n',
            'two\n\n',
            'three',
        ), (
            '<p>one</p>',
            '<p>two</p>',
            '<p>three</p>',
        ))

  def testPara_removingEmptyElemWithAttributes(self):
    self.assertExecution(
        (
            'before\n',
            '$tag.class.add[current][test]\n\n',
            'after',
        ),
        messages=['/root:3: removing an empty element with attributes: ' +
                  '<p class="test"/>'])

  def testAutoParaCloseAtEnd(self):
    self.assertExecution('test', '<p>test</p>')

  def testElementOpenedAtEnd(self):
    self.assertExecution(
        '$tag.open[div][block]test',
        messages=['<unknown>:-1: element not closed in branch "root": <div>'])

  def testStripsInnerSpaces(self):
    self.assertExecution(
        '$tag.open[div][block] \n one two\n \n$tag.close[div]',
        '<div>one two</div>')


class NeutralTypographyTest(EpubExecutionTestCase):

  def InputHook(self, text):
    return '$typo.set[neutral]' + text

  def testFormatInteger_zero(self):
    self.assertEqual('0', NeutralTypography.FormatInteger(0))

  def testFormatInteger_small(self):
    self.assertEqual('123', NeutralTypography.FormatInteger(123))

  def testFormatInteger_negative(self):
    self.assertEqual('-12345678',
                     NeutralTypography.FormatInteger(-12345678))

  def testFormatInteger_positive(self):
    self.assertEqual('12345678',
                     NeutralTypography.FormatInteger(12345678))

  def testTypoInteger(self):
    self.assertExecution(u'before $typo.integer[-12345678] after',
                         u'<p>before -12345678 after</p>')

  def testAllSpecialChars(self):
    self.assertExecution(
        special_chars,
        u'<p>{0}</p>'.format(' '.join((
            u"% &amp; _ $ $ # #",
            u"a\xa0b",
            u"–c—",
            u"d…",
            u"«e»",
            u"« f »",
            u"'g'h'",
            u"i ! j: k ; l?",
            u"m!:;?",
        ))))

  def testPunctuationDouble_keepsSpaces(self):
    self.assertExecution(
        'one ! two : three ; four ? five , six .',
        u'<p>one ! two : three ; four ? five , six .</p>')

  def testPunctuationDouble_doesNotInsertSpaces(self):
    self.assertExecution(
        'one! two: three; four? five, six.',
        u'<p>one! two: three; four? five, six.</p>')

  def testPunctuationDouble_multipleInSequence(self):
    self.assertExecution('what !?;: wtf:;?!',
                         u'<p>what !?;: wtf:;?!</p>')

  def testGuillemets_keepsSpaces(self):
    self.assertExecution(u'one « two » three',
                         u'<p>one « two » three</p>')

  def testGuillemets_doesNotInsertSpaces(self):
    self.assertExecution(u'one «two» three',
                         u'<p>one «two» three</p>')

  def testApostrophes(self):
    self.assertExecution(u"'one' 'two' ' 'three'",
                         u"<p>'one' 'two' ' 'three'</p>")


class FrenchTypographyTest(EpubExecutionTestCase):

  def InputHook(self, text):
    return '$typo.set[french]' + text

  def testFormatInteger_zero(self):
    self.assertEqual(u'0', FrenchTypography.FormatInteger(0))

  def testFormatInteger_small(self):
    self.assertEqual(u'123', FrenchTypography.FormatInteger(123))

  def testFormatInteger_negative(self):
    self.assertEqual(u'\u201312\xa0345\xa0678',
                     FrenchTypography.FormatInteger(-12345678))

  def testFormatInteger_positive(self):
    self.assertEqual(u'12\xa0345\xa0678',
                     FrenchTypography.FormatInteger(12345678))

  def testTypoInteger(self):
    self.assertExecution(u'before $typo.integer[-12345678] after',
                         u'<p>before \u201312&#160;345&#160;678 after</p>')

  def testAllSpecialChars(self):
    self.assertExecution(
        special_chars,
        u'<p>{0}</p>'.format(' '.join((
            u"% &amp; _ $ $ # #",
            u"a\xa0b",
            u"–c—",
            u"d…",
            u"«\xa0e\xa0»",
            u"«\xa0f\xa0»",
            u"‘g’h’",
            u"i\xa0! j\xa0: k\xa0; l\xa0?",
            u"m\xa0!:;?",
        ))))

  def testPunctuationDouble_convertsSpaces(self):
    self.assertExecution(
        'one ! two : three ; four ? five , six .',
        u'<p>one&#160;! two&#160;: three&#160;; four&#160;? five , six .</p>')

  def testPunctuationDouble_insertsSpaces(self):
    self.assertExecution(
        'one! two: three; four? five, six.',
        u'<p>one&#160;! two&#160;: three&#160;; four&#160;? five, six.</p>')

  def testPunctuationDouble_insertsSpacesAfterInlineTag(self):
    self.assertExecution(
        (
            '$tag.open[span][inline]one$tag.close[span]! ',
            '$tag.open[span][inline]two$tag.close[span]: ',
            '$tag.open[span][inline]three$tag.close[span]; ',
            '$tag.open[span][inline]four$tag.close[span]? ',
        ), (
            '<p>',
                u'<span>one</span>&#160;! ',
                u'<span>two</span>&#160;: ',
                u'<span>three</span>&#160;; ',
                u'<span>four</span>&#160;?',
            '</p>',
        ))

  def testPunctuationDouble_insertsSpacesAfterBlockTag(self):
    self.assertExecution(
        (
            '$tag.open[div][block]one$tag.close[div]! ',
            '$tag.open[div][block]two$tag.close[div]',
                '$tag.open[div][block]:$tag.close[div]',
            '$tag.open[div][block]three$tag.close[div]; ',
            '$tag.open[div][block]four$tag.close[div]? ',
        ), (
            '<div>one</div><p>!</p>',
            '<div>two</div><div>:</div>',
            '<div>three</div><p>;</p>',
            '<div>four</div><p>?</p>',
        ))

  def testPunctuationDouble_convertsSpaceAfterEllipsis(self):
    self.assertExecution(
        'Err... ? Ah... ! Yes..... : here',
        u'<p>Err…&#160;? Ah…&#160;! Yes.....&#160;: here</p>')

  def testPunctuationDouble_insertsNoSpaceAfterEllipsis(self):
    self.assertExecution(
        'Err...? Ah...! Yes.....: here',
        u'<p>Err…? Ah…! Yes.....: here</p>')

  def testPunctuationDouble_multipleInSequence(self):
    self.assertExecution('what !?;: wtf:;?!',
                         u'<p>what&#160;!?;: wtf&#160;:;?!</p>')

  def testGuillemets_convertsSpaces(self):
    self.assertExecution(u'one « two » three',
                         u'<p>one «&#160;two&#160;» three</p>')

  def testGuillemets_insertsSpaces(self):
    self.assertExecution(u'one «two» three',
                         u'<p>one «&#160;two&#160;» three</p>')

  def testGuillemets_insertsSpacesAroundInlineTag(self):
    self.assertExecution(
        u'one «$tag.open[span][inline]two$tag.close[span]» three',
        u'<p>one «&#160;<span>two</span>&#160;» three</p>')

  def testGuillemets_insertsSpacesAroundBlockTag(self):
    self.assertExecution(
        u'one «$tag.open[div][block]two$tag.close[div]» three',
        u'<p>one «</p><div>two</div><p>» three</p>')

  def testApostrophes(self):
    self.assertExecution(u"'one' 'two' ' 'three'",
                         u"<p>‘one’ ‘two’ ‘ ‘three’</p>")

  def testTypoNewline(self):
    self.assertExecution("<<$typo.newline>>", u'<p>«»</p>')


class SimpleMacrosTest(EpubExecutionTestCase):

  def testPar_success(self):
    self.assertExecution('before$par`after', '<p>before</p><p>after</p>')

  def testPar_cannotOpen(self):
    self.assertExecution(
        '$tag.open[div][block]before$par`after$tag.close[div]',
        messages=['/root:1: $par: unable to open a new paragraph'])

  def testTypoSet_invalid(self):
    self.assertExecution(
        '$typo.set[invalid]',
        messages=['/root:1: $typo.set: unknown typography name: invalid; ' +
                  'expected one of: french, neutral'])

  def testTypoSet_multipleTimes(self):
    self.assertExecution(
        (
            '$typo.set[neutral]',
            '$typo.set[french]',
            'a?',
            '$typo.set[french]',
            '$typo.set[neutral]',
            'b?',
            '$typo.set[neutral]',
            '$typo.set[french]',
            'c?',
        ),
        u'<p>a\xa0?b?c\xa0?</p>')

  def testTypoName_default(self):
    self.assertExecution('$typo.name', '<p>neutral</p>')

  def testTypoSet_root(self):
    self.assertExecution(
        (
            '$typo.set[french]',
            '$typo.name',
        ),
        '<p>french</p>')

  def testTypo_inheritance(self):
    self.assertExecution(
        (
            '$branch.create.sub[one]',
            '$branch.write[one][$branch.create.sub[two]]',
            '$branch.write[two][$typo.set[neutral]]',
            '$typo.set[french]',
            'root $typo.name?',
            '$branch.append[one]',
            '$branch.write[one][one $typo.name?]',
            '$branch.write[one][$branch.append[two]]',
            '$branch.write[two][two $typo.name?]',
        ), (
            u'<p>root french\xa0?</p>',
            u'<p>one french\xa0?</p>',
            u'<p>two neutral?</p>',
        ))

  def testTypoInteger_invalid(self):
    self.assertExecution(
        '$typo.integer[invalid]',
        messages=['/root:1: $typo.integer: invalid integer: invalid'])


class TagOpenCloseTest(EpubExecutionTestCase):

  def testOnce(self):
    self.assertExecution(
        'before $tag.open[span][inline]inside$tag.close[span] after',
        '<p>before <span>inside</span> after</p>')

  def testTwice(self):
    self.assertExecution(
        (
            'before $tag.open[span][inline]inside$tag.close[span]',
            ' between ',
            '$tag.open[span][inline]inside 2$tag.close[span] after',
        ), (
            '<p>',
                'before <span>inside</span>',
                ' between ',
                '<span>inside 2</span> after',
            '</p>',
        ))

  def testNested(self):
    self.assertExecution(
        (
            'before ',
            '$tag.open[span][inline]',
                'one ',
                '$tag.open[span][inline]',
                    'nested',
                '$tag.close[span]',
                ' two',
            '$tag.close[span]',
            ' after',
        ),
        '<p>before <span>one <span>nested</span> two</span> after</p>')

  def testParaAndContainerNoParasInside(self):
    self.assertExecution(
        '$tag.open[h1][para]inside$tag.close[h1]',
        '<h1>inside</h1>')

  def testParaWithParasInside(self):
    self.assertExecution(
        (
            '$tag.open[h1][para]',
                'inside'
                '1\n',
                'inside 2\n',
            '$tag.close[h1]',
        ),
        messages=['/root:2: unable to open a new paragraph'])

  def testParaSurroundedWithParas(self):
    self.assertExecution(
        (
            'before',
            '$tag.open[h1][para]inside$tag.close[h1]',
            'after',
        ), (
            '<p>before</p>',
            '<h1>inside</h1>',
            '<p>after</p>',
        ))

  def testTagOpen_paraAndContainerAutoClosePara(self):
    self.assertExecution(
        (
            'before',
            '$tag.open[h1][para]inside$tag.close[h1]',
        ), (
            '<p>before</p>',
            '<h1>inside</h1>',
        ))

  def testTagOpen_inlineOpensPara(self):
    self.assertExecution(
        (
            'test\n\n',
            '$tag.open[span][inline]inside$tag.close[span]',
        ), (
            '<p>test</p>',
            '<p><span>inside</span></p>',
        ))

  def testTagOpen_blockAutoPara(self):
    self.assertExecution(
        (
            '$tag.open[div][block,autopara=span]'
            'one\n\n',
            'two',
            '$tag.close[div]',
        ), (
            '<div>',
                '<span>one</span>',
                '<span>two</span>',
            '</div>',
        ))

  def testTagOpen_invalidLevel(self):
    self.assertExecution(
        (
            '$tag.open[span][invalid]',
                'inside',
            '$tag.close[span]',
        ), messages=['/root:1: $tag.open: unknown level: invalid; ' +
                     'expected one of: autopara, block, inline, para.'])

  def testTagOpen_blockInInline(self):
    self.assertExecution(
        (
            '$tag.open[span][inline]',
                '$tag.open[div][block]',
                '$tag.close[div]',
            '$tag.close[div]',
        ), messages=['/root:2: $tag.open: impossible to open a non-inline tag ' +
                     'inside an inline tag'])

  def testTagClose_autoParaClose(self):
    self.assertExecution(
        '$tag.open[div][block,autopara=p]inside$tag.close[div]after',
        '<div><p>inside</p></div><p>after</p>')

  def testTagClose_tagNotFound(self):
    self.assertExecution(
        (
            '$tag.open[span][inline]',
                'inside',
            '$tag.close[div]',
        ), messages=['/root:3: $tag.close: ' +
                     'expected current tag to be <div>, got <span>'])

  def testTagClose_body(self):
    self.assertExecution(
        '$tag.close[body]',
        messages=['/root:1: $tag.close: ' +
                  'cannot close the root element of the branch'])

  def testTagClose_twoTagsAtOnce(self):
    self.assertExecution(
        (
            'before',
            '$tag.open[div][para]',
                'inside',
                '$tag.open[span][inline]',
                    'nested',
            '$tag.close[div]',
            'after',
        ), messages=['/root:6: $tag.close: ' +
                     'expected current tag to be <div>, got <span>'])

  def testTagClose_closeParaManually(self):
    self.assertExecution(
        (
                'before',
            '$tag.close[p]',
            '$tag.open[div][block]',
                'after',
            '$tag.close[div]',
            '$tag.open[div][block]',
                'next',
            '$tag.close[div]',
        ), (
            '<p>before</p>',
            '<div>after</div>',
            '<div>next</div>',
        ))

  def testTagClose_removingEmptyElemWithAttributes(self):
    self.assertExecution(
        (
            '$tag.open[div][block,autopara=p]',
            'text\n',
            '$tag.class.add[current][test]',
            '$tag.close[div]',
        ), messages=['/root:5: $tag.close: removing an empty element ' +
                     'with attributes: <p class="test"/>'])


class TagAttrSetTest(EpubExecutionTestCase):

  def testSimple(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
                '$tag.open[div][block]',
                    'before ',
                    '$tag.attr.set[<div>][name][value]',
                    'after',
                '$tag.close[div]',
            '$tag.close[div]',
        ),
        '<div><div name="value">before after</div></div>')

  def testOverwrite(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
                '$tag.attr.set[<div>][name][first]',
                'inside',
                '$tag.attr.set[<div>][name][second]',
            '$tag.close[div]',
        ),
        '<div name="second">inside</div>')

  def testBlankAttributeName(self):
    self.assertExecution(
        (
            '$tag.open[span][inline]',
                '$tag.attr.set[<span>][ \n \n ][value]',
            '$tag.close[span]',
        ), messages=['/root:2: $tag.attr.set: attribute name cannot be empty'])

  def testBlankValue(self):
    self.assertExecution(
        (
            '$tag.open[span][inline]',
                '$tag.attr.set[<span>][name][]',
                'inside',
            '$tag.close[span]',
        ),
        '<p><span name="">inside</span></p>')

  def testInvalidTarget(self):
    self.assertExecution(
        '$tag.attr.set[invalid][name][value]',
        messages=['/root:1: $tag.attr.set: invalid target: invalid'])

  def testTargetNotFound(self):
    self.assertExecution(
        '$tag.attr.set[<div>][name][value]',
        messages=['/root:1: $tag.attr.set: no element found for target: <div>'])


class ParTest(EpubExecutionTestCase):

  def testCloseAndOpen(self):
    self.assertExecution(
        'one\n\ntwo$par`three',
        '<p>one</p><p>two</p><p>three</p>')

  def testOpenOnly(self):
    self.assertExecution(
        '$par`one\n\n$par`two',
        '<p>one</p><p>two</p>')

  def testCannotOpen(self):
    self.assertExecution(
        '$tag.open[div][block]$par$tag.close[div]',
        messages=['/root:1: $par: unable to open a new paragraph'])


class TagClassAddTest(EpubExecutionTestCase):

  def testOnce(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
                '$tag.open[div][block]',
                    'before ',
                    '$tag.class.add[<div>][first]',
                    'after',
                '$tag.close[div]',
            '$tag.close[div]',
        ),
        '<div><div class="first">before after</div></div>')

  def testTwice(self):
    self.assertExecution(
        (
            '$tag.open[span][inline]',
                'one ',
                '$tag.class.add[<span>][first]',
                'two ',
                '$tag.class.add[<span>][second]',
                'three',
            '$tag.close[span]',
        ),
        '<p><span class="first second">one two three</span></p>')

  def testTwiceSame(self):
    self.assertExecution(
        (
            '$tag.open[span][inline]',
                '$tag.class.add[<span>][same]',
                '$tag.class.add[<span>][same]',
                'inside',
            '$tag.close[span]',
        ),
        '<p><span class="same">inside</span></p>')

  def testMultipleClassesAtOnce(self):
    self.assertExecution(
        (
            '$tag.open[span][inline]',
                '$tag.class.add[<span>][  one two\n one \n ]',
                '$tag.class.add[<span>][three\ntwo four]',
                'inside',
            '$tag.close[span]',
        ),
        '<p><span class="one two three four">inside</span></p>')

  def testTarget_current(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
                '$tag.open[div][block]',
                    'before ',
                    '$tag.class.add[current][first]',
                    'after',
                '$tag.close[div]',
            '$tag.close[div]',
        ),
        '<div><div class="first">before after</div></div>')

  def testTarget_para(self):
    self.assertExecution(
        (
            '$tag.open[div][para]',
                '$tag.open[span][inline]',
                    'before ',
                    '$tag.class.add[para][first]',
                    'after',
                '$tag.close[span]',
            '$tag.close[div]',
        ),
        '<div class="first"><span>before after</span></div>')

  def testTarget_previousAfterOpeningTag(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.open[span][inline]',
                'nested',
              '$tag.close[span]',
            '$tag.close[div]',
            '$tag.class.add[previous][test]',
        ),
        '<div class="test"><span>nested</span></div>')

  def testTarget_previousAfterClosingTag(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.open[span][inline]',
                'nested',
              '$tag.close[span]',
            '$tag.close[div]',
            '$tag.open[div][block]',
              '$tag.class.add[previous][test]',
              'after',
            '$tag.close[div]',
        ), (
            '<div class="test">',
                '<span>nested</span>',
            '</div>',
            '<div>',
                'after',
            '</div>',
        ))

  def testTarget_previousAfterClosingTwoTags(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
                'before',
                '$tag.open[span][inline]',
                    'inside',
                '$tag.close[span]',
            '$tag.close[div]',
            '$tag.open[div][block]',
                '$tag.open[span][inline]',
                    '$tag.class.add[previous][test]',
                    'after',
                '$tag.close[span]',
            '$tag.close[div]',
        ), (
            '<div class="test">',
                'before',
                '<span>inside</span>',
            '</div>',
            '<div>',
                '<span>after</span>',
            '</div>',
        ))

  def testTarget_previousNoneAvailable(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
                '$tag.class.add[previous][test]',
            '$tag.close[div]',
        ),
        messages=['/root:2: $tag.class.add: no previous element exists'])

  def testSpecialClassName(self):
    self.assertExecution(
        (
            '$tag.open[span][inline]',
                '$tag.class.add[<span>][&"]',
                'inside',
            '$tag.close[span]',
        ),
        '<p><span class="&amp;&quot;">inside</span></p>')

  def testBlankClassName(self):
    self.assertExecution(
        (
            '$tag.open[span][inline]',
                '$tag.class.add[<span>][ \n \n ]',
                'inside',
            '$tag.close[span]',
        ),
        '<p><span>inside</span></p>')

  def testTargetNotFound(self):
    self.assertExecution(
        '$tag.class.add[<div>][first]',
        messages=['/root:1: $tag.class.add: no element found for target: <div>'])

  def testInvalidTarget(self):
    self.assertExecution(
        '$tag.class.add[invalid][first]',
        messages=['/root:1: $tag.class.add: invalid target: invalid'])


if __name__ == '__main__':
  unittest.main()