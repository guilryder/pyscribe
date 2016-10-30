$$whitespace.skip

$macro.new[file.output2source(path)][../$path]
$macro.new[file.output2core(path)][$file.source2core[$file.output2source[$path]]]

$macro.new[format.init.xhtml][$macro.new[format.select(if.xhtml,if.latex)][$if.xhtml]]
$macro.new[format.init.latex][$macro.new[format.select(if.xhtml,if.latex)][$if.latex]]
$macro.call[format.init.$output.format]


$macro.new[root.create(basename,contents)][
  $branch.create.root[$macro.call[root.branch.type.$output.format]][root][
    $macro.call[output.filename.$output.format][$basename]]
  $macro.new[root.basename][$basename]

  $branch.write[root][
    $macro.call[root.open.$output.format]
    $contents
    $macro.call[root.close.$output.format]
  ]
]


################################################################################
# Device size
# $device.size = 'small' (default) or 'large'

$if.def[device.size][][$macro.new[device.size][small]]
$macro.new[device.size.init.small][$macro.new[device.size.select(if.small,if.large)][$if.small]]
$macro.new[device.size.init.large][$macro.new[device.size.select(if.small,if.large)][$if.large]]
$macro.call[device.size.init.$device.size]

$macro.new[formatsize.select(if.xhtml,if.latex.small,if.latex.large)][
  $format.select[
    $if.xhtml
  ][
    $device.size.select[
      $if.latex.small
    ][
      $if.latex.large
    ]
  ]
]


################################################################################
# Common

# Various
$macro.new[text.colon][$format.select[^:][\string^:]]

$macro.new[linebreak.small][$formatsize.select[][$\][]]
$macro.new[newline.large][$formatsize.select[][][$newline]]

$macro.new[roman.smallcaps(number)][
  $fmt.smallcaps[$case.lower[$roman[$number]]]
]

# Abbreviations
$macro.new[ier][$format.select[$fmt.superscript[er]][\ier{}]]
$macro.new[iere][$format.select[$fmt.superscript[re]][\iere{}]]
$macro.new[ieme][$format.select[$fmt.superscript[e]][\ieme{}]]
$macro.new[no][$format.select[n$fmt.superscript[o]][\no{}]]
$macro.new[No][$format.select[N$fmt.superscript[o]][\No{}]]

# Text formatting
$macro.new[fmt.macro.new(macro.name,xhtml.macro,xhtml.arg,latex.macro,latex.arg)][
  $macro.new[$macro.name(contents)][
    $format.select[
      $macro.call[$xhtml.macro][$xhtml.arg][$contents]
    ][
      $macro.call[$latex.macro][$latex.arg][$contents]
    ]
  ]
]
$fmt.macro.new[fmt.bold][fmt.tag][b][fmt.latex][\textbf]
$fmt.macro.new[fmt.italic][fmt.tag][i][fmt.latex][\textit]
$fmt.macro.new[fmt.sansserif][fmt.css][sansserif][fmt.latex][\textsf]
$fmt.macro.new[fmt.script][fmt.css][script][fmt.latex][\scripttext]
$fmt.macro.new[fmt.smallcaps][fmt.css][smallcaps][fmt.latex][\textsc]
$fmt.macro.new[fmt.strikeout][fmt.tag][s][fmt.latex][\sout]
$fmt.macro.new[fmt.subscript][fmt.tag][sub][fmt.latex][\textsubscript]
$fmt.macro.new[fmt.superscript][fmt.tag][sup][fmt.latex][\textsuperscript]
$fmt.macro.new[fmt.typewriter][fmt.css][typewriter][fmt.latex][\texttt]
$fmt.macro.new[fmt.underline][fmt.tag][u][fmt.latex][\underline]
$fmt.macro.new[fmt.size.p1][fmt.css][sizep1][fmt.tex][\large]
$fmt.macro.new[fmt.size.p2][fmt.css][sizep2][fmt.tex][\Large]
$fmt.macro.new[fmt.size.p3][fmt.css][sizep3][fmt.tex][\LARGE]
$fmt.macro.new[fmt.size.p4][fmt.css][sizep4][fmt.tex][\Huge]

# Paragraph formatting
$macro.new[para.macro.new(macro.name,css.class,tex.command)][
  $macro.new[$macro.name(contents)][
    $format.select[
      $para.css[$css.class][$contents]
    ][
      $para.tex[$tex.command][$contents]
    ]
  ]
]
$para.macro.new[para.center][center][\centering]
$para.macro.new[para.flushleft][flushleft][\raggedright]
$para.macro.new[para.flushright][flushright][\raggedleft]
$para.macro.new[para.bold][bold][\bfseries]
$para.macro.new[para.italic][italic][\itshape]
$para.macro.new[para.sansserif][sansserif][\sf]
$para.macro.new[para.typewriter][typewriter][\ttfamily]


################################################################################
# XHTML

$macro.new[output.filename.xhtml(basename)][$basename^.html]
$macro.new[root.branch.type.xhtml][xhtml]

$macro.new[root.open.xhtml][
  # Helpers
  $macro.new[tag(name,level,contents)][$tag.open[$name][$level]$contents$tag.close[$name]]
  $macro.new[tag.empty(name,level)][$tag[$name][$level][]]

  # <head> tags
  $macro.new[head.append(content)][
    $branch.write[head][$content$newline]
  ]
  # <link rel="stylesheet" type="text/css" href="..."/>
  $macro.new[css.file(css.filename)][
    $head.append[
      $tag[link][para][
        $tag.attr.set[current][rel][stylesheet]
        $tag.attr.set[current][type][text/css]
        $tag.attr.set[current][href][$css.filename]
      ]
    ]
  ]
  # <meta name="..." content="..."/>
  $macro.new[head.meta.name(name,content)][
    $head.append[
      $tag[meta][block][
        $tag.attr.set[current][name][$name]
        $tag.attr.set[current][content][$content]
      ]
    ]
  ]
  # <meta http-equiv="..." content="..."/>
  $macro.new[head.meta.httpequiv(httpequiv,content)][
    $head.append[
      $tag[meta][block][
        $tag.attr.set[current][http-equiv][$httpequiv]
        $tag.attr.set[current][content][$content]
      ]
    ]
  ]
  # <style tyle="text/css">...</style>
  $macro.new[css.inline(css.contents)][
    $branch.write[style][
      $typo.set[neutral]
      $macro.new[par][]
      $tag[style][para][
        $tag.attr.set[current][type][text/css]
        $css.contents
      ]
    ]
  ]

  # <head> contents
  $branch.write[head][
    $branch.create.sub[style]$newline
    $branch.append[style]
  ]
  $css.file[$file.output2core[core.css]]

  # Metadata
  $macro.new[metadata.title.set(title.file,title.book)][
    $head.append[$tag[title][block][$title.file]]
  ]
  $macro.new[metadata.author.set(author)][
    $head.meta.name[author][$author]
  ]
  $macro.new[metadata.language.set(language.code)][
    $head.meta.name[dc.language][$language.code]
    $head.meta.httpequiv[content-language][$language.code]
  ]

  # Headers
  $counter.create[header.level1.counter]
  $counter.create[header.level2.counter]
  $macro.new[header.level1.counter.child.reset][$header.level2.counter.set[0]]
  $macro.new[header.level2.counter.child.reset][]
  $macro.new[header.incr(level)][
    $macro.call[header.level$level^.counter.incr]
    $macro.call[header.level$level^.counter.child.reset]
  ]
  $macro.new[header.before(level)][
    $footnotes.flush
  ]
  $macro.new[header(level,title)][
    $header.withtoc[$level][$title][$title]
  ]
  $macro.new[header.withtoc(level,title.toc,title.doc)][
    $header.before[$level]
    $header.incr[$level]
    $tag[h$level][para][$header.title.numbered[$level][$title.doc]]
  ]
  $macro.new[header.title.numbered(level,title.doc)][
    $macro.call[header.level$level^.counter.fmt]~~~$title.doc
  ]
  $macro.new[header.nonumber(level,title)][
    $header.before[$level]
    $macro.call[header.level$level^.counter.child.reset]
    $tag[h$level][para][$title]
  ]

  # Vertical spacing
  $macro.new[bigskip][$tag.class.add[previous][bigskip]]
  $macro.new[medskip][$tag.class.add[previous][medskip]]
  $macro.new[smallskip][$tag.class.add[previous][smallskip]]

  # Text formatting
  $macro.new[fmt.tag(tag.name,contents)][
    $tag[$tag.name][inline][$contents]
  ]
  $macro.new[fmt.css(css.class,contents)][
    $tag[span][inline][
      $tag.class.add[current][$css.class]
      $contents
    ]
  ]
  $macro.new[number(number)][$typo.number[$number]]

  # Paragraph formatting
  $macro.new[para.css(css.class,contents)][
    $tag[div][block,autopara=p][
      $tag.class.add[nonauto][$css.class]
      $contents
    ]
  ]
  $macro.new[para.block.css(css.class,contents)][
    $tag[div][block][
      $tag.class.add[nonauto][$css.class]
      $contents
    ]
  ]
  $macro.new[para.noindent][$tag.class.add[para][noindent]]
  $macro.new[para.nospace.before][$tag.class.add[para][nospace-before]]
  $macro.new[para.nospace.after][$tag.class.add[para][nospace-after]]

  # Lists
  $macro.new[list.itemize(contents)][$tag[ul][block][$contents]]
  $macro.new[list.enumerate(contents)][$tag[ol][block][$contents]]
  $macro.new[list.item(contents)][$tag[li][block][$contents]]

  # Link IDs
  $counter.create[id.counter]
  $macro.new[id.new][$id.counter.incr]
  $macro.new[id.current(prefix)][$prefix$id.counter]
  $macro.new[id.attr.set.custom(id)][$tag.attr.set[current][id][$id]]
  $macro.new[id.href.set.custom(id)][$tag.attr.set[current][href][^#$id]]
  $macro.new[id.attr.set(prefix)][$id.attr.set.custom[$id.current[$prefix]]]
  $macro.new[id.href.set(prefix)][$id.href.set.custom[$id.current[$prefix]]]

  # Footnotes
  # $footnotes.add[contents] - adds a new footnote
  # $footnotes.flush - writes all footnotes since the last flush
  $counter.create[footnotes.counter]

  # Creates a new branch for the footnotes, puts the ID in $footnotes.branch.
  # The branch contains a header, therefore should be appended only if it
  # contains at least one footnote.
  $macro.new[footnotes.reset][
    $branch.create.sub[!footnotes.branch]
    $branch.write[$footnotes.branch][$tag.empty[hr][para]]
    $footnotes.counter.set[0]
  ]

  $macro.new[footnotes.flush][
    # Do nothing if no footnotes have been recorded.
    $footnotes.counter.if.positive[
      $para.css[footnotes][$branch.append[$footnotes.branch]]
      $footnotes.reset
    ]
  ]

  # Footnote mark link
  # source: prefix of the ID to give to the mark
  # dest: prefix of the ID of the link target
  $macro.new[footnotes.counter.mark(source,dest)][
    $tag[a][inline][
    $id.attr.set[$source]
    $id.href.set[$dest]
    ^[$footnotes.counter^]]
  ]

  $macro.new[footnotes.add(contents)][
    $footnotes.counter.incr
    $id.new
    ^ $footnotes.counter.mark[fnl][fnc]
    $branch.write[$footnotes.branch][$footnotes.counter.mark[fnc][fnl]^ $contents$par]
  ]

  $footnotes.reset

  # Various
  $macro.new[\][$tag.empty[br][inline]]
  $macro.new[line.break][$\]
  $macro.new[page.new][$tag.class.add[previous][page-after]]
  $macro.new[page.before.avoid][$tag.class.add[previous][page-after-avoid]]
  $macro.new[separator][
    $tag[div][block][
      $tag.class.add[nonauto][separator]
      *~~~*~~~*
    ]
  ]
  $macro.new[page.same(content)][$para.css[page-same][$content]]
  $macro.new[image(alt.text,image.file.noext,css.class,width.latex)][
    $tag[img][inline][
      $tag.attr.set[current][alt][$alt.text]
      $tag.attr.set[current][src][$image.file.noext^.jpg]
      $tag.class.add[current][$css.class]
    ]
  ]

  $typo.set[french]
]

$macro.new[root.close.xhtml][
  $footnotes.flush
]


################################################################################
# Latex

$macro.new[output.filename.latex(basename)][$basename^ -^ $device.size^.tex]
$macro.new[root.branch.type.latex][latex]

$macro.new[root.open.latex][
  \documentclass$device.size.select[^[ebook^]][]{pyscribe}$newline

  # Latex helpers
  $macro.new[latex.env(name,contents)][
    \begin{$name}
      $newline
      $contents
      $newline
    \end{$name}
  ]
  $macro.new[latex.env.new(macro.name,env.name)][
    $macro.new[$macro.name(contents)][$latex.env[$env.name][$contents]]
  ]
  $macro.new[latex.env.new.para(macro.name,env.name)][
    $macro.new[$macro.name(contents)][
      $par
      $latex.env[$env.name][$contents]
      $par
    ]
  ]
  $macro.new[latex.macro.new(macro.name,cmd.name)][
    $macro.new[$macro.name(contents)][$fmt.latex[$cmd.name][$contents]]
  ]

  # Headers
  $macro.new[headers.config.sectionsonly.latex][
    $macro.new[header.level1.cmd][\section]
  ]
  $macro.new[headers.config.chaptersandsections.latex][
    $macro.new[header.level1.cmd][\chapter]
    $macro.new[header.level2.cmd][\section]
  ]
  $macro.new[header.level.cmd(level)][
    $macro.call[header.level$level^.cmd]
  ]
  $macro.new[header(level,title)][
    $header.level.cmd[$level]{$title}
  ]
  $macro.new[header.withtoc(level,title.toc,title.doc)][
    $header.level.cmd[$level]^[$title.toc^]{$title.doc}
  ]
  $macro.new[header.nonumber(level,title)][
    $header.level.cmd[$level]*{$title}
  ]
  $macro.new[section.nonumber(title)][\section*{$title}]
  $macro.new[section.withtoc(title.toc,title.doc)][\section^[$title.toc^]{$title.doc}]
  $latex.macro.new[chapter][\chapter]

  # Vertical spacing
  $macro.new[bigskip][\bigskip]
  $macro.new[medskip][\medskip]
  $macro.new[smallskip][\smallskip]

  # Text formatting
  $macro.new[fmt.latex(cmd.name,contents)][
    $cmd.name{$contents}
  ]
  $macro.new[fmt.tex(cmd.name,contents)][
    {$cmd.name^ $contents}
  ]
  $latex.macro.new[number][\nombre]

  # Paragraph formatting
  $macro.new[para.tex(cmd.name,contents)][
    $par{$cmd.name$newline
    $contents$par}
  ]
  $macro.new[para.noindent][\noindent^ ]
  $macro.new[para.nospace.before][\vspace{-\parskip}]
  $macro.new[para.nospace.after][\vspace{-\parskip}]

  # Lists
  $latex.env.new.para[list.itemize][itemize]
  $latex.env.new.para[list.enumerate][enumerate]
  $macro.new[list.item(contents)][\item $contents]

  # Footnotes
  $latex.macro.new[footnotes.add][\footnote]

  # Various
  $macro.new[\][\\]
  $macro.new[line.break][\newline]
  $macro.new[page.new][\newpage]
  $macro.new[page.before.avoid][\nopagebreak^[4^]]
  $macro.new[par][\par]
  $macro.new[separator][\separator]
  $latex.env.new[page.same][samepage]
  $macro.new[image(alt.text,image.file.noext,css.class,width.latex)][
    \ifx\pdfoutput\undefined\else$newline
    \includegraphics^[width=$width.latex^]{$image.file.noext}$newline
  ]
]

$macro.new[root.close.latex][
  $newline
  $newline
  \end{document}
  $newline
]
