%-----------------------------------------------------------------------------
%
%               LaTeX Class/Style File
%
% Name:         TU Berlin - Self-Archiving Cover Sheet Template
%
% Purpose:      Cover sheet for  self-archiving of research publications,
%               to be deposited in an open access repository. 
%               The template is provided by the Open Access team at TU Berlin 
%               University Library. It is intended to be used by members of TU Berlin.
%        
% Creator:      Michaela Voigt https://orcid.org/0000-0001-9486-3189
% 
% Source:       This template is based on
%               "Charité - Universitätsmedizin Berlin Repository Cover Sheet Template"
%               created by Thomas Vogel, Steffi Grimm, Elena Gandert (June 2019)
%               and provided by the Charité Medical Library 
%               https://www.overleaf.com/latex/templates/charite-universitatsmedizin-berlin-repository-cover-sheet-template/bypqttrsbjmn
%               Contact openaccess@charite.de
%
% Created:      May 2021
% Updated:      August 2024
%
% Terms of Use: With the exception of the TU Berlin logo, the template can be reused
%               without restrictions. In case of questions, please contact us at
%               openaccess@ub.tu-berlin.de.
% 
%-----------------------------------------------------------------------------


\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{def/tuberlin}

%% Options
% Language: set labels for cover page 
\DeclareOption{english}	 { 
	\def \tuberlin@docTypeHeader{Document type}
	\def \tuberlin@versionAvailableAtHeader{This version is available at}
	\def \tuberlin@citationDetailsHeader{Citation details}
	\def \tuberlin@termsOfUseHeader{Terms of use}
	\def \tuberlin@dateOfVersionHeader{Date of this version}
	\def \tuberlin@OAtuberlin{Open Access via institutional repository of Technische Universität Berlin}
}

\DeclareOption*{\PassOptionsToClass{\CurrentOption}{memoir}}

\ExecuteOptions{english}
\ProcessOptions
\relax

\LoadClass[oldfontcommands, extrafontsizes, a4paper, oneside]{memoir}

%% Packages
\RequirePackage[dvipsnames, svgnames]{xcolor}
\RequirePackage{tikz}
\usetikzlibrary{shapes.geometric, arrows}
\usepackage{svg}
\RequirePackage{xspace}
\RequirePackage{pdfpages}
\RequirePackage{graphicx}
\usepackage[hidelinks,pdfa,pdfusetitle]{hyperref}
\usepackage{hyperxmp}
\RequirePackage{url}
\urlstyle{sf}
\usepackage{ccicons} % use Creative Commons icons
\usepackage[absolute]{textpos} % exact position logo
\usepackage{amsmath} % https://ctan.org/pkg/amsmath for mathematical features

%% Encoding
\RequirePackage[utf8]{inputenc}
\RequirePackage[T1]{fontenc}

%% PDF/A compliance
%Embed color scheme (for PDF/A compliancy)
\immediate\pdfobj stream attr{/N 3} file{def/sRGB_IEC61966-2-1_black_scaled.icc}
\edef\OBJ@RVT{\the\pdflastobj}
\pdfcatalog{%
/OutputIntents [ <<
/Type /OutputIntent
/S/GTS_PDFA1
/DestOutputProfile \OBJ@RVT\space 0 R
/OutputConditionIdentifier (sRGB_IEC61966-2-1_black_scaled)
/Info(sRGB_IEC61966-2-1_black_scaled)
 >> ]}
%Embed fonts (Unicode mapping for Type1 fonts)
\input glyphtounicode.tex
\pdfgentounicode=1
\pdfinclusioncopyfonts=1
% create uncompressed PDF
\pdfobjcompresslevel=0
\pdfcompresslevel =0
% PDF/A version
\hypersetup{pdfapart=2, pdfaconformance=b, pdflang={en}}

%% Fonts and typography
%\RequirePackage{helvet}           
\RequirePackage[scaled=0.95]{helvet} % Helvetica (kerning adjusted)
\renewcommand{\sfdefault}{phv}     % Helvetica, load Arial clone
\RequirePackage[final]{microtype}  % Improved typography


%% TU Berlin colors (cf. Corporate Design Manual)
% \definecolor{tuberlinred}{RGB}{197 14 31} % TU red #C50E1F (not used as of May 2021)
% \definecolor{tuberlindarkgray}{RGB}{91 75 75} % TU gray #5B4B4B for headings
\definecolor{tuberlingrayarea}{RGB}{249 247 247} % TU gray #F9F7F7 for background

%% TU Berlin colors (cf. Corporate Design Manual, as of 2022 -- new in template as of August 2024)
\definecolor{tuberlinred}{RGB}{196 13 30} % TU red #C40D1E (not used as of May 2021, here for possible later use)
\definecolor{tuberlindarkgray}{RGB}{67 67 67} % TU gray #434343 for headings
% \definecolor{tuberlingrayarea}{RGB}{178 178 178} % TU gray #b2b2b2 for background (not used as that's far too dark for our purpose)

%% Layout
\usepackage[a4paper]{geometry} % showframe

% Paper size
% offsets
%\hoffset=-0.34cm
\hoffset=-1in
%\voffset=-0.34cm
\voffset=-1in

% text area
\textwidth=160mm
\textheight=253mm

% header
\topmargin=22mm
\headsep=0mm
\headheight=0mm

% left margin
\oddsidemargin=24mm
\marginparpush=10mm

% right margin
\marginparwidth=0mm
\marginparsep=0mm

% footer
\footskip=0mm

%% Title page
\newcommand{\tuberlintitle}
{
    \begin{titlingpage}
	        
	   % Logo right corner 
       \begin{textblock*}{2mm}(17cm,4cm)
       \includesvg[width=40mm]{def/tu-berlin-logo-long-red.svg}
       \end{textblock*}

            
            %%% gray background (template version 1)
            %\vskip2in
            %\begin{tikzpicture}[remember picture, overlay]         
	     %   \fill [tuberlingrayarea, opacity=1] (-1.0,-3.0) rectangle (16,-25);
	   %     \end{tikzpicture}
	   %     \raggedright
           % \vskip1.5in

            %%% new gray background (new CD 2022, in template since Nov 2025)
            
            \vskip2in
            %\begin{tikzpicture}[remember picture, overlay, every node/.style={trapezium}]         
	       %  \node[trapezium left angle=90, trapezium right angle=180, fill=tuberlingrayarea, opacity=1,  minimum width=15cm] at (0.0,-8.0) {};
        \begin{tikzpicture}[remember picture, overlay] 
        \fill [tuberlingrayarea, opacity=1, rotate=4] (-4.0,-2.5) rectangle (20,-13);


	    \end{tikzpicture}
	        \raggedright
            \vskip1.5in
            
            %%% title elements
              {%
				\fontsize{16}{20}
				\boldmath
				\sffamily
				\theauthor
				\par
            }
             \vskip1.5\onelineskip
             {
				\Large
				\fontsize{20}{24}
				\bfseries
				\boldmath
				\sffamily
				\thetitle
				\par
            }
            \vskip0.5\onelineskip

        	\ifx\tuberlin@subtitle\empty
        		% no subtitle
        	\else
	            \vskip1\onelineskip
		        {
					\fontsize{16}{20}
					\boldmath
					\sffamily
					\tuberlin@subtitle
					\par
		        }
	        \fi
            
           
            \vfill
            {
	            %\fontsize{10}{12}
	            \sffamily
	            %%%%%%%%
	            
	            \textbf{\textcolor{tuberlindarkgray}{\tuberlin@OAtuberlin}}
	            
	            %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%	            
	            \ifx\tuberlin@documentType\empty
		          	% no document type
	            \else
	            \vskip1.5\onelineskip
		            \textbf{\textcolor{tuberlindarkgray}{\tuberlin@docTypeHeader}}\par
		            \tuberlin@documentType \hspace{.5em}
		                \ifx\tuberlin@documentVersion\empty % no document version
		                \else | \hspace{.1em} \tuberlin@documentVersion
	            \fi          	
               	%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
	            
		        \tuberlin@fundingAck % Project info, optional
	            \fi          	
               	%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
                
               	\ifx\tuberlin@dateOfVersion\empty
               		% no date of publication details
               	\else
               	\vskip1.5\onelineskip
               	\textbf{\textcolor{tuberlindarkgray}{\tuberlin@dateOfVersionHeader}}\par
               	\tuberlin@dateOfVersion
               	\fi
                %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
				\ifx\tuberlin@versionAvailableAt\empty
					% no versionAvailableAt
				\else
					\vskip1\onelineskip
					\textbf{\textcolor{tuberlindarkgray}{\tuberlin@versionAvailableAtHeader}} \par
					\tuberlin@versionAvailableAt
				\fi
                %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
               	\ifx\tuberlin@citationDetails\empty
               		% no citation details
               	\else
               		\vskip2\onelineskip
               		\textbf{\textcolor{tuberlindarkgray}{\tuberlin@citationDetailsHeader}}\par
               		\tuberlin@citationDetails
               	\fi
               	%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
               	
               	\vskip1\onelineskip
				\tuberlin@publisherStatement
              	
              	%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
               	\ifx\tuberlin@termsOfUse\empty
               		% no terms of use
               		\vskip1.5\onelineskip
               	\else
               		\vskip2\onelineskip
               	   	\textbf{\textcolor{tuberlindarkgray}{\tuberlin@termsOfUseHeader}}\par
			   		\tuberlin@termsOfUse
			   	\fi	
			   	%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
               	

                \vskip1\onelineskip
            }
    \end{titlingpage}
}


%% User-specified data

\newcommand{\subtitle}[1]{ \def \tuberlin@subtitle{#1} }
\subtitle{}

\newcommand{\documentType}[1]{ \def \tuberlin@documentType{#1} }
\documentType{}

\newcommand{\fundingAck}[1]{ \def \tuberlin@fundingAck{#1} }
\fundingAck{}

\newcommand{\documentVersion}[1]{ \def \tuberlin@documentVersion{#1} }
\documentVersion{}

\newcommand{\dateOfVersion}[1]{ \def \tuberlin@dateOfVersion{#1} }
\dateOfVersion{}

\newcommand{\versionAvailableAt}[1]{ \def \tuberlin@versionAvailableAt{#1} }
\newcommand{\versionAvailableAtDOI}[1]{\versionAvailableAt{\DOIURL{#1}}}
\newcommand{\versionAvailableAtURN}[1]{\versionAvailableAt{\URNURL{#1}}}
\versionAvailableAt{}

\newcommand{\citationDetails}[1]{ \def \tuberlin@citationDetails{#1} }
\citationDetails{}

\newcommand{\termsOfUse}[1]{ \def \tuberlin@termsOfUse{#1} }
\termsOfUse{}

\newcommand{\publisherStatement}[1]{ \def \tuberlin@publisherStatement{#1} }
\publisherStatement{}

%%%%%%%%%%%%%%

%% DOIs, URNs, etc.

%\RequirePackage{doi} % Ignores syntax of latex in DOI links
%\renewcommand{\doitext}{DOI:\space}

\makeatletter

\providecommand{\DOI}[1]{%
	\begingroup
	\let\bibinfo\@secondoftwo
	\urlstyle{sf}%
	\href{https://doi.org/#1}{%
		DOI:~\nolinkurl{#1}%
	}%
	\endgroup
}

\providecommand{\URL}[1]{%
	\begingroup
	\urlstyle{sf}%
	\href{#1}{%
		\nolinkurl{#1}%
	}%
	\endgroup
}

\providecommand{\DOIURL}[1]{%
	\URL{https://doi.org/#1}
}

\providecommand{\URNURL}[1]{%
	\URL{http://nbn-resolving.de/#1}
}
\makeatother


%%%%%%%%%%%%%%
% Versions
% submitted
\newcommand{\submitted}{Submitted manuscript \newline (version that has been submitted for publication; not yet peer-reviewed)}
% accepted
\newcommand{\accepted}{Accepted manuscript \newline (final author-created version; includes changes from peer review; accepted for publication)}
% published
\newcommand{\published}{Published version \newline (Version of Record; peer-reviewed, formally published; copyedited, layouted and/or typeset by the publisher)}


%%%%%%%%%%%%%%
% Licenses
\newcommand{\InCopyright}{This work is protected by copyright and/or related rights. You are free to use this work in any way permitted by the copyright and related rights legislation that applies to your usage. For other uses, you must obtain permission from the rights-holder(s).}
\newcommand{\CCBYlic}{\ccby\ This work is licensed under a Creative Commons Attribution 4.0 International license: \URL{https://creativecommons.org/licenses/by/4.0/}}
\newcommand{\CCBYSAlic}{\ccbysa\ This work is licensed under a Creative Commons Attribution-ShareAlike 4.0 International license: \URL{https://creativecommons.org/licenses/by-sa/4.0/}}
\newcommand{\CCBYNDlic}{\ccbynd\ This work is licensed under a Creative Commons Attribution-NoDerivatives 4.0 International license: \URL{https://creativecommons.org/licenses/by-nd/4.0/}}
\newcommand{\CCBYNClic}{\ccbynceu\ This work is licensed under a Creative Commons Attribution-NonCommercial 4.0 International license: \URL{https://creativecommons.org/licenses/by-nc/4.0/}}
\newcommand{\CCBYNCSAlic}{\ccbyncsaeu\ This work is licensed under a Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International license: \URL{https://creativecommons.org/licenses/by-nc-sa/4.0/}}
\newcommand{\CCBYNCNDlic}{\ccbyncndeu\ This work is licensed under a Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International license: \URL{https://creativecommons.org/licenses/by-nc-nd/4.0/}}

%%%%%%%%%%%%%%

\endinput