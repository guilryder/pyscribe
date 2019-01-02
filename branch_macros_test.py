#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'

from branches import TextBranch
from builtin_macros import *
from execution import *
from testutils import *


class BranchWriteTest(ExecutionTestCase):

  def GetExecutionBranch(self, executor):
    self.CreateBranch(executor, TextBranch, name='other')
    return executor.system_branch

  def testCurrentBranch(self):
    self.assertExecution(
        '$branch.write[system][contents]',
        {'/system': 'contents', '/output/other': ''})

  def testDifferentBranch(self):
    self.assertExecution(
        '$branch.write[other][contents]',
        {'/system': '', '/output/other': 'contents'})

  def testBranchNotFound(self):
    self.assertExecution(
        '$branch.write[invalid][contents]',
        messages=['/root:1: $branch.write: branch not found: invalid'])


class BranchCreateTest(ExecutionTestCase):

  def testRoot_text(self):
    self.assertExecution(
        (
            '$branch.create.root[text][new][.ext]\n',
            '$branch.write[new][one\n\ntwo]\n',
        ),
        {'/system': '\n', '/output.ext': 'one\n\ntwo'})

  def testRoot_unknownType(self):
    self.assertExecution(
        '$branch.create.root[invalid][new][output]',
        messages=['/root:1: $branch.create.root: ' +
                  'unknown branch type: invalid;' +
                  ' expected one of: html, latex, text'])

  def testRoot_duplicateBranchName(self):
    self.assertExecution(
        (
            '$branch.create.root[text][one][.a]',
            '$branch.create.root[text][two][.b]',
            '$branch.create.root[text][one][.c]',
        ),
        messages=['/root:3: $branch.create.root: ' +
                  'a branch of this name already exists: one'])

  def testRoot_emptyOutputSuffix(self):
    self.assertExecution(
        (
            '$branch.create.root[text][one][]',
            '$branch.write[one][inside]',
        ),
        {'/output': 'inside'})

  def testRoot_invalidOutputSuffix_dotPrefixMissing(self):
    self.assertExecution(
        '$branch.create.root[text][one][foo.bar]',
        messages=["/root:1: $branch.create.root: invalid output file name "
                  "suffix: 'foo.bar'; must be empty or start with a period"])

  def testRoot_invalidOutputSuffix_dirSeparatorInside(self):
    self.assertExecution(
        '$branch.create.root[text][one][.foo/bar]',
        messages=["/root:1: $branch.create.root: invalid output file name "
                  "suffix: '.foo/bar'; must be a basename "
                  "(no directory separator)"])

  def testRoot_invalidOutputSuffix_dirSeparatorSuffix(self):
    self.assertExecution(
        '$branch.create.root[text][one][.foo/]',
        messages=["/root:1: $branch.create.root: invalid output file name "
                  "suffix: '.foo/'; must be a basename "
                  "(no directory separator)"])

  def testRoot_nameRef(self):
    self.assertExecution(
        (
            '$branch.create.root[text][!new][.ext]',
            '$branch.write[$new][inside]',
            '$new',
        ),
        {'/system': 'auto1', '/output.ext': 'inside'})

  def testRoot_inheritsCurrentBranch(self):
    self.assertExecution(
        (
            '$macro.new[first][one]',
            '$branch.create.root[text][new][.ext]',
            '$macro.new[second][two]',
            '$branch.write[new][$first $second]',
        ),
        {'/system': '', '/output.ext': 'one two'})

  def testRoot_doesNotInheritsOtherBranches(self):
    self.assertExecution(
        (
            '$branch.create.root[text][new1][.1]',
            '$branch.create.root[text][new2][.2]',
            '$branch.write[new1][$macro.new[macro][test]]',
            '$branch.write[new2][',
              '$macro]',
        ),
        messages=['/root:5: macro not found: $macro',
                  '  /root:4: $branch.write'])

  def testSub_multiple(self):
    self.assertExecution(
        (
            '$branch.create.sub[one]',
            'one^ ',
            '$branch.append[one]',
            'two^ ',
            '$branch.write[one][oneA^ ]'
            '$branch.create.sub[two]',
            '$branch.append[two]',
            '$branch.write[one][oneB^ ]'
            'three^ ',
            '$branch.write[two][twoA^ ]'
            '$branch.create.sub[three]',
            '$branch.write[one][oneC^ ]'
            '$branch.append[three]',
            'four',
        ),
        'one oneA oneB oneC two twoA three four')

  def testSub_nested(self):
    self.assertExecution(
        (
            'one^ ',
            '$branch.create.sub[one]',
            '$branch.append[one]',
            'two^ ',
            '$branch.create.sub[two]',
            '$branch.append[two]',
            'three',
            '$branch.write[one]['
              'oneB^ '
              '$branch.create.sub[oneA]',
              '$branch.append[oneA]',
              'oneE^ ',
            ']',
            '$branch.write[two]['
              'twoB^ '
              '$branch.create.sub[twoA]',
              '$branch.append[twoA]',
              'twoE^ ',
            ']',
            '$branch.write[oneA][oneI^ ]',
            '$branch.write[twoA][twoI^ ]',
        ),
        'one oneB oneI oneE two twoB twoI twoE three')

  def testSub_duplicateName(self):
    self.assertExecution(
        (
            '$branch.create.sub[one]',
            '$branch.create.sub[two]',
            '$branch.create.sub[one]',
        ),
        messages=['/root:3: $branch.create.sub: ' +
                  'a branch of this name already exists: one'])

  def testSub_nameRef(self):
    self.assertExecution(
        (
            '$branch.create.sub[!new]',
            'before $branch.append[$new] after',
            '$branch.write[$new][inside]',
        ),
        'before inside after')


class BranchAppendTest(ExecutionTestCase):

  def testParentMismatch_siblings(self):
    self.assertExecution(
        (
            '$branch.create.sub[one]',
            '$branch.create.sub[two]',
            '$branch.write[one][$branch.create.sub[one-sub]]',
            '$branch.write[two][$branch.append[one-sub]]',
        ),
        messages=["/root:4: $branch.append: expected a sub-branch created by" +
                  " branch 'two'; got one created by branch 'one'",
                  "  /root:4: $branch.write"])

  def testParentMismatch_childIntoParent(self):
    self.assertExecution(
        (
            '$branch.create.sub[child]',
            '$branch.write[child][$branch.create.sub[child-sub]]',
            '$branch.append[child-sub]',
        ),
        messages=["/root:3: $branch.append: expected a sub-branch created by" +
                  " branch 'system'; got one created by branch 'child'"])

  def testParentMismatch_parentIntoChild(self):
    self.assertExecution(
        (
            '$branch.create.sub[child]',
            '$branch.create.sub[sibling]',
            '$branch.write[child][$branch.append[sibling]]',
        ),
        messages=["/root:3: $branch.append: expected a sub-branch created by" +
                  " branch 'child'; got one created by branch 'system'",
                  "  /root:3: $branch.write"])

  def testAlreadyAttached(self):
    self.assertExecution(
        (
            '$branch.create.sub[sub]',
            '$branch.append[sub]',
            '$branch.append[sub]',
        ),
        messages=[
            "/root:3: $branch.append: the sub-branch 'sub' is already attached",
        ])


if __name__ == '__main__':
  unittest.main()
