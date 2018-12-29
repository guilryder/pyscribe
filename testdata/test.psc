#!/usr/bin/env pyscribe
$$whitespace.preserve
$include[$dir.lib/core]

################################################################################
# XHTML

$macro.wrap[root.open.xhtml][][
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

$macro.wrap[root.open.latex][][
  # Cover
  $macro.new[page.title][
    \makeatletter
    \begin{document}
    \begin{center}
      {\LARGE \@maintitle \par}
    \end{center}
    \makeatother
  ]

  # Headers
  $headers.config.chaptersandsections.latex

  # Various
  \newcommand\scripttext^[1^]{{\fontfamily{pzc}\selectfont\large^#1}}$newline
]

################################################################################
# Testing

$macro.new[inside][
  Inside inside inside $\ Inside inside
]

$macro.new[repeat.thirty(body)][
  $repeat[10][$body]
  $repeat[10][$body]
  $repeat[10][$body]
]

$macro.new[test.typography(contents)][
  Neutral typography: $typo.set[neutral]$contents
  English typography: $typo.set[english]$contents
  French typography: $typo.set[french]$contents
]

$macro.new[para.macro(macro.name,contents)][
  $par$text.dollar$macro.name: $contents
]

$macro.new[para.macro.typography(macro.name,contents)][
  $para.macro[$macro.name][
    $test.typography[contents $\]
  ]
]


$macro.new[book.title][Test Title]
$macro.new[book.author][Test Author]
$macro.new[book.language][fr]

$macro.new[latex.class.options][demo]

$root.create[Test][
$page.title
$page.new

$page.toc.withtitle[Sommaire]

$format.select[
  $reference.target[dummy-target][para] Used as link target
][]

$header[1][Typography]

Special characters: % & _ $text.dollar $text.hash

$test.typography[
  Lorem... ipsum...dolor <<sit>> amet, consectetur `adipiscing' elit, ``sed do'' eiusmod! tempor: incididunt; ut? labore!? et dolore magna aliqua. $par
]

$para.macro[^-][$repeat.thirty[beforebeforebefore$-afterafterafter^ ]]

$header[1][$fmt.typewriter[core.psc] macros]

$header[2][Various]

$para.macro[$text.backslash][before $\ after]
$para.macro[line.break][before $\ after]
$para.macro[linebreak.small][Before $linebreak.small After]
$para.macro[newline.large][Before $newline.large After]

$para.macro[text.backslash][before$text.backslash^after]
$para.macro[text.colon][before$text.colon^after]
$para.macro[roman.smallcaps][Louis~$roman.smallcaps[14], Roi-Soleil]
$para.macro[code.nopipe][$code.nopipe[foo@example.com]]

$para.macro[page.new][before $par $page.new $par after]
$para.macro[page.before.avoid][before $par $page.before.avoid $par after]
$par $repeat.thirty[Before $par]
$para.macro[page.same][$page.same[$repeat.thirty[Inside $par]]]

$para.macro[image][
  $image[Image alt text][
    $format.select[data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA
AAAFCAYAAACNbyblAAAAHElEQVQI12P4//8/w38GIAXDIBKE0DHxgljNBAAO9TXL0Y4OHwAAAABJRU5ErkJggg==][non-existing-image]][png][][.5\linewidth,draft]
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

$para.macro.typography[number][
  separator $number[12]
  separator $number[-12.3]
  separator $number[1234567.8901]
  separator $number[-1234567.8901]
  separator $number[1234567,8901]
  separator $number[+1234567,8901]
]

$header[2][Paragraph formatting]

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

$para.macro.para.formatting[para.center]
$para.macro.para.formatting[para.flushleft]
$para.macro.para.formatting[para.flushright]
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

]
