#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

from lxml import etree

import html_format
import log
import testutils


_STUB_PREFIX1 = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<html xmlns="http://www.w3.org/1999/xhtml"'
         ' xmlns:epub="http://www.idpf.org/2007/ops">\n'
      '<head>\n'
        '<meta http-equiv="Content-Type" '
              'content="application/xhtml+xml; charset=utf-8"/>\n'
)

_STUB_PREFIX2 = (
      '</head>\n'
      '<body>\n'
)

_STUB_PREFIX = _STUB_PREFIX1 + _STUB_PREFIX2

_STUB_SUFFIX = (
      '\n</body>\n'
    '</html>\n'
)


def ParseXml(xml_string):
  return etree.fromstring(xml_string.encode()).getroottree()

def XmlToString(elem_or_tree):
  return etree.tostring(elem_or_tree, encoding=str)

def MakeExpectedXmlString(expected_body, *,
                          prefix=_STUB_PREFIX, suffix=_STUB_SUFFIX):
  result = prefix + expected_body + suffix
  result = result.replace('<body>\n\n</body>', '<body>\n</body>')
  return result


class AppendTextToXmlTest(testutils.TestCase):

  def check(self, text, initial_xml_string, expected_xml_string):
    initial_xml_string = '<root>' + initial_xml_string + '</root>'
    expected_xml_string = '<root>' + expected_xml_string + '</root>'
    tree = ParseXml(initial_xml_string)
    html_format.HtmlBranch._AppendTextToXml(text,
                                            tail_elem=tree.find('.//tail'),
                                            text_elem=tree.find('.//text'))
    self.assertTextEqual(XmlToString(tree),
                         expected_xml_string,
                         'output mismatch')

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


class InlineXmlElementTest(testutils.TestCase):

  def check(self, initial_xml_string, expected_xml_string):
    tree = ParseXml(initial_xml_string)
    html_format.HtmlBranch(parent=None)._InlineXmlElement(
        tree.find('.//inline'))
    self.assertTextEqual(XmlToString(tree), expected_xml_string)

  def testEmptyAlone(self):
    self.check('<root><inline></inline></root>',
               '<root></root>')

  def testEmptyNoPrevious(self):
    self.check('<root>before <inline></inline> after</root>',
               '<root>before  after</root>')

  def testEmptyWithPrevious(self):
    self.check(
        '<root>first <prev>p</prev> before <inline></inline> after</root>',
        '<root>first <prev>p</prev> before  after</root>')

  def testOnlyText(self):
    self.check('<root>before <inline>inside</inline> after</root>',
               '<root>before inside after</root>')

  def testOneChildNoPrevious(self):
    self.check('<root>before <inline>1 <sub>2</sub> 3</inline> after</root>',
               '<root>before 1 <sub>2</sub> 3 after</root>')

  def testAttributesLost(self):
    with self.assertRaises(log.NodeError):
      self.check('<root><inline attr="value">inside</inline></root>', '')


class HtmlBranchTest(testutils.BranchTestCase):

  def setUp(self):
    super().setUp()
    self.branch = html_format.HtmlBranch(parent=None)

  def assertRender(self, expected_xml_string):
    with self.FakeOutputFile() as writer:
      self.branch.writer = writer
      self.branch._Render(writer)
      self.assertTextEqual(writer.getvalue(),
                           MakeExpectedXmlString(expected_xml_string))

  def testRender_htmlBoilerplate(self):
    self.branch.AppendText('test')
    self.assertRender('<p>test</p>')

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
    self.branch.AppendText(testutils.TEST_UNICODE)
    self.assertRender(f'<p>{testutils.TEST_UNICODE}</p>')

  def testRender_mix(self):
    self.PrepareMix(self.branch)
    self.assertRender(
        '\n'.join((
            '<p>one</p>',
            '<p>sub1</p>',
            '<p>sub12</p>',
            '<p>two</p>',
            '<p>sub21</p>',
            '<p>three</p>',
        )))

  def testRender_unattachedBranch(self):
    self.branch.CreateSubBranch()
    self.branch.AppendText('test')
    self.assertRender('<p>test</p>')

  def testAppendText_trimsSpaces(self):
    self.branch.AppendText('   a   ')
    self.branch.AppendText('  b  ')
    self.branch.AppendText(' c ')
    self.branch.AppendText('   d')
    self.branch.AppendText('e   ')
    self.branch.AppendText('f')
    self.branch.AppendText(' ')
    self.branch.AppendText('g ')
    self.branch.AppendText(' ')
    self.branch.AppendText('h')
    self.assertRender('<p>a b c de f g h</p>')

  def testAppendText_mergesSpacesIntoNbsp(self):
    self.branch.AppendText('  a  ')
    self.branch.AppendText('  \xa0  \xa0b \xa0 ')
    self.branch.AppendText('\xa0c\xa0')
    self.branch.AppendText('d  \xa0')
    self.branch.AppendText('  e')
    self.assertRender('<p>a\xa0\xa0b\xa0\xa0c\xa0d\xa0e</p>')


class HtmlExecutionTestCase(testutils.ExecutionTestCase):

  @classmethod
  def MakeExpectedString(cls, text):
    return MakeExpectedXmlString(text)

  def GetExecutionBranch(self, executor):
    return self.CreateBranch(executor, html_format.HtmlBranch)

  def assertExecutionOutput(self, actual, expected, msg):
    # If possible, strip out the stub to clarify error messages.
    if actual.startswith(_STUB_PREFIX) and actual.endswith(_STUB_SUFFIX):
      self.assertTextEqual(actual[len(_STUB_PREFIX):-len(_STUB_SUFFIX)],
                           expected, msg)

    self.assertTextEqual(actual, self.MakeExpectedString(expected), msg)


class GlobalExecutionTest(HtmlExecutionTestCase):

  def testBranchType(self):
    self.assertExecution('$identity[$branch.type]', '<p>html</p>')

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

  def testPara_emptyOnlyAttributes_fails(self):
    self.assertExecution(
        (
            'before\n\n'
            '$tag.class.add[current][test]\n\n'
            'after'
        ),
        messages=['/root:3: removing an empty element with attributes: ' +
                  '<p class="test"></p>'])

  def testPara_emptyOnlyAttributes_deleteIfEmpty(self):
    self.assertExecution(
        (
            'before\n\n',
            '$tag.delete.ifempty[current]$tag.class.add[current][test]\n\n',
            'after',
        ), (
            '<p>before</p>',
            '<p>after</p>',
        ))

  def testAutoParaCloseAtEnd(self):
    self.assertExecution('test', '<p>test</p>')

  def testElementOpenedAtEnd(self):
    self.assertExecution(
        '$tag.open[div][block]test',
        messages=['element not closed in branch "root": <div>'])

  def testStripsInnerSpaces_textInside(self):
    self.assertExecution(
        '$tag.open[div][block] \n one two\n \n$tag.close[div]',
        '<div>one two</div>')

  def testStripsInnerSpaces_whitespace(self):
    self.assertExecution(
        '$tag.open[div][block] \n  \n $tag.close[div]',
        '<div></div>')

  def testStripsInnerSpaces_nbsp(self):
    self.assertExecution(
        '$tag.open[div][block] \n ~~ ~ \n $tag.close[div]',
        '<div>\xa0\xa0\xa0</div>')

  def testSpacesAroundMacroThenAnotherMacro(self):
    self.assertExecution("a $empty b$text.dollar",
                         "<p>a b$</p>")

  def testNbspThenSpaceThenOpenInlineTag(self):
    self.assertExecution("a~ $tag.open[span][inline]inside$tag.close[span]",
                         "<p>a\xa0<span>inside</span></p>")

  def testNbspThenSpaceThenOpenBlockTag(self):
    self.assertExecution("a~ $tag.open[div][block]inside$tag.close[div]",
                         "<p>a\xa0</p>\n<div>inside</div>")

  def testNbspThenCloseTagThenSpace(self):
    self.assertExecution("$tag.open[span][inline]inside~$tag.close[span] test",
                         "<p><span>inside\xa0</span>test</p>")

  def testEmptyTags_nonVoid(self):
    self.assertExecution(
        (
            '$tag.open[div][block]$tag.close[div]',
            '$tag.open[span][block]$tag.close[span]',
            '$tag.open[blockquote][block]$tag.close[blockquote]',
            '$tag.open[i][block]$tag.close[i]',
        ), (
            '<div></div>',
            '<span></span>',
            '<blockquote></blockquote>',
            '<i></i>',
        ))

  def testEmptyTags_void(self):
    self.assertExecution(
        (
            '$tag.open[hr][block]$tag.close[hr]',
            '$tag.open[br][block]$tag.close[br]',
            '$tag.open[wbr][block]$tag.close[wbr]',
        ), (
            '<hr/>',
            '<br/>',
            '<wbr/>',
        ))

  def testIncludeText(self):
    included = '\n'.join((
        '$$invalid',
        '$foo',
        '^',
        testutils.TEST_UNICODE,
    ))
    self.assertExecution(
        {
            '/root': 'roota $include.text[hello.txt] rootb',
            '/hello.txt': included + testutils.SPECIAL_CHARS,
        },
        f'<p>roota {included}{testutils.SPECIAL_CHARS_AS_HTML} rootb</p>')


class StructureExecutionTest(HtmlExecutionTestCase):

  @classmethod
  def MakeExpectedString(cls, text):
    return MakeExpectedXmlString(text,
                                 prefix=_STUB_PREFIX1, suffix=_STUB_SUFFIX)

  @staticmethod
  def __MakeExpected(header_lines, footer):
    return ''.join(('\n'.join(header_lines), '\n', _STUB_PREFIX2, footer))

  def testHeadBranch(self):
    self.assertExecution(
        (
            '$branch.write[head][',
              '$tag.open[title][para]My Title$tag.close[title]',
            ']',
            'My body',
        ),
        self.__MakeExpected(('<title>My Title</title>',), '<p>My body</p>'))

  def testStyle_notEscaped(self):
    self.assertExecution(
        (
            '$branch.write[head][',
              '$tag.open[title][para]My & Title$tag.close[title]',
              '$tag.open[style][para]h1 > div { "blah" }$tag.close[style]',
            ']',
            'My & body',
        ),
        self.__MakeExpected(
            (
                '<title>My &amp; Title</title>',
                '<style><!--',
                'h1 > div { "blah" }',
                '--></style>',
            ), '<p>My &amp; body</p>'))

  def testStyle_includedCssFile(self):
    self.assertExecution(
        {
            '/root': (
                '$branch.write[head][',
                  '$tag.open[style][para]',
                  '$tag.body.raw[$include.text[dummy.css]]',
                  '$tag.close[style]',
                ']',
                'test',
            ),
            '/dummy.css': '\n'.join((
                'p { margin: 0; }',
                '',
                'img { border: 0; }',
                '/* Special characters: \' " ` \'\' < > ? : ! */',
            )),
        },
        self.__MakeExpected(
            (
                '<style><!--',
                'p { margin: 0; }',
                '',
                'img { border: 0; }',
                '/* Special characters: \' " ` \'\' < > ? : ! */',
                '--></style>',
            ), '<p>test</p>'))


class NeutralTypographyTest(HtmlExecutionTestCase):

  typo = html_format.NeutralTypography

  def InputHook(self, text):
    return '$typo.set[neutral]' + text

  def testFormatNumber_invalid(self):
    self.assertEqual(self.typo.FormatNumber('invalid'), 'invalid')

  def testFormatNumber_zero(self):
    self.assertEqual(self.typo.FormatNumber('0'), '0')

  def testFormatNumber_small(self):
    self.assertEqual(self.typo.FormatNumber('123'), '123')

  def testFormatNumber_negative(self):
    self.assertEqual(self.typo.FormatNumber('-12345678'), '-12345678')

  def testFormatNumber_positive(self):
    self.assertEqual(self.typo.FormatNumber('+12345678'), '+12345678',)

  def testTypoNumber(self):
    self.assertExecution('before $typo.number[-12345678] after',
                         '<p>before -12345678 after</p>')

  def testAllSpecialChars(self):
    self.assertExecution(
        testutils.SPECIAL_CHARS,
        f'<p>{testutils.TYPO_TO_SPECIAL_CHARS_AS_HTML["neutral"]}</p>')

  def testPunctuationDouble_keepsSpaces(self):
    self.assertExecution(
        'one ! two : three ; four ? five , six .',
        '<p>one ! two : three ; four ? five , six .</p>')

  def testPunctuationDouble_doesNotInsertSpaces(self):
    self.assertExecution(
        'one! two: three; four? five, six.',
        '<p>one! two: three; four? five, six.</p>')

  def testPunctuationDouble_multipleInSequence(self):
    self.assertExecution('what !?;: wtf:;?!',
                         '<p>what !?;: wtf:;?!</p>')

  def testPunctuationDouble_afterNbsp(self):
    self.assertExecution('dialog~!',
                         '<p>dialog\xa0!</p>')

  def testGuillemets_keepsSpaces(self):
    self.assertExecution('one « two » three',
                         '<p>one « two » three</p>')

  def testGuillemets_doesNotInsertSpaces(self):
    self.assertExecution('one «two» three',
                         '<p>one «two» three</p>')

  def testGuillemets_aroundNbsp(self):
    self.assertExecution('«~inside~»',
                         '<p>«\xa0inside\xa0»</p>')

  def testBackticksApostrophes(self):
    self.assertExecution("`one' 'two` th'ree fo`ur `' ' `",
                         "<p>`one' 'two` th'ree fo`ur `' ' `</p>")

  def testNbsp_inside(self):
    self.assertExecution(
        'a~~b  ~~  c~~  ~~d  ~~e~~  f',
        '<p>a\xa0\xa0b\xa0\xa0c\xa0\xa0\xa0\xa0d\xa0\xa0e\xa0\xa0f</p>')

  def testNbsp_prefix(self):
    self.assertExecution(
        '~~~a',
        '<p>\xa0\xa0\xa0a</p>')

  def testNbsp_suffix(self):
    self.assertExecution(
        'a~~~',
        '<p>a\xa0\xa0\xa0</p>')


class EnglishTypographyTest(HtmlExecutionTestCase):

  typo = html_format.EnglishTypography

  def InputHook(self, text):
    return '$typo.set[english]' + text

  def testFormatNumber_invalid(self):
    self.assertEqual(self.typo.FormatNumber('invalid'), 'invalid')

  def testFormatNumber_zero(self):
    self.assertEqual(self.typo.FormatNumber('0'), '0')

  def testFormatNumber_short(self):
    self.assertEqual(self.typo.FormatNumber('123'), '123')

  def testFormatNumber_long(self):
    self.assertEqual(self.typo.FormatNumber('12345678'),
                     '12,345,678')
    self.assertEqual(self.typo.FormatNumber('123456'),
                     '123,456')

  def testFormatNumber_negative(self):
    self.assertEqual(self.typo.FormatNumber('-1234,5678'),
                     '\u20131,234,567,8')

  def testFormatNumber_positive(self):
    self.assertEqual(self.typo.FormatNumber('+1234.5678'),
                     '+1,234.567,8')

  def testFormatNumber_decimalShort(self):
    self.assertEqual(self.typo.FormatNumber('3.5'), '3.5')

  def testFormatNumber_decimalLong(self):
    self.assertEqual(self.typo.FormatNumber('3.567890'),
                     '3.567,890')
    self.assertEqual(self.typo.FormatNumber('3,5678901'),
                     '3,567,890,1')

  def testFormatNumber_decimalOnly(self):
    self.assertEqual(self.typo.FormatNumber('.5'), '.5')
    self.assertEqual(self.typo.FormatNumber(',123'), ',123')
    self.assertEqual(self.typo.FormatNumber('-.5'), '\u2013.5')

  def testTypoNumber(self):
    self.assertExecution('before $typo.number[-12345678] after',
                         '<p>before \u201312,345,678 after</p>')

  def testAllSpecialChars(self):
    self.assertExecution(
        testutils.SPECIAL_CHARS,
        f'<p>{testutils.TYPO_TO_SPECIAL_CHARS_AS_HTML["english"]}</p>')

  def testPunctuationDouble_preservesSpaces(self):
    self.assertExecution(
        'one ! two : three ; four ? five , six .',
        '<p>one ! two : three ; four ? five , six .</p>')

  def testPunctuationDouble_doesNotInsertSpaces(self):
    self.assertExecution(
        'one! two: three; four? five, six.',
        '<p>one! two: three; four? five, six.</p>')

  def testPunctuationDouble_doesNotInsertSpacesAfterInlineTag(self):
    self.assertExecution(
        (
            '$tag.open[span][inline]one$tag.close[span]! ',
            '$tag.open[span][inline]two$tag.close[span]: ',
            '$tag.open[span][inline]three$tag.close[span]; ',
            '$tag.open[span][inline]four$tag.close[span]? ',
        ), (
            '<p>'
              '<span>one</span>! '
              '<span>two</span>: '
              '<span>three</span>; '
              '<span>four</span>?'
            '</p>'
        ))

  def testPunctuationDouble_insertsNoSpacesAfterBlockTag(self):
    self.assertExecution(
        (
            '$tag.open[div][block]one$tag.close[div]! ',
            '$tag.open[div][block]two$tag.close[div]',
              '$tag.open[div][block]:$tag.close[div]',
            '$tag.open[div][block]three$tag.close[div]; ',
            '$tag.open[div][block]four$tag.close[div]? ',
        ), (
            '<div>one</div>', '<p>!</p>',
            '<div>two</div>', '<div>:</div>',
            '<div>three</div>', '<p>;</p>',
            '<div>four</div>', '<p>?</p>',
        ))

  def testPunctuationDouble_preservesSpaceAfterEllipsis(self):
    self.assertExecution(
        'Err... ? Ah... ! Yes..... : here',
        '<p>Err… ? Ah… ! Yes..... : here</p>')

  def testPunctuationDouble_insertsNoSpaceAfterEllipsis(self):
    self.assertExecution(
        'Err...? Ah...! Yes.....: here',
        '<p>Err…? Ah…! Yes.....: here</p>')

  def testPunctuationDouble_multipleInSequence(self):
    self.assertExecution('what !?;: wtf:;?!',
                         '<p>what !?;: wtf:;?!</p>')

  def testPunctuationDouble_afterNbsp(self):
    self.assertExecution('$macro.new[test][dialog~]$test?',
                         '<p>dialog\xa0?</p>')

  def testPunctuationDouble_afterNbspAndSpace(self):
    self.assertExecution('$macro.new[test][dialog~]$test ?',
                         '<p>dialog\xa0?</p>')

  def testPunctuationDouble_cornerCases(self):
    self.assertExecution(
        (
            'A', '$text.punctuation.double[]',
            'B', '$text.punctuation.double[ ]',
            'C', '$text.punctuation.double[^ ]',
            'D',
        ),
        '<p>ABC D</p>')

  def testGuillemets_preservesSpaces(self):
    self.assertExecution('one « two » three',
                         '<p>one « two » three</p>')

  def testGuillemets_doesNotInsertSpaces(self):
    self.assertExecution('one «two» three',
                         '<p>one «two» three</p>')

  def testGuillemets_doesNotInsertSpacesAroundInlineTag(self):
    self.assertExecution(
        'one «$tag.open[span][inline]two$tag.close[span]» three',
        '<p>one «<span>two</span>» three</p>')

  def testGuillemets_doesNotInsertSpacesAroundBlockTag(self):
    self.assertExecution(
        'one «$tag.open[div][block] two $tag.close[div]» three',
        (
            '<p>one «</p>',
            '<div>two</div>',
            '<p>» three</p>',
        ))

  def testGuillemets_aroundNbsp(self):
    self.assertExecution('«~inside~»',
                         '<p>«\xa0inside\xa0»</p>')

  def testBackticksApostrophes(self):
    self.assertExecution("`one' 'two` th'ree fo`ur `' ' `",
                         "<p>‘one’ ’two‘ th’ree fo‘ur ‘’ ’ ‘</p>")

  def testTypoNewline(self):
    self.assertExecution("<<$typo.newline>>", '<p>«»</p>')

  def testNbsp_inside(self):
    self.assertExecution(
        'a~~b  ~~  c~~  ~~d  ~~e~~  f',
        '<p>a\xa0\xa0b\xa0\xa0c\xa0\xa0\xa0\xa0d\xa0\xa0e\xa0\xa0f</p>')

  def testNbsp_prefix(self):
    self.assertExecution(
        '~~~a',
        '<p>\xa0\xa0\xa0a</p>')

  def testNbsp_suffix(self):
    self.assertExecution(
        'a~~~',
        '<p>a\xa0\xa0\xa0</p>')


class FrenchTypographyTest(HtmlExecutionTestCase):

  typo = html_format.FrenchTypography

  def InputHook(self, text):
    return '$typo.set[french]' + text

  def testFormatNumber_invalid(self):
    self.assertEqual(self.typo.FormatNumber('invalid'), 'invalid')

  def testFormatNumber_zero(self):
    self.assertEqual(self.typo.FormatNumber('0'), '0')

  def testFormatNumber_short(self):
    self.assertEqual(self.typo.FormatNumber('123'), '123')

  def testFormatNumber_long(self):
    self.assertEqual(self.typo.FormatNumber('12345678'),
                     '12\xa0345\xa0678')
    self.assertEqual(self.typo.FormatNumber('123456'),
                     '123\xa0456')

  def testFormatNumber_negative(self):
    self.assertEqual(self.typo.FormatNumber('-1234,5678'),
                     '\u20131\xa0234,567\xa08')

  def testFormatNumber_positive(self):
    self.assertEqual(self.typo.FormatNumber('+1234.5678'),
                     '+1\xa0234.567\xa08')

  def testFormatNumber_decimalShort(self):
    self.assertEqual(self.typo.FormatNumber('3.5'), '3.5')

  def testFormatNumber_decimalLong(self):
    self.assertEqual(self.typo.FormatNumber('3.567890'),
                     '3.567\xa0890')
    self.assertEqual(self.typo.FormatNumber('3,5678901'),
                     '3,567\xa0890\xa01')

  def testFormatNumber_decimalOnly(self):
    self.assertEqual(self.typo.FormatNumber('.5'), '.5')
    self.assertEqual(self.typo.FormatNumber(',123'), ',123')
    self.assertEqual(self.typo.FormatNumber('-.5'), '\u2013.5')

  def testTypoNumber(self):
    self.assertExecution('before $typo.number[-12345678] after',
                         '<p>before \u201312\xa0345\xa0678 after</p>')

  def testAllSpecialChars(self):
    self.assertExecution(
        testutils.SPECIAL_CHARS,
        f'<p>{testutils.TYPO_TO_SPECIAL_CHARS_AS_HTML["french"]}</p>')

  def testPunctuationDouble_convertsSpaces(self):
    self.assertExecution(
        'one ! two : three ; four ? five , six .',
        '<p>one\xa0! two\xa0: three\xa0; four\xa0? five , six .</p>')

  def testPunctuationDouble_insertsSpaces(self):
    self.assertExecution(
        'one! two: three; four? five, six.',
        '<p>one\xa0! two\xa0: three\xa0; four\xa0? five, six.</p>')

  def testPunctuationDouble_insertsSpacesAfterInlineTag(self):
    self.assertExecution(
        (
            '$tag.open[span][inline]one$tag.close[span]! ',
            '$tag.open[span][inline]two$tag.close[span]: ',
            '$tag.open[span][inline]three$tag.close[span]; ',
            '$tag.open[span][inline]four$tag.close[span]? ',
        ), (
            '<p>'
              '<span>one</span>\xa0! '
              '<span>two</span>\xa0: '
              '<span>three</span>\xa0; '
              '<span>four</span>\xa0?'
            '</p>'
        ))

  def testPunctuationDouble_insertsNoSpacesAfterBlockTag(self):
    self.assertExecution(
        (
            '$tag.open[div][block]one$tag.close[div]! ',
            '$tag.open[div][block]two$tag.close[div]',
              '$tag.open[div][block]:$tag.close[div]',
            '$tag.open[div][block]three$tag.close[div]; ',
            '$tag.open[div][block]four$tag.close[div]? ',
        ), (
            '<div>one</div>', '<p>!</p>',
            '<div>two</div>', '<div>:</div>',
            '<div>three</div>', '<p>;</p>',
            '<div>four</div>', '<p>?</p>',
        ))

  def testPunctuationDouble_convertsSpaceAfterEllipsis(self):
    self.assertExecution(
        'Err... ? Ah... ! Yes..... : here',
        '<p>Err…\xa0? Ah…\xa0! Yes.....\xa0: here</p>')

  def testPunctuationDouble_insertsNoSpaceAfterEllipsis(self):
    self.assertExecution(
        'Err...? Ah...! Yes.....: here',
        '<p>Err…? Ah…! Yes.....: here</p>')

  def testPunctuationDouble_multipleInSequence(self):
    self.assertExecution('what !?;: wtf:;?!',
                         '<p>what\xa0!?;: wtf\xa0:;?!</p>')

  def testPunctuationDouble_afterNbsp(self):
    self.assertExecution('$macro.new[test][dialog~]$test?',
                         '<p>dialog\xa0?</p>')

  def testPunctuationDouble_afterNbspAndSpace(self):
    self.assertExecution('$macro.new[test][dialog~]$test ?',
                         '<p>dialog\xa0?</p>')

  def testPunctuationDouble_cornerCases(self):
    self.assertExecution(
        (
            'A', '$text.punctuation.double[]',
            'B', '$text.punctuation.double[ ]',
            'C', '$text.punctuation.double[^ ]',
            'D',
        ),
        '<p>ABC\xa0D</p>')

  def testGuillemets_convertsSpaces(self):
    self.assertExecution('one « two » three',
                         '<p>one «\xa0two\xa0» three</p>')

  def testGuillemets_insertsSpaces(self):
    self.assertExecution('one «two» three',
                         '<p>one «\xa0two\xa0» three</p>')

  def testGuillemets_insertsSpacesAroundInlineTag(self):
    self.assertExecution(
        'one «$tag.open[span][inline]two$tag.close[span]» three',
        '<p>one «\xa0<span>two</span>\xa0» three</p>')

  def testGuillemets_insertsSpacesAroundBlockTag(self):
    self.assertExecution(
        'one «$tag.open[div][block] two $tag.close[div]» three',
        (
            '<p>one «</p>',
            '<div>two</div>',
            '<p>» three</p>',
        ))

  def testGuillemets_aroundNbsp(self):
    self.assertExecution('«~inside~»',
                         '<p>«\xa0inside\xa0»</p>')

  def testBackticksApostrophes(self):
    self.assertExecution("`one' 'two` th'ree fo`ur `' ' `",
                         "<p>‘one’ ’two‘ th’ree fo‘ur ‘’ ’ ‘</p>")

  def testTypoNewline(self):
    self.assertExecution("<<$typo.newline>>", '<p>«»</p>')

  def testNbsp_inside(self):
    self.assertExecution(
        'a~~b  ~~  c~~  ~~d  ~~e~~  f',
        '<p>a\xa0\xa0b\xa0\xa0c\xa0\xa0\xa0\xa0d\xa0\xa0e\xa0\xa0f</p>')

  def testNbsp_prefix(self):
    self.assertExecution(
        '~~~a',
        '<p>\xa0\xa0\xa0a</p>')

  def testNbsp_suffix(self):
    self.assertExecution(
        'a~~~',
        '<p>a\xa0\xa0\xa0</p>')


class SimpleMacrosTest(HtmlExecutionTestCase):

  def testPar_success(self):
    self.assertExecution(
        'before$par^after',
        (
            '<p>before</p>',
            '<p>after</p>',
        ))

  def testPar_cannotOpen(self):
    self.assertExecution(
        '$tag.open[div][block]before$par^after$tag.close[div]',
        messages=['/root:1: $par: unable to open a new paragraph'])

  def testTypoSet_invalid(self):
    self.assertExecution(
        '$typo.set[invalid]',
        messages=['/root:1: $typo.set: unknown typography name: invalid; ' +
                  'expected one of: english, french, neutral'])

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
        '<p>a\xa0?b?c\xa0?</p>')

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
            '<p>root french\xa0?</p>',
            '<p>one french\xa0?</p>',
            '<p>two neutral?</p>',
        ))

  def testTypoNumber_invalid(self):
    self.assertExecution(
        '$typo.number[invalid]',
        messages=['/root:1: $typo.number: invalid integer: invalid'])
    self.assertExecution(
        '$typo.number[1.2,3]',
        messages=['/root:1: $typo.number: invalid integer: 1.2,3'])
    self.assertExecution(
        '$typo.number[--3]',
        messages=['/root:1: $typo.number: invalid integer: \u20133'])


class TagOpenCloseTest(HtmlExecutionTestCase):

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
            '<p>'
              'before <span>inside</span>'
              ' between '
              '<span>inside 2</span> after'
            '</p>'
        ))

  def testNested_regularText(self):
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

  def testNested_noSpaces(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.open[span][inline]one$tag.close[span]',
              '$tag.open[div][block]two$tag.close[div]',
            '$tag.close[div]',
        ), (
            '<div>'
              '<span>one</span>'
              '<div>two</div>'
            '</div>'
        ))

  def testParaAndContainerNoParasInside(self):
    self.assertExecution(
        '$tag.open[h1][para]inside$tag.close[h1]',
        '<h1>inside</h1>')

  def testParaWithParasInside(self):
    self.assertExecution(
        (
            '$tag.open[h1][para]\n'
              'inside\n'
              '1\n\n'
              'inside 2\n\n'
            '$tag.close[h1]\n'
        ),
        messages=['/root:3: unable to open a new paragraph'])

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
            '<div><span>one</span>',
            '<span>two</span></div>',
        ))

  def testTagOpen_voidAutoPara(self):
    self.assertExecution(
        '$tag.open[div][block,autopara=hr]',
        messages=['/root:1: $tag.open: cannot use void tag as autopara: <hr>'])

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
        ), messages=['/root:2: $tag.open: impossible to open ' +
                     'a non-inline tag inside an inline tag'])

  def testTagClose_autoParaClose(self):
    self.assertExecution(
        '$tag.open[div][block,autopara=p]inside$tag.close[div]after',
        (
            '<div><p>inside</p></div>',
            '<p>after</p>',
        ))

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
            '$tag.open[div][block,autopara=p]\n'
            'text\n\n'
            '$tag.class.add[current][test]\n'
            '$tag.close[div]\n'
        ),
        messages=['/root:5: $tag.close: removing an empty element ' +
                  'with attributes: <p class="test"></p>'])


class TagDeleteIfEmptyTest(HtmlExecutionTestCase):

  def testCompletelyEmpty(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.delete.ifempty[current]',
            '$tag.close[div]',
        ),
        '')

  def testNotEmpty_beforeAndAfterText(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              'before',
              '$tag.delete.ifempty[current]',
              ' after',
            '$tag.close[div]',
        ),
        '<div>before after</div>')

  def testNotEmpty_beforeText(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              'before',
              '$tag.delete.ifempty[current]',
            '$tag.close[div]',
        ),
        '<div>before</div>')

  def testNotEmpty_beforeChild(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.open[span][inline]before$tag.close[span]',
              '$tag.delete.ifempty[current]',
            '$tag.close[div]',
        ),
        '<div><span>before</span></div>')

  def testNotEmpty_afterText(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.delete.ifempty[current]',
              '^after',
            '$tag.close[div]',
        ),
        '<div>after</div>')

  def testNotEmpty_afterChild(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.delete.ifempty[current]',
              '$tag.open[span][inline]after$tag.close[span]',
            '$tag.close[div]',
        ),
        '<div><span>after</span></div>')

  def testKeepsTextBefore(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              'before',
              '$tag.open[span][inline]',
                  '$tag.delete.ifempty[current]',
              '$tag.close[span]',
            '$tag.close[div]',
        ),
        '<div>before</div>')

  def testKeepsTextAfter(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.open[span][inline]',
                  '$tag.delete.ifempty[current]',
              '$tag.close[span]',
              'after',
            '$tag.close[div]',
        ),
        '<div>after</div>')

  def testIgnoresAttributes(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.delete.ifempty[current]',
              '$tag.attr.set[current][name][value]',
            '$tag.close[div]',
        ),
        '')

  def testIgnoresSpaces(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.delete.ifempty[current]',
              '  \n   \n   ',
            '$tag.close[div]',
        ),
        '')

  def testWithRegularText(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.delete.ifempty[current]',
              'inside',
            '$tag.close[div]',
        ),
        '<div>inside</div>')

  def testWithChildren(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.open[pre][block]',
                '$tag.open[br][inline]$tag.close[br]',
                '$tag.delete.ifempty[current]',
                '$tag.open[br][inline]$tag.close[br]',
              '$tag.close[pre]',
            '$tag.close[div]',
        ), (
            '<div>'
                '<pre>'
                    '<br/>'
                    '<br/>'
                '</pre>'
            '</div>'
        ))

  def testTarget_named(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
               '$tag.open[span][inline]',
                   '$tag.delete.ifempty[<div>]',
               '$tag.close[span]',
            '$tag.close[div]',
        ),
        '<div><span></span></div>')

  def testTarget_para(self):
    self.assertExecution(
        (
            '$tag.open[p][para]',
               '$tag.open[span][inline]',
                   '$tag.delete.ifempty[para]',
               '$tag.close[span]',
            '$tag.close[p]',
        ),
        '<p><span></span></p>')

  def testTarget_nonauto(self):
    self.assertExecution(
        (
            '$tag.open[div][block,autopara=p]',
               '$tag.delete.ifempty[nonauto]',
            '$tag.close[div]',
        ),
        '')

  def testTarget_auto(self):
    self.assertExecution(
        (
            '$tag.open[div][block,autopara=p]',
              '$tag.delete.ifempty[auto]',
            '$tag.close[div]',
        ),
        '<div></div>')

  def testTarget_parent_completelyEmpty(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
                '$tag.open[pre][block]',
                    '$tag.delete.ifempty[parent]',
                    '$tag.delete.ifempty[current]',
                '$tag.close[pre]',
            '$tag.close[div]',
        ),
        '')

  def testTarget_parent_parentNotEmpty(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
                '$tag.open[pre][block]',
                    '$tag.delete.ifempty[parent]',
                    '$tag.delete.ifempty[current]',
                '$tag.close[pre]',
                'parent',
            '$tag.close[div]',
        ),
        '<div>parent</div>')

  def testOnlyChild(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.open[div][block]',
                '$tag.delete.ifempty[current]',
              '$tag.close[div]',
            '$tag.close[div]',
        ),
        '<div></div>')

  def testNested(self):
    del_if_empty = '$tag.delete.ifempty[current]'
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.open[h1][block]' + del_if_empty + '$tag.close[h1]',
              '$tag.open[h2][block]',
                del_if_empty,
                '$tag.open[span][inline]' + del_if_empty + '$tag.close[span]',
              '$tag.close[h2]',
              '$tag.open[h3][block]' + del_if_empty + '$tag.close[h3]',
            '$tag.close[div]',
        ),
        '<div></div>')

  def testComplexTree(self):
    del_if_empty = '$tag.delete.ifempty[current]'
    self.assertExecution(
        (
            '$tag.open[x][block]',
              '$tag.open[x1][block]' + del_if_empty + '$tag.close[x1]',
              '$tag.open[x2][block]',
                '$tag.open[x21][block]' + del_if_empty + '$tag.close[x21]',
                'before',
                '$tag.open[x22][block]' + del_if_empty + '$tag.close[x22]',
              '$tag.close[x2]',
              '$tag.open[x3][block]' + del_if_empty + '$tag.close[x3]',
              '$tag.open[x4][block]',
                '$tag.open[x41][block]' + del_if_empty + '$tag.close[x41]',
                'after',
                '$tag.open[x42][block]' + del_if_empty + '$tag.close[x42]',
              '$tag.close[x4]',
              '$tag.open[x5][block]' + del_if_empty + '$tag.close[x5]',
            '$tag.close[x]',
        ), (
            '<x>'
              '<x2>before</x2>',
              '<x4>after</x4>'
            '</x>',
        ))

  def testWithAutoPara(self):
    self.assertExecution(
        (
            '$tag.open[div][block,autopara=span]',
            'one\n\n',
            'two',
            '$tag.close[div]',
        ), (
            '<div>'
              '<span>one</span>',
              '<span>two</span>'
            '</div>'
        ))

  def testWithSubBranch(self):
    self.assertExecution(
        (
            '$tag.open[div][block,autopara=span]',
            'one\n\n',
            'two',
            '$tag.close[div]',
        ), (
            '<div>'
                '<span>one</span>',
                '<span>two</span>'
            '</div>'
        ))


class TagBodyRawTest(HtmlExecutionTestCase):

  def testSimple(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.body.raw[inside]',
            '$tag.close[div]',
        ),
        '<div>inside</div>')

  def testPreservesNewlinesInsideOnly(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.body.raw[',
                '\n'.join((
                    '',
                    'line 1',
                    'line 2',
                    '',
                    '',
                    'line 3',
                    '',
                )),
              ']',
            '$tag.close[div]',
        ),
        (
            '<div>line 1',
            'line 2',
            '',
            '',
            'line 3</div>',
        ))

  def testHonorsTypography_charsOnlyNotSpacing(self):
    self.assertExecution(
        (
            '$typo.set[french]',
            '$tag.open[div][block]',
              '$tag.body.raw[',
                testutils.SPECIAL_CHARS,
              ']',
            '$tag.close[div]',
        ),
        f'<div>{testutils.TYPO_TO_SPECIAL_CHARS_AS_HTML["english"]}</div>')

  def testPreservesExactSpacingInside(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              'before$tag.body.raw[^\xa0^ ^ inside^ \xa0^ ]after',
            '$tag.close[div]',
        ),
        '<div>before\xa0  inside \xa0 after</div>')

  def testPreservesTypographySpacingAround(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              'before \xa0  $tag.body.raw[inside]  after',
            '$tag.close[div]',
        ),
        '<div>before\xa0inside after</div>')


class TagAttrSetTest(HtmlExecutionTestCase):

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

  def testCurrent(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              'before ',
              '$tag.attr.set[current][name][value]',
              'after',
            '$tag.close[div]',
        ),
        '<div name="value">before after</div>')

  def testEmptyTag(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.attr.set[current][name][value]',
            '$tag.close[div]',
        ),
        '<div name="value"></div>')

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
            '$tag.open[span][inline]\n'
              '$tag.attr.set[<span>][ \n \n ][value]\n'
            '$tag.close[span]\n'
        ),
        messages=['/root:2: $tag.attr.set: attribute name cannot be empty'])

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


class ParTest(HtmlExecutionTestCase):

  def testCloseAndOpen(self):
    self.assertExecution(
        'one\n\ntwo$par^three',
        (
            '<p>one</p>',
            '<p>two</p>',
            '<p>three</p>',
        ))

  def testOpenOnly(self):
    self.assertExecution(
        '$par^one\n\n$par^two',
        (
            '<p>one</p>',
            '<p>two</p>',
        ))

  def testCannotOpen(self):
    self.assertExecution(
        '$tag.open[div][block]$par$tag.close[div]',
        messages=['/root:1: $par: unable to open a new paragraph'])


class TagClassAddTest(HtmlExecutionTestCase):

  def testOnce(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.open[div][block]',
                'before',
                '$tag.class.add[<div>][first]',
                '$tag.open[div][block]after$tag.close[div]',
              '$tag.close[div]',
            '$tag.close[div]',
        ), (
            '<div>'
              '<div class="first">'
                'before'
                '<div>after</div>'
              '</div>'
            '</div>'
        ))

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
        ), (
            '<p>'
              '<span class="first second">one two three</span>'
            '</p>'
        ))

  def testTwiceSame(self):
    self.assertExecution(
        (
            '$tag.open[span][inline]',
              '$tag.class.add[<span>][same]',
              '$tag.class.add[<span>][same]',
              'inside',
            '$tag.close[span]',
        ), (
            '<p>'
              '<span class="same">inside</span>'
            '</p>'
        ))

  def testMultipleClassesAtOnce(self):
    self.assertExecution(
        (
            '$tag.open[span][inline]',
              '$tag.class.add[<span>][  one two\n one \n ]',
              '$tag.class.add[<span>][three\ntwo four]',
              'inside',
            '$tag.close[span]',
        ), (
            '<p>'
              '<span class="one two three four">inside</span>'
            '</p>'
        ))

  def testTarget_current_regular(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.open[pre][block]',
                'before ',
                '$tag.class.add[current][first]',
                'after',
              '$tag.close[pre]',
            '$tag.close[div]',
        ), (
            '<div>'
              '<pre class="first">before after</pre>'
            '</div>'
        ))

  def testTarget_current_insideAutoPara(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.open[pre][block,autopara=p]',
                '$tag.class.add[current][first]',
                'inside',
              '$tag.close[pre]',
            '$tag.close[div]',
        ), (
            '<div>'
              '<pre>'
                '<p class="first">inside</p>'
              '</pre>'
            '</div>'
        ))

  def testTarget_current_insideNoAutoPara(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.open[pre][block]',
                '$tag.class.add[current][first]',
                'inside',
              '$tag.close[pre]',
            '$tag.close[div]',
        ), (
            '<div>'
              '<pre class="first">inside</pre>'
            '</div>'
        ))

  def testTarget_auto_regular(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.open[pre][block]',
                'before ',
                '$tag.class.add[auto][first]',
                'after',
              '$tag.close[pre]',
            '$tag.close[div]',
        ),
        messages=['/root:4: $tag.class.add: no element found for target: auto'])

  def testTarget_auto_insideAutoPara(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.open[pre][block,autopara=p]',
                '$tag.class.add[auto][first]',
                'inside',
              '$tag.close[pre]',
            '$tag.close[div]',
        ), (
            '<div>'
              '<pre>'
                '<p class="first">inside</p>'
              '</pre>'
            '</div>'
        ))

  def testTarget_auto_insideNoAutoPara(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.open[pre][block]',
                '$tag.class.add[auto][first]',
                'inside',
              '$tag.close[pre]',
            '$tag.close[div]',
        ),
        messages=['/root:3: $tag.class.add: no element found for target: auto'])

  def testTarget_nonauto_regular(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.open[pre][block]',
                'before ',
                '$tag.class.add[nonauto][first]',
                'after',
              '$tag.close[pre]',
            '$tag.close[div]',
        ), (
            '<div>'
              '<pre class="first">before after</pre>'
            '</div>'
        ))

  def testTarget_nonauto_insideAutoPara(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
                '$tag.open[pre][block,autopara=p]',
                '$tag.class.add[nonauto][first]',
                'inside',
              '$tag.close[pre]',
            '$tag.close[div]',
        ), (
            '<div>'
              '<pre class="first">'
                '<p>inside</p>'
              '</pre>'
            '</div>'
        ))

  def testTarget_nonauto_insideNoAutoPara(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.open[pre][block]',
                '$tag.class.add[nonauto][first]',
                'inside',
              '$tag.close[pre]',
            '$tag.close[div]',
        ), (
            '<div>'
              '<pre class="first">inside</pre>'
            '</div>'
        ))

  def testTarget_parent_regular(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.open[pre][block]',
                'before ',
                '$tag.class.add[parent][first]',
                'after',
              '$tag.close[pre]',
            '$tag.close[div]',
        ), (
            '<div class="first">'
              '<pre>before after</pre>'
            '</div>'
        ))

  def testTarget_parent_insideAutoPara(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.open[pre][block,autopara=p]',
                '$tag.class.add[parent][first]',
                'inside',
              '$tag.close[pre]',
            '$tag.close[div]',
        ), (
            '<div>'
              '<pre class="first">'
                '<p>inside</p>'
              '</pre>'
            '</div>'
        ))

  def testTarget_parent_insideNoAutoPara(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.open[pre][block]',
                '$tag.class.add[parent][first]',
                'inside',
              '$tag.close[pre]',
            '$tag.close[div]',
        ), (
            '<div class="first">'
              '<pre>inside</pre>'
            '</div>'
        ))

  def testTarget_para(self):
    self.assertExecution(
        (
            '$tag.open[div][para]',
              '$tag.open[pre][inline]',
                'before ',
                '$tag.class.add[para][first]',
                'after',
              '$tag.close[pre]',
            '$tag.close[div]',
        ), (
            '<div class="first">'
              '<pre>before after</pre>'
            '</div>'
        ))

  def testTarget_previousAfterOpeningTag(self):
    self.assertExecution(
        (
            '$tag.open[div][block]',
              '$tag.open[span][inline]',
                'nested',
              '$tag.close[span]',
            '$tag.close[div]',
            '$tag.class.add[previous][test]',
        ), (
            '<div class="test">'
              '<span>nested</span>'
            '</div>'
        ))

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
            '<div class="test">'
              '<span>nested</span>'
            '</div>',
            '<div>'
              'after'
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
            '<div class="test">'
              'before'
              '<span>inside</span>'
            '</div>',
            '<div>'
              '<span>after</span>'
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
        ), (
            '<p>'
              '<span class="&amp;&quot;">inside</span>'
            '</p>'
        ))

  def testBlankClassName(self):
    self.assertExecution(
        (
            '$tag.open[span][inline]',
              '$tag.class.add[<span>][ \n \n ]',
              'inside',
            '$tag.close[span]',
        ), (
            '<p>'
              '<span>inside</span>'
            '</p>'
        ))

  def testTargetNotFound(self):
    self.assertExecution(
        '$tag.class.add[<div>][first]',
        messages=['/root:1: $tag.class.add: ' +
                  'no element found for target: <div>'])

  def testInvalidTarget(self):
    self.assertExecution(
        '$tag.class.add[invalid][first]',
        messages=['/root:1: $tag.class.add: invalid target: invalid'])


if __name__ == '__main__':
  testutils.unittest.main()
