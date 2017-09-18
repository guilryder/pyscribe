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

% Generic packages
\RequirePackage{fixltx2e}          % \textsubscript{}
\RequirePackage{xspace}            % Automatic spacing
\RequirePackage[normalem]{ulem}    % Underlining, striking out
\RequirePackage{ifpdf}             % PDF mode detection
\RequirePackage[utf8]{inputenc}    % Accents, special characters
\RequirePackage[T1]{fontenc}       % French guillemets
\RequirePackage{numprint}          % Number formatting
\RequirePackage{textcomp}          % TS1 encoding
\RequirePackage{graphicx}          % Images

% PDF-specific settings
\ifpdf
\RequirePackage[pdftex,colorlinks=true,linkcolor=blue]{hyperref}
\else
\RequirePackage[hypertex]{hyperref}
\fi

% Metadata
\newcommand\titleset[1]{
  \newcommand\@maintitle{#1}
  \hypersetup{pdftitle=\@maintitle}
}
\newcommand\authorset[1]{
  \author{#1}
  \hypersetup{pdfauthor=\@author}
}
\newcommand\languageset[1]{
  \usepackage[#1]{babel}
  \ifdefined\frenchbsetup\frenchbsetup{og=,fg=}\fi
}
