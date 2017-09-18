\NeedsTeXFormat{LaTeX2e}[1999/01/01]
\ProvidesClass{pyscribe}[2011/07/18]

\newif\ifebook
\DeclareOption{ebook}{\ebooktrue}

\ProcessOptions\relax

\ifebook
\LoadClass[a4paper,oneside]{book}
\RequirePackage[papersize={90mm,120mm},margin=2mm]{geometry}
\RequirePackage{fourier}
\sloppy
\pagestyle{empty}

\else
\LoadClass[a4paper,oneside,11pt]{book}
\RequirePackage{a4wide}
\RequirePackage{lmodern}

\RequirePackage{slantsc}
\renewcommand\scitdefault{\scsldefault}
\fi
