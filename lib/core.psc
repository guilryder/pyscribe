$$whitespace.skip
$$special.chars.latex.mode

################################################################################
# Core helpers

$macro.new[file.output2input(path)][$dir.input.rel.output/$path]

$macro.new[identity(contents)][$contents]

$macro.new[macro.new.default(name,body.default)][
  $if.def[$name][][
    $macro.new[$name()][$body.default]
  ]
]


################################################################################
# Initialization

# Inline mode: embeds external files whenever possible instead of linking to
# them, to make the output file more self-contained.
# Typical use case: inlining *.css files.
# Usage: $inline.select[if inline mode][if not inline mode]
$macro.new.default[inline][0]
$if.eq[$inline][1][
  $macro.new[inline.select(if.inline,if.linked)][$if.inline]
][
  $macro.new[inline.select(if.inline,if.linked)][$if.linked]
]

# Validates the output format.
# Usage: $format.select[if html][if latex]
$macro.new[format.init.html][$macro.new[format.select(if.html,if.latex)][$if.html]]
$macro.new[format.init.latex][$macro.new[format.select(if.html,if.latex)][$if.latex]]
$macro.call[format.init.$format]


################################################################################
# Root branch

# Creates the default root branch writing into $file.output.basename.prefix,
# with the file extension that matches $format.
$macro.new[root.create(contents)][
  $branch.create.root[$macro.call[root.branch.type.$format]][root][
    $macro.call[output.ext.$format]
  ]

  $branch.write[root][
    $macro.call[root.open.$format]
    $root.open.hook
    $contents
    $macro.call[root.close.$format]
  ]
]

$macro.new[root.open.hook][
  $metadata.all.set
]


################################################################################
# Common

# Metadata
$macro.new[metadata.all.set][
  $metadata.title.set[$book.title]
  $metadata.author.set[$book.author]
  $metadata.language.set[$book.language]
  $format.select[][$preamble.append[$newline]]
]

# Map of language code to name.
$macro.new[language.name.fr][french]
$macro.new[language.name.en][english]

# Various
$macro.new[text.colon][$format.select[^:][\string^:]]

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
$macro.new[fmt.macro.new(macro.name,html.macro,html.arg,latex.macro,latex.arg)][
  $macro.new[$macro.name(contents)][
    $format.select[
      $macro.call[$html.macro][$html.arg][$contents]
    ][
      $macro.call[$latex.macro][$latex.arg][$contents]
    ]
  ]
]
$fmt.macro.new[fmt.bold][fmt.tag][b][fmt.latex][\textbf]
$fmt.macro.new[fmt.italic][fmt.tag][i][fmt.latex][\textit]
$fmt.macro.new[fmt.sansserif][fmt.css][sansserif][fmt.latex][\textsf]
$fmt.macro.new[fmt.script][fmt.css][script][fmt.latex][\scripttext]  # undefined in Latex
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

# Table of contents
$macro.new[page.toc.initialize][
  $if.def[page.toc.defined][][
    $macro.new[page.toc.defined][]
    $branch.create.sub[toc]
  ]
]
$macro.new[page.toc.withtitle(title)][
  $format.select[
    $page.toc.initialize
    $footnotes.flush
    $tag[nav][block][
      $epub.type.set[toc][nonauto]
      $para.block.css[toc-title][$title]
      $para.block.css[toc][$branch.append[toc]]
    ]
  ][
    $document.preamble.append[
      \addtocontents{toc}{\protect\thispagestyle{empty}}$newline
    ]
    \renewcommand\contentsname{$title}$newline
    \clearpage
    \pagestyle{empty}
    \tableofcontents
  ]
]
$macro.new[page.toc.append(contents)][
  $page.toc.initialize
  $branch.write[toc][$contents]
]


################################################################################
# HTML

$macro.new[output.ext.html][.html]
$macro.new[root.branch.type.html][html]

$macro.new.default[core.css.filename][file:///$dir.lib/core.css]

$macro.new[root.open.html][
  # Helpers
  $macro.new[tag(name,level,contents)][$tag.open[$name][$level]$contents$tag.close[$name]]
  $macro.new[tag.empty(name,level)][$tag[$name][$level][]]

  # <head> tags
  $macro.new[head.append(contents)][
    $branch.write[head][$contents$newline]
  ]
  # <link rel="stylesheet" type="text/css" href="..."/>
  $macro.new[css.file.link(css.filename)][
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
      $tag[style][para][
        $tag.attr.set[current][type][text/css]
        $tag.body.raw[$css.contents]
      ]
    ]
  ]

  # CSS file inclusion/linking.
  $macro.new[css.file(css.filename)][
    $inline.select[
      $css.inline[$include.text[$dir.output/$css.filename]]
    ][
      $css.file.link[$css.filename]
    ]
  ]

  # <head> contents
  $branch.write[head][
    $branch.create.sub[style]
    $branch.write[style][$typo.set[neutral]]
    $branch.append[style]
  ]
  $if.eq[$core.css.filename][][][$css.file[$core.css.filename]]

  # Metadata
  $macro.new[metadata.title.set(title)][
    $head.append[$tag[title][block][$eval.text[$title]]]
  ]
  $macro.new[metadata.author.set(author)][
    $head.meta.name[author][$author]
  ]
  $macro.new[metadata.language.set(language.code)][
    $head.meta.name[dc.language][$language.code]
    $head.meta.httpequiv[content-language][$language.code]
    $typo.set[$macro.call[language.name.$language.code]]
  ]

  # Headers

  # Declares a single header level. Each level:
  # * has a counter named header.levelN.counter
  # * resets numbering of the following levels
  # Requires $header.level.count to be set.
  # $level: index of the level to declare
  # $level.next: $level + 1
  # $level.count: index of the last level
  $macro.new[header.level.declare(level,level.next)][
    $counter.create[header.level$level^.counter]
    $macro.new[header.level$level^.counter.child.reset][
      $if.eq[$level][$header.level.count][][
        $macro.call[header.level$level.next^.counter.set][0]
        $macro.call[header.level$level.next^.counter.child.reset]
      ]
    ]
  ]
  $macro.new[header.level.count][8]
  $header.level.declare[1][2]
  $header.level.declare[2][3]
  $header.level.declare[3][4]
  $header.level.declare[4][5]
  $header.level.declare[5][6]
  $header.level.declare[6][7]
  $header.level.declare[7][8]
  $header.level.declare[8][9]

  $macro.new[header.incr(level)][
    $macro.call[header.level$level^.counter.incr]
    $macro.call[header.level$level^.counter.child.reset]
  ]
  $macro.new[header.before(level)][
    $if.eq[$level][1][$footnotes.flush][]
    $if.eq[$level][2][$footnotes.flush][]
  ]
  $macro.new[header(level,title)][
    $header.withtoc[$level][$title][$title]
  ]
  $macro.new[header.withtoc(level,title.toc,title.doc)][
    $header.before[$level]
    $header.incr[$level]
    $macro.call[header.render][$level][
      $header.title.numbered.toc[$level][$title.toc]
    ][
      $header.title.numbered[$level][$title.doc]
    ]
  ]
  $macro.new[header.title.numbered(level,title)][
    $macro.call[header.level$level^.counter.fmt]~~~$title
  ]
  $macro.new[header.title.numbered.toc(level,title.toc)][
    $macro.call[header.level$level^.counter.fmt]. $title.toc
  ]
  $macro.new[header.nonumber(level,title)][
    $header.nonumber.withtoc[$level][$title][$title]
  ]
  $macro.new[header.nonumber.withtoc(level,title.toc,title.doc)][
    $header.before[$level]
    $macro.call[header.level$level^.counter.child.reset]
    $macro.call[header.render][$level][$title.toc][$title.doc]
  ]
  $macro.new[header.render(level,title.toc,title.doc)][
    $tag[h$level][para][
      $if.def[header.level$level^.toc.use][
        $header.render.toc[$level][$title.toc]
      ][]
      $title.doc
    ]
  ]

  # Table of contents
  $macro.new[header.render.toc(level,title)][
    $id.new
    $id.attr.set[header][current]
    $header.render.toc.entry[$level][
      $tag[a][inline][
        $id.href.set[header]
        $title
      ]
    ]
  ]
  $macro.new[header.render.toc.entry(level,contents)][
    $page.toc.append[
      $tag[p][para][
        $tag.class.add[current][toc$level]
        $contents
      ]
    ]
  ]

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
  $macro.new[para.css.custom(level,css.class,contents)][
    $tag[div][$level][
      $tag.class.add[nonauto][$css.class]
      $contents
    ]
  ]
  $macro.new[para.css(css.class,contents)][
    $para.css.custom[block,autopara=p][$css.class][$contents]
  ]
  $macro.new[para.block.css(css.class,contents)][
    $para.css.custom[block][$css.class][$contents]
  ]
  $macro.new[para.noindent][$tag.class.add[para][noindent]]
  $macro.new[para.nospace.before][$tag.class.add[para][nospace-before]]
  $macro.new[para.nospace.after][$tag.class.add[para][nospace-after]]

  # Vertical spacing
  $macro.new[bigskip][$tag.class.add[previous][bigskip]]
  $macro.new[medskip][$tag.class.add[previous][medskip]]
  $macro.new[smallskip][$tag.class.add[previous][smallskip]]

  # Lists
  $macro.new[list.itemize(contents)][$tag[ul][block][$contents]]
  $macro.new[list.enumerate(contents)][$tag[ol][block][$contents]]
  $macro.new[list.item(contents)][$tag[li][block][$contents]]

  # Links
  $macro.new[hyperlink(url,contents)][
    $tag[a][inline][
      $tag.attr.set[current][href][$url]
      $contents
    ]
  ]

  # Link IDs
  $counter.create[id.counter]
  $macro.new[id.new][$id.counter.incr]
  $macro.new[id.current(prefix)][$prefix$id.counter]
  $macro.new[id.attr.set.custom(id,element.target)][$tag.attr.set[$element.target][id][$id]]
  $macro.new[id.href.set.custom(id)][$tag.attr.set[current][href][^#$id]]
  $macro.new[id.attr.set(prefix,element.target)][$id.attr.set.custom[$id.current[$prefix]][$element.target]]
  $macro.new[id.href.set(prefix)][$id.href.set.custom[$id.current[$prefix]]]

  # Named references.
  $macro.new[reference.target(id,element.target)][
    $id.attr.set.custom[ref-$id][$element.target]
  ]
  $macro.new[reference.target.inline(id,contents)][
    $tag[span][inline][
      $reference.target[$id][current]
      $contents
    ]
  ]
  $macro.new[reference.link(target.id,contents)][
    $tag[a][inline][
      $id.href.set.custom[ref-$target.id]
      $contents
    ]
  ]

  # Epub
  $macro.new[epub.type.set(type,element.target)][
    $tag.attr.set[$element.target][{http://www.idpf.org/2007/ops}type][$type]
  ]

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
  # source: prefix of the ID to give to the mark, ignored if empty
  # dest: prefix of the ID of the link target
  $macro.new[footnotes.counter.mark(source,dest)][
    $tag[a][inline][
      $epub.type.set[noteref][current]
      $if.eq[$source][][][$id.attr.set[$source][current]]
      $id.href.set[$dest]
      ^[$footnotes.counter^]
    ]
  ]

  $macro.new[footnotes.add(contents)][
    $footnotes.counter.incr
    $id.new
    ^ $footnotes.counter.mark[fnl][fnc]
    $branch.write[$footnotes.branch][
      $tag[aside][block,autopara=p][
        $epub.type.set[footnote][nonauto]
        $id.attr.set[fnc][nonauto]
        $footnotes.counter.mark[][fnl]^ $contents$par
      ]
    ]
  ]

  $footnotes.reset

  # Various

  $macro.new[\][$tag.empty[br][inline]]
  $macro.new[line.break][$\]

  $macro.new[page.new][$tag.class.add[previous][page-after]]
  $macro.new[page.before.avoid][$tag.class.add[previous][page-after-avoid]]
  $macro.new[page.same(contents)][$para.css[page-same][$contents]]

  $macro.new[image(alt.text,image.file.noext,ext.html,css.class,width.latex)][
    $tag[img][inline][
      $tag.attr.set[current][alt][$alt.text]
      $tag.attr.set[current][src][$image.file.noext^.$ext.html]
      $tag.class.add[current][$css.class]
    ]
  ]

  $macro.new[code.nopipe(contents)][$fmt.typewriter[$contents]]
]

$macro.new[root.close.html][
  $footnotes.flush
]


################################################################################
# Latex

$macro.new[output.ext.latex][^.tex]
$macro.new[root.branch.type.latex][latex]
$macro.new[latex.class.options][]
$macro.new[latex.languages.extra][]  # comma-separated with trailing comma

$macro.new[root.open.latex][
  $branch.create.sub[preamble]
  $macro.new[preamble.append(contents)][
    $branch.write[preamble][$contents]
  ]
  $macro.new[preamble.append.section(contents)][
    $preamble.append[$contents$newline$newline]
  ]

  $branch.create.sub[document.preamble]
  $macro.new[document.preamble.append(contents)][
    $branch.write[document.preamble][$contents]
  ]

  # Metadata
  $macro.new[metadata.title.set(title)][
    $preamble.append[\titleset{$eval.text[$title]}$newline]
  ]
  $macro.new[metadata.author.set(author)][
    $preamble.append[\authorset{$eval.text[$author]}$newline]
  ]
  $macro.new[metadata.language.set(language.code)][
    $preamble.append[
      \languageset{$latex.languages.extra$macro.call[language.name.$language.code]}$newline
    ]
  ]

  # Latex helpers
  $macro.new[latex.cmd(name)][$name$latex.sep]
  $macro.new[latex.env(name,contents)][
    $latex.env.custom[$name][$newline$contents]
  ]
  $macro.new[latex.env.custom(name,contents)][
    \begin{$name}
      $contents$newline
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
    $macro.new[header.level1.cmdname][section]
    $macro.new[header.level2.cmdname][subsection]
  ]
  $macro.new[headers.config.chaptersandsections.latex][
    $macro.new[header.level1.cmdname][chapter]
    $macro.new[header.level2.cmdname][section]
    $macro.new[header.level3.cmdname][subsection]
  ]
  $macro.new[header.level.cmd(level)][
    \$macro.call[header.level$level^.cmdname]
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
  $macro.new[header.nonumber.withtoc(level,title.toc,title.doc)][
    $header.level.cmd[$level]*{$title.doc}
    \addcontentsline{toc}{$macro.call[header.level$level^.cmdname]}{$title.toc}
  ]
  $macro.new[section.nonumber(title)][\section*{$title}]
  $macro.new[section.withtoc(title.toc,title.doc)][\section^[$title.toc^]{$title.doc}]
  $latex.macro.new[chapter][\chapter]

  # Text formatting
  $macro.new[fmt.latex(cmd.name,contents)][
    $cmd.name{$contents}
  ]
  $macro.new[fmt.tex(cmd.name,contents)][
    {$latex.cmd[$cmd.name]$contents}
  ]
  $latex.macro.new[number][\numprint]

  # Paragraph formatting
  $macro.new[para.tex(cmd.name,contents)][
    $par{$cmd.name$newline
    $contents$par}
  ]
  $macro.new[para.noindent][\noindent^ ]
  $macro.new[para.nospace.before][\vspace{-\parskip}]
  $macro.new[para.nospace.after][\vspace{-\parskip}]

  # Vertical spacing
  $macro.new[bigskip][\bigskip]
  $macro.new[medskip][\medskip]
  $macro.new[smallskip][\smallskip]

  # Lists
  $latex.env.new.para[list.itemize][itemize]
  $latex.env.new.para[list.enumerate][enumerate]
  $macro.new[list.item(contents)][$latex.cmd[\item]$contents]

  # Links
  $macro.new[hyperlink(url,contents)][
    \href{$url}{$contents}
  ]

  # Epub
  $macro.new[epub.type.set(type,element.target)][]

  # Footnotes
  $latex.macro.new[footnotes.add][\footnote]

  # Various

  $macro.new[\][$latex.cmd[\\]]
  $macro.new[line.break][$latex.cmd[\newline]]
  $macro.new[par][$latex.cmd[\par]]

  $macro.new[page.new][$latex.cmd[\clearpage]]
  $macro.new[page.before.avoid][\nopagebreak^[4^]]
  $latex.env.new[page.same][samepage]

  $macro.new[image(alt.text,image.file.noext,ext.html,css.class,width.latex)][
    \ifx\pdfoutput\undefined\else$newline
    \includegraphics^[width=$width.latex^]{$image.file.noext}$newline
  ]

  $macro.new[code.nopipe(contents)][\verb|$contents|]

  # Latex header

  # Class options: set 'ebook' in small mode, append the custom options.
  # Omit the brackets if no options.
  \documentclass$if.eq[$latex.class.options][][][^[$latex.class.options^]]{pyscribe}$newline
  $branch.append[preamble]
  \begin{document}$newline
  $branch.append[document.preamble]
]

$macro.new[root.close.latex][
  $newline
  $newline
  \end{document}$newline
]
