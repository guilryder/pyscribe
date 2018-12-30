#!/usr/bin/env pyscribe
$$whitespace.skip
$include[$dir.lib/core]

$macro.new[book.title][Hello World]
$macro.new[book.author][Test Author]
$macro.new[book.language][fr]

# For hard-coded output filename: $root.create[Hello][...]
$root.create[$if.def[out.filename][$out.filename][Hello]][

Hello, World!

]
