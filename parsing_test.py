#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

from parsing import *
from testutils import *


class TokenTest(TestCase):

  def testRepr(self):
    self.assertEqual(repr(Token('TEXT', 42, 'a\nb')), r"(TEXT l42 'a\nb')")


class TextNodeTest(TestCase):

  def testStr(self):
    self.assertEqual(str(TextNode(test_location, 'a\nb')), r"'a\nb'")

  def testRepr(self):
    self.assertEqual(repr(TextNode(test_location, 'a\nb')),
                     r"file.txt:42'a\nb'")

  def testEq(self):
    node = TextNode(test_location, 'text')
    self.assertEqual(node, TextNode(test_location, 'text'))
    self.assertNotEqual(node, CallNode(test_location, 'text', []))
    self.assertNotEqual(node, TextNode(loc('file.txt', 43), 'text'))
    self.assertNotEqual(node, TextNode(test_location, 'other'))


class CallNodeTest(TestCase):

  def testStr_noArgs(self):
    self.assertEqual(str(CallNode(test_location, 'name', [])),
                     '$name')

  def testStr_twoArgs(self):
    self.assertEqual(str(CallNode(test_location, 'name',
                                  [[TextNode(test_location, 'one')],
                                   [TextNode(test_location, 'two')]])),
                     "$name['one']['two']")

  def testRepr_noArgs(self):
    self.assertEqual(repr(CallNode(test_location, 'name', [])),
                     '$name')

  def testRepr_twoArgs(self):
    self.assertEqual(repr(CallNode(test_location, 'name', [['one'], ['two']])),
                     "$name['one']['two']")

  def testEq(self):
    node = CallNode(test_location, 'name', ['one', 'two'])
    self.assertEqual(node, CallNode(test_location, 'name', ['one', 'two']))
    self.assertNotEqual(node, TextNode(test_location, 'text'))
    self.assertNotEqual(node, CallNode(test_location, 'name', ['other']))
    self.assertNotEqual(node, CallNode(test_location, 'other', ['one', 'two']))


class FormatNodesTest(TestCase):

  def testEmpty(self):
    self.assertEqual(FormatNodes([]), '')

  def testOneTextNode(self):
    self.assertEqual(FormatNodes([TextNode(loc('root', 1), 'text')]),
                     "'text'")

  def testTwoTextNodesDifferentLine(self):
    self.assertEqual(FormatNodes([TextNode(loc('root', 1), 'one'),
                                  TextNode(loc('root', 2), 'two')]),
                     "'one''two'")

  def testTwoTextNodesSameLine(self):
    self.assertEqual(FormatNodes([TextNode(test_location, 'one'),
                                  TextNode(test_location, 'two')]),
                     "'onetwo'")


class PeekableIteratorTest(TestCase):

  def testEmpty(self):
    it = PeekableIterator([])
    self.assertIs(it.peek(), None)
    self.assertIs(next(it), None)
    self.assertIs(it.peek(), None)
    self.assertIs(next(it), None)

  def testOneElement_peekFirst(self):
    elem1 = '1'
    it = PeekableIterator([elem1])
    self.assertIs(it.peek(), elem1)
    self.assertIs(next(it), elem1)
    self.assertIs(it.peek(), None)
    self.assertIs(next(it), None)

  def testOneElement_nextFirst(self):
    elem1 = '1'
    it = PeekableIterator([elem1])
    self.assertIs(next(it), elem1)
    self.assertIs(it.peek(), None)
    self.assertIs(next(it), None)
    self.assertIs(it.peek(), None)

  def testThreeElements(self):
    elem1, elem2, elem3 = '1', '2', '3'
    it = PeekableIterator([elem1, elem2, elem3])
    self.assertIs(it.peek(), elem1)
    self.assertIs(next(it), elem1)
    self.assertIs(next(it), elem2)
    self.assertIs(it.peek(), elem3)
    self.assertIs(next(it), elem3)
    self.assertIs(it.peek(), None)
    self.assertIs(next(it), None)


class ParsingTest(TestCase):

  def assertParsing(self, input_text, output=None, messages=(),
                    fatal_error=None, filename=Filename('root', '/cur')):
    # By default, expect a fatal error if log messages are expected.
    if fatal_error is None:
      fatal_error = (len(messages) > 0)

    logger = FakeLogger()

    # Create a fake input file and parse it.
    input_file = self.FakeInputFile(input_text, newline=None)
    try:
      nodes = ParseFile(input_file, filename, logger=logger)
    except FatalError:
      nodes = None

    # Verify the output.
    actual_fatal_error = (nodes is None)
    if fatal_error:
      self.assertTrue(actual_fatal_error, 'expected a fatal error')
    else:
      self.assertFalse(actual_fatal_error,
                       'unexpected fatal error; messages: {0}'.format(
                          logger.ConsumeStdErr()))
      if isinstance(output, str):
        self.assertEqualExt(FormatNodes(nodes), output, 'nodes text mismatch')
      else:
        self.assertEqualExt(nodes, output, 'nodes mismatch',
                            fmt=ReprNodes)

    # Verify the log messages.
    self.assertEqualExt(logger.ConsumeStdErr(), '\n'.join(messages),
                        'messages mismatch')

  def testReadError(self):
    self.assertParsing(None, messages=[
        'root:1: unable to read the input file: root\nFake error'])

  def testEmpty(self):
    self.assertParsing('', '')

  def testEscapeOnly(self):
    self.assertParsing('^', '')

  def testText(self):
    self.assertParsing('text', "'text'")

  def testUnicode(self):
    self.assertParsing(test_unicode, repr(test_unicode))

  def testStrips(self):
    self.assertParsing(' \t\n\r\f\v\xa0text\xa0 \t\n\r\f\v',
                       r"'text'")

  def testTrailingEscapeDropped(self):
    self.assertParsing('test^', "'test'")

  def testTrailingEscapeBeforeWhitespace(self):
    self.assertParsing('test^  ', "'test '")

  def testNewline(self):
    self.assertParsing('first\nsecond', r"'first\n''second'")

  def testRepeatedNewlines(self):
    self.assertParsing('\n\n\nfirst\n\n\nsecond\n\n\nthird\n\n',
                       r"'first\n\n\n''second\n\n\n''third'")

  def testCrLf(self):
    self.assertParsing('A\nB\rC\r\nD', r"'A\n''B\n''C\n''D'")

  def testComment(self):
    self.assertParsing('first  # comment\nsecond\n#comment\nthird',
                       r"'first''second\n''third'")
    self.assertParsing('first  # comment\nsecond\n#comment\nthird',
                       [TextNode(loc('root', 1), 'first'),
                        TextNode(loc('root', 2), 'second\n'),
                        TextNode(loc('root', 4), 'third')])

  def testEscapeStandard(self):
    self.assertParsing('be^fore^$after^\n  ^^ next',
                       r"'before$after^\n''^ next'")

  def testEscapeSpecialCharacters(self):
    self.assertParsing("^% ^& ^~ ^-- ^-^-- ^... ^« ^» ^<< ^>> ^' ^!^:^;^?",
                       '"% & ~ -- --- ... \xab \xbb << >> \' !:;?"')

  def testBackslashNoEscape(self):
    self.assertParsing('text\\', r"'text\\'")

  def testWhitespacePreserve(self):
    self.assertParsing(
        '\n'.join((
            '$$whitespace.preserve',
            '$top[',
            '  a',
            '  # comment',
            '  $inner[arg][',
            '    $deep b # comment',
            '    before close',
            '  ]',
            'c]',
        )), [
            CallNode(loc('root', 2), 'top', [[
                TextNode(loc('root', 3), 'a\n'),
                CallNode(loc('root', 5), 'inner', [
                    [TextNode(loc('root', 5), 'arg')],
                    [
                        CallNode(loc('root', 6), 'deep', []),
                        TextNode(loc('root', 6), ' b'),
                        TextNode(loc('root', 7), 'before close'),
                    ]
                ]),
                TextNode(loc('root', 8), '\n'),
                TextNode(loc('root', 9), 'c'),
            ]]),
        ])

  def testWhitespaceSkip(self):
    self.assertParsing(
        '\n'.join((
            '$$whitespace.skip',
            '$top[',
            '  a',
            '  # comment',
            '  $inner[arg][',
            '    $deep b # comment',
            '    before close',
            '  ]',
            'c]',
        )), [
            CallNode(loc('root', 2), 'top', [[
                TextNode(loc('root', 3), 'a'),
                CallNode(loc('root', 5), 'inner', [
                    [TextNode(loc('root', 5), 'arg')],
                    [
                        CallNode(loc('root', 6), 'deep', []),
                        TextNode(loc('root', 6), 'b'),
                        TextNode(loc('root', 7), 'before close'),
                    ],
                ]),
                TextNode(loc('root', 9), 'c'),
            ]]),
        ])

  def testWhitespace_mix(self):
    self.assertParsing(
        '\n'.join((
            '$$whitespace.skip',
            'A1',
            '2',
            '$$whitespace.preserve',
            'B1',
            '2',
            '$$whitespace.preserve$$whitespace.skip',
            'C1',
            '2',
            '$$whitespace.skip$$whitespace.preserve',
            'D1',
            '2',
            '$$whitespace.skip^E1',
            '2',
            '$$whitespace.preserve^F1',
            '2',
            '$$whitespace.skip$G1',
            '2',
            '$$whitespace.preserve$H1',
            '2',
        )), [
            TextNode(loc('root', 2), 'A1'),
            TextNode(loc('root', 3), '2'),
            TextNode(loc('root', 5), 'B1\n'),
            TextNode(loc('root', 6), '2\n'),
            TextNode(loc('root', 8), 'C1'),
            TextNode(loc('root', 9), '2'),
            TextNode(loc('root', 11), 'D1\n'),
            TextNode(loc('root', 12), '2\n'),
            TextNode(loc('root', 13), 'E1'),
            TextNode(loc('root', 14), '2'),
            TextNode(loc('root', 15), 'F1\n'),
            TextNode(loc('root', 16), '2\n'),
            CallNode(loc('root', 17), 'G1', []),
            TextNode(loc('root', 18), '2'),
            CallNode(loc('root', 19), 'H1', []),
            TextNode(loc('root', 19), '\n'),
            TextNode(loc('root', 20), '2'),
        ])

  def testWhitespace_preserveByDefault(self):
    self.assertParsing('a\nb', r"'a\n''b'")

  def testPreProcessing_unknownInstruction(self):
    self.assertParsing(
        'before$$invalid\nafter',
        messages=["root:1: unknown pre-processing instruction: '$$invalid'\n" +
                  "known instructions: $$whitespace.preserve, " +
                  "$$whitespace.skip"])

  def testPreprocessing_emptyInstruction(self):
    self.assertParsing(
        '$$ $dummy',
        messages=["root:1: unknown pre-processing instruction: '$$'\n" +
                  "known instructions: $$whitespace.preserve, " +
                  "$$whitespace.skip"])

  def testMacro_noArgs(self):
    self.assertParsing('before $name after', r"'before '$name' after'")

  def testMacro_someArgs(self):
    self.assertParsing('before $name[arg1][][arg3] after',
                       r"'before '$name['arg1'][]['arg3']' after'")

  def testMacro_nested(self):
    self.assertParsing('$top[a $inner[arg][$deep b] $other c]',
                       r"$top['a '$inner['arg'][$deep' b']' '$other' c']")

  def testMacro_noBreakBeforeArg(self):
    self.assertParsing('$name [arg2]',
                       messages=["root:1: syntax error: '['"])
    self.assertParsing('$name[arg1] [arg2]',
                       messages=["root:1: syntax error: '['"])

  def testMacro_emptyName(self):
    self.assertParsing('$!name after',
                       messages=["root:1: invalid macro name: '$!name'"])

  def testMacro_startsWithDigit(self):
    self.assertParsing('$0name after',
                       messages=["root:1: invalid macro name: '$0name'"])

  def testMacro_startsWithPeriod(self):
    self.assertParsing('$.name after',
                       messages=["root:1: invalid macro name: '$.name'"])

  def testMacro_startsWithUnderscore(self):
    self.assertParsing('$_name after',
                       messages=["root:1: invalid macro name: '$_name'"])

  def testMacro_specialVariableNames(self):
    self.assertParsing('$_ $\\', "$_' '$\\")

  def testMacro_endsWithPeriod(self):
    self.assertParsing('before $one.two. after',
                       r"'before '$one.two'. after'")

  def testMacro_periodInside(self):
    self.assertParsing('before $one.two after',
                       r"'before '$one.two' after'")

  def testMacro_endsWithUnderscore(self):
    self.assertParsing('before $one_ after',
                       r"'before '$one_' after'")

  def testMacro_endsWithUnderscorePeriod(self):
    self.assertParsing('before $one_. after',
                       r"'before '$one_'. after'")

  def testDashEn(self):
    self.assertParsing('before--after', "'before'$text.dash.en'after'")

  def testDashEm(self):
    self.assertParsing('before---after', "'before'$text.dash.em'after'")

  def testOneDash(self):
    self.assertParsing('before-after', "'before-after'")

  def testTooManyDashes(self):
    self.assertParsing('before----after', "'before----after'")
    self.assertParsing('before------after', "'before------after'")

  def testEllipsis(self):
    self.assertParsing('before...after', "'before'$text.ellipsis'after'")

  def testTooManyPeriods(self):
    self.assertParsing('before....after', "'before....after'")
    self.assertParsing('before......after', "'before......after'")

  def testGuillemetsCharacter(self):
    self.assertParsing(
        'before«in»after',
        "'before'$text.guillemet.open'in'$text.guillemet.close'after'")
    self.assertParsing(
        'before « in » after',
        "'before '$text.guillemet.open' in '$text.guillemet.close' after'")

  def testManyGuillemetCharacters(self):
    self.assertParsing(
        'before««in»»after',
        ''.join((
            "'before'",
            "$text.guillemet.open$text.guillemet.open",
            "'in'",
            "$text.guillemet.close$text.guillemet.close",
            "'after'",
        )))

  def testGuillemetsSymbol(self):
    self.assertParsing(
        'before<<in>>after',
        "'before'$text.guillemet.open'in'$text.guillemet.close'after'")
    self.assertParsing(
        'before << in >> after',
        "'before '$text.guillemet.open' in '$text.guillemet.close' after'")

  def testManyGuillemetSymbols(self):
    self.assertParsing('before<<<in>>>after',
                       "'before<<<in>>>after'")
    self.assertParsing('before<<<<in>>>>after',
                       "'before<<<<in>>>>after'")

  def testQuote(self):
    self.assertParsing('before"in"after',
                       "'before\"in\"after'")
    self.assertParsing('before "in" after',
                       "'before \"in\" after'")
    self.assertParsing('before""in""after',
                       "'before\"\"in\"\"after'")

  def testBacktickSingle(self):
    self.assertParsing(
        "a`b `c` d",
        ''.join((
            "'a'$text.backtick'b '",
            "$text.backtick",
            "'c'",
            "$text.backtick",
            "' d'",
        )))

  def testBacktickDouble(self):
    self.assertParsing(
        "a``b ``c`` d",
        ''.join((
            "'a'$text.quote.open'b '",
            "$text.quote.open",
            "'c'",
            "$text.quote.open",
            "' d'",
        )))

  def testApostropheSingle(self):
    self.assertParsing(
        "a'b 'c' d",
        ''.join((
            "'a'$text.apostrophe'b '",
            "$text.apostrophe",
            "'c'",
            "$text.apostrophe",
            "' d'",
        )))

  def testApostropheDouble(self):
    self.assertParsing(
        "a''b ''c'' d",
        ''.join((
            "'a'$text.quote.close'b '",
            "$text.quote.close",
            "'c'",
            "$text.quote.close",
            "' d'",
        )))

  def testManyBackticksAndApostrophes(self):
    self.assertParsing(
        "a`````b'''''c",
        ''.join((
            "'a'",
            "$text.quote.open$text.quote.open$text.backtick",
            "'b'",
            "$text.quote.close$text.quote.close$text.apostrophe",
            "'c'",
        )))

  def testDoublePunctuation(self):
    self.assertParsing(
        "!:;? a?;:! b !",
        ''.join((
            "$text.punctuation.double['!:;?']",
            "' a'",
            "$text.punctuation.double['?;:!']",
            "' b '",
            "$text.punctuation.double['!']",
        )))

  def testAllSpecialChars(self):
    self.assertParsing(
        special_chars,
        ' '.join((
            "$text.percent' '$text.ampersand' '$text.underscore'",
            "$ '$text.dollar' # '$text.hash'",
            "a'$text.nbsp'b",
            "n'$-'o",
            "'$text.dash.en'c'$text.dash.em'",
            "d'$text.ellipsis'",
            "'$text.guillemet.open'e'$text.guillemet.close'",
            "'$text.guillemet.open' f '$text.guillemet.close'",
            "'$text.backtick'g'$text.apostrophe'h'$text.apostrophe'",
            "'$text.apostrophe'g'$text.backtick'h'$text.backtick'",
            "'$text.quote.open'i'$text.quote.close'j'$text.quote.close'",
            "'$text.quote.close'k'$text.quote.open'l'$text.quote.open'",
            "'$text.quote.open$text.backtick'm" +
                "'$text.quote.close$text.apostrophe'",
            "n '$text.punctuation.double['!']'",
            "o'$text.punctuation.double[':']'",
            "p '$text.punctuation.double[';']'",
            "q'$text.punctuation.double['?']'",
            "r'$text.punctuation.double['!:;?']",
        )))
  def testNoValidToken(self):
    self.assertParsing(
        '$macro[',
        messages=["root:1: syntax error: macro argument should be closed"])

  def testUnclosedMacroArgument(self):
    self.assertParsing(
        '\n'.join((
            'a',
            '$macro[',  # error
            'b',
            'c',
        )),
        messages=["root:2: syntax error: macro argument should be closed"])

  def testUnclosedMacroArgumentNested(self):
    self.assertParsing(
        '\n'.join((
            'a',
            '$macro1[]',  # valid so far - ignored
            'b',
            '$macro2[',  # initial error
            'c',
            '$macro3[',  # other error - ignored
            'd',
        )),
        messages=["root:6: syntax error: macro argument should be closed"])

  def testTooManyArgumentClose(self):
    self.assertParsing(
        '\n'.join((
            '$macro[',
            'a',
            ']',
            'b',
            ']',  # error
            'c',
        )),
        messages=["root:5: syntax error: no macro argument to close"])


if __name__ == '__main__':
  unittest.main()
