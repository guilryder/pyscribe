# Copyright 2011, Guillaume Ryder, GNU GPL v3 license

__author__ = 'Guillaume Ryder'


import execution
from macros import *


class LatexBranch(execution.TextBranch):
  """
  Branch for LaTeX-code.
  """

  type_name = 'latex'

  def __init__(self, *args, **kwargs):
    super(LatexBranch, self).__init__(*args, **kwargs)

    if not self.parent:
      self.context.AddMacros(GetPublicMacros(Macros))


class Macros:
  # pylint: disable=anomalous-backslash-in-string

  TextPercent = StaticAppendTextCallback('\%', public_name='text.percent')
  TextAmpersand = StaticAppendTextCallback('\&', public_name='text.ampersand')
  TextUnderscore = StaticAppendTextCallback('\_', public_name='text.underscore')
  TextDollar = StaticAppendTextCallback('\$', public_name='text.dollar')
  TextHash = StaticAppendTextCallback('\#', public_name='text.hash')
  TextNbsp = StaticAppendTextCallback('~', public_name='text.nbsp')
  TextSoftHyphen = StaticAppendTextCallback('\-', public_name='text.softhyphen')
  TextDashEn = StaticAppendTextCallback('--', public_name='text.dash.en')
  TextDashEm = StaticAppendTextCallback('---', public_name='text.dash.em')
