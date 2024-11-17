#!/usr/bin/env pyscribe
$$whitespace.skip
$include[$dir.lib/core]

################################################################################
# HTML

$macro.wrap[root.open.html][][
  # Cover
  $macro.new[page.title][
    $para.center[
      $fmt.size.p2[$fmt.bold[$book.title]]
    ]
  ]

  # Headers
  $macro.new[header.level1.toc.use][]
  $macro.new[header.level1.counter.fmt][$roman[$header.level1.counter]]
  $macro.new[header.level2.toc.use][]
  $macro.new[header.level2.counter.fmt][$alpha.latin[$header.level2.counter])]
  $macro.new[header.level3.counter.fmt][$header.level3.counter^.]
]

################################################################################
# Latex

$$special.chars.latex.mode
$macro.wrap[root.open.latex][][
  # Cover
  $macro.new[page.title][
    $latex.env[center][
      $fmt.size.p2[$book.title $par]
    ]
  ]

  # Headers
  $headers.config.chaptersandsections.latex

  # Typographies
  $macro.new[typo.set(typo)][
    \selectlanguage{$if.eq[$typo][neutral][english][$typo]}
  ]

  # Various
  $preamble.append.section[
    \newcommand\scripttext^[1^]{{\fontfamily{pzc}\selectfont\large^#1}}
  ]
]
$$special.chars.escape.all

################################################################################
# Testing

$$whitespace.preserve

$macro.new[repeat.2lines(body)][
  $repeat[2][$repeat[10][$body] $\]
]

$macro.new[test.typography(contents)][
  $macro.new[test.typography.typo(typo)][
    $typo.set[$typo]Typography $typo:
    $contents
    $par $medskip
  ]
  $medskip
  $para.flushleft[
    $test.typography.typo[neutral]
    $test.typography.typo[english]
    $test.typography.typo[french]
  ]
]

$macro.new[para.macro(macro.name,contents)][
  $par$medskip
  $fmt.typewriter[$text.dollar$macro.name]^ $contents
]

$macro.new[para.macro.linewrap(macro.name)][
  $para.macro[$macro.name][$repeat[10][beforebeforebefore$macro.call[$macro.name]afterafterafter^ ]]
]

$$whitespace.skip


$macro.new[book.title][Test Title]
$macro.new[book.author][Test Author]
$macro.new[book.language][fr]

$macro.new[latex.class.options][demo]
$macro.new[latex.languages.extra][english,]

$root.create[
$$whitespace.preserve
$page.title
$page.new

$page.toc.withtitle[Sommaire]

$format.select[
  $reference.target[dummy-target][para] Used as link target
][]

$header[1][Typography]

Special characters: % & \ $text.caret _ $text.dollar $text.hash © ® ™

$test.typography[
  sep... sep...sep $\
  <<inside>> sep << inside >> sep <<~inside~>> sep $\
  sep `inside' sep ` inside ' sep ``inside'' sep `` inside '' sep $\
  sep! sep: sep; sep? sep!? sep, sep $\
  sep ! sep : sep ; sep ? sep !? sep, sep $\
  sep~! sep~: sep~; sep~? sep~!? sep,~sep $\
  sep ~ ! sep ~ : sep ~ ; sep ~ ? sep ~ !? sep, ~ sep
]

$para.macro.linewrap[^-]
$para.macro.linewrap[text.nbsp]
$para.macro.linewrap[text.nbsp.thin]
$para.macro.linewrap[text.sp.fixed]

$header[1][$fmt.typewriter[core.psc] macros]

$header[2][Various]

$para.macro[$text.backslash][before $\ after]
$para.macro[line.break][before $\ after]

$para.macro[text.backslash][before$text.backslash^after]
$para.macro[text.colon][before$text.colon^after]
$para.macro[roman.smallcaps][14 = $roman.smallcaps[14] = XIV]
$para.macro[code.nopipe][$code.nopipe[foo@example.com]]

$para.macro[page.new][before $par $page.new $par after]
$para.macro[page.before.avoid][before $par $page.before.avoid $par after]
$par $repeat[30][Before $par]
$para.macro[page.same][$page.same[$repeat[30][Inside $par]]]

$para.macro[image][
  $image[Image alt text][
    $format.select[data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA
AAAFCAYAAACNbyblAAAAHElEQVQI12P4//8/w38GIAXDIBKE0DHxgljNBAAO9TXL0Y4OHwAAAABJRU5ErkJggg==][non-existing-image]][png][][.5^\linewidth,draft]
]

$header[2][Abbreviations]

$para.macro[ier][Le 1$ier élément.]
$para.macro[iere][La 1$iere chose.]
$para.macro[ieme][Le 3$ieme élément.]
$para.macro[no][Le $no^7 est ici.]
$para.macro[No][$no^7]

$header[2][Text formatting]

$macro.new[para.macro.text.formatting(macro.name)][
  $para.macro[$macro.name][
    ^ $macro.call[$macro.name][one
      ^ $macro.call[$macro.name][two
        ^ $macro.call[$macro.name][three]]]
  ]
]

$para.macro.text.formatting[fmt.bold]
$para.macro.text.formatting[fmt.italic]
$para.macro.text.formatting[fmt.sansserif]
$para.macro.text.formatting[fmt.script]
$para.macro.text.formatting[fmt.smallcaps]
$para.macro.text.formatting[fmt.strikeout]
$para.macro.text.formatting[fmt.typewriter]
$para.macro.text.formatting[fmt.subscript]
$para.macro.text.formatting[fmt.superscript] M$fmt.superscript[me] Durand
$para.macro.text.formatting[fmt.typewriter]
$para.macro.text.formatting[fmt.underline]
$para.macro.text.formatting[fmt.size.p1]
$para.macro.text.formatting[fmt.size.p2]
$para.macro.text.formatting[fmt.size.p3]
$para.macro.text.formatting[fmt.size.p4]

$para.macro[number][
  $\ $test.typography[
    sep $number[12]
    sep $number[-12.3]
    sep $number[1234567.8901]
    sep $number[-1234567.8901]
    sep $number[1234567,8901]
    sep $number[+1234567,8901]
  ]
]

$header[2][Paragraph formatting]

$macro.new[inside][$repeat.2lines[Inside^ ]]

$macro.new[para.macro.para.formatting(macro.name)][
  $para.macro[$macro.name][
    $macro.call[$macro.name][$inside]
  ]
]

$macro.new[para.macro.para.prefix(macro.name)][
  $para.macro[$macro.name][
    $macro.call[$macro.name]$inside
  ]
]

$para.center[$repeat.2lines[$text.dollar^para.center^ ]
$para.flushleft[$repeat.2lines[$text.dollar^para.left^ ]
$para.flushright[$repeat.2lines[$text.dollar^para.right^ ]
$para.center[$repeat.2lines[$text.dollar^para.center^ ]
$para.flushleft[$repeat.2lines[$text.dollar^para.left^ ]
$para.flushright[$repeat.2lines[$text.dollar^para.right^ ]
]]]]]]

$para.macro.para.formatting[para.bold]
$para.macro.para.formatting[para.italic]
$para.macro.para.formatting[para.sansserif]
$para.macro.para.formatting[para.typewriter]
$para.macro.para.prefix[para.noindent]
$para.macro.para.prefix[para.nospace.before]$par After $par
$para.macro.para.prefix[para.nospace.after]$par After $par

$header[2][Vertical spacing]

$para.macro[bigskip][Before$par $bigskip After]
$para.macro[medskip][Before$par $medskip After]
$para.macro[smallskip][Before$par $medskip After]

$header[2][Lists]

$list.itemize[
  $list.item[
    One
    $list.enumerate[
      $list.item[One One]
      $list.item[One Two
        $list.enumerate[
          $list.item[One Two One]
          $list.item[One Two Two]
        ]
      ]
      $list.item[One Three]
    ]
  ]
  $list.item[Two]
  $list.item[Three
    $list.itemize[
      $list.item[Three One]
      $list.item[Three Two
        $list.itemize[
          $list.item[Three Two One]
          $list.item[Three Two Two]
        ]
      ]
      $list.item[Three Three]
    ]
  ]
]

$header[2][Links]

$para.macro[hyperlink][$hyperlink[https://example.org][hyperlink caption]]

$format.select[
  $reference.link[dummy-target][Links to the target above.]
][Reference targets not supported in LaTeX mode.]

$para.macro[footnotes.add][Before$footnotes.add[Footnote contents.] after.]

$header[3][Header level 3]
$para.macro[footnotes.add][Foonote two$footnotes.add[Foonote two contents.]]

$header[3][Header level 3 again]
$para.macro[footnotes.add][Foonote three$footnotes.add[Foonote three contents.]]

$format.select[
$header[2][Footnotes flushing]

Footnotes flushed after header level 2.

$para.macro[footnotes.add][Footnote four$footnotes.add[Footnote four contents.] restarts from 1.]

$para.macro[footnotes.flush][Before $footnotes.flush After]

$para.macro[footnotes.add][Footnote five$footnotes.add[Footnote five contents.]]
][]

$format.select[
# HTML
$header[2][HTML]

$css.inline[
$$special.chars.escape.none
  .red {
    color: red;
  }

  /* Special characters: ' " ` `` '' \ ^^ _ < > ? : ! */ # ignored
]$$special.chars.escape.all


$para.macro[para.css.custom][
  $para.css.custom[block,autopara=p][red][contents]
]

][
# Latex
]

]
