#!/usr/bin/env python
# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'


import executor
from log import FatalError, InternalError, Location
from macros import *


class LatexBranch(executor.TextBranch):
  """
  Branch for LaTeX-code.
  """

  type_name = 'latex'

  def __init__(self, *args, **kwargs):
    super(LatexBranch, self).__init__(*args, **kwargs)

    if not self.parent:
      self.context.AddMacros(GetPublicMacros(Macros))


class Macros(object):

  TextPercent = StaticAppendTextCallback('\%', public_name='text.percent')
  TextAmpersand = StaticAppendTextCallback('\&', public_name='text.ampersand')
  TextNbsp = StaticAppendTextCallback('~', public_name='text.nbsp')
  TextDashEn = StaticAppendTextCallback('--', public_name='text.dash.en')
  TextDashEm = StaticAppendTextCallback('---', public_name='text.dash.em')
