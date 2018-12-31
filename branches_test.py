#!/usr/bin/env python3
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

from branches import *
from testutils import *


class TextBranchTest(BranchTestCase):

  def setUp(self):
    super(TextBranchTest, self).setUp()
    self.branch = TextBranch(parent=None, name='dummy')

  def assertRender(self, expected):
    with self.FakeOutputFile() as writer:
      self.branch.writer = writer
      self.branch.Render()
      self.assertEqual(writer.getvalue(), expected)

  def testRepr(self):
    self.assertEqual(repr(self.branch), '<TextBranch: dummy>')

  def testRender_empty(self):
    self.assertRender('')

  def testRender_text(self):
    self.branch.AppendText('one ')
    self.branch.AppendText('two ')
    self.branch.AppendText('three ')
    self.assertRender('one two three ')

  def testRender_mix(self):
    self.PrepareMix(self.branch)
    self.assertRender('one sub1 sub12 two sub21 three ')

  def testRender_unattachedBranch(self):
    self.branch.CreateSubBranch()
    self.branch.AppendText('test')
    self.assertRender('test')


if __name__ == '__main__':
  unittest.main()
