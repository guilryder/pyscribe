\NeedsTeXFormat{LaTeX2e}[2018/12/01]
\ProvidesClass{pyscribe}[2011/07/18]

% Whether to format as an e-book: small page size, no margins.
\newif\ifebook
\DeclareOption{ebook}{\ebooktrue}

% Whether to use simple formatting for short, plain text documents:
% article class instead of book (except with the ebook option),
% simpler cover page.
\newif\ifsimple
\DeclareOption{simple}{\simpletrue}

\ProcessOptions\relax

\ifebook
\LoadClass[a4paper,oneside]{book}
\RequirePackage[papersize={90mm,120mm},margin=2mm]{geometry}
\RequirePackage{fourier}
\sloppy
\pagestyle{empty}

\else
\ifsimple
\LoadClass[a4paper,11pt]{article}
\else
\LoadClass[a4paper,oneside,11pt]{book}
\RequirePackage{a4wide}
\fi

\RequirePackage{lmodern}

\RequirePackage{slantsc}
\renewcommand\scitdefault{\scsldefault}
\fi

% Generic packages
\RequirePackage{xspace}            % Automatic spacing
\RequirePackage[normalem]{ulem}    % Underlining, striking out
\RequirePackage{ifpdf}             % PDF mode detection
\RequirePackage[utf8]{inputenc}    % Accents, special characters
\RequirePackage[T1]{fontenc}       % French guillemets
\RequirePackage[autolanguage]{numprint}  % Number formatting
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
  \ifdefined\frenchsetup\frenchsetup{og=«,fg=»}\fi
}

% Special characters
\newcommand\textspfixed{\hskip 0.333em \relax}
