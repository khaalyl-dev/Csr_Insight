#!/usr/bin/env python3
"""Emit longtable LaTeX for product backlog (variable 3/5-line rows from Word)."""
import re
from pathlib import Path


def tex_escape(s: str) -> str:
    """Contenu déjà partiellement LaTeX (\\&, etc.) : n’échapper que le nécessaire."""
    s = re.sub(r"(?<!\\)&", r"\\&", s)
    s = re.sub(r"(?<!\\)%", r"\\%", s)
    s = re.sub(r"(?<!\\)_", r"\\_", s)
    s = re.sub(r"(?<!\\)\$", r"\\$", s)
    s = re.sub(r"(?<!\\)#", r"\\#", s)
    return s


def main():
    p = Path(__file__).resolve().parent.parent / "chapters" / "chapitre-02-fondation-initiation.tex"
    lines = p.read_text(encoding="utf-8").splitlines()
    start = None
    for i, ln in enumerate(lines):
        if ln.strip() == "Priorité":
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and re.fullmatch(r"\d+", lines[j].strip() or ""):
                start = j
                break
    if start is None:
        raise SystemExit("start not found")
    stop = None
    for k in range(start, len(lines)):
        if lines[k].startswith("\\subsection{"):
            stop = k
            break
    if stop is None:
        raise SystemExit("stop not found")

    toks = []
    for k in range(start, stop):
        s = lines[k].strip()
        if s:
            toks.append(s)

    rows_out = []
    i = 0
    while i < len(toks):
        if re.fullmatch(r"\d+", toks[i]) and i + 1 < len(toks) and not re.match(r"\d+\.\d+", toks[i + 1]):
            epic_id = toks[i]
            epic_name = toks[i + 1]
            i += 2
            while i < len(toks) and re.match(r"\d+\.\d+", toks[i]):
                us_id = toks[i]
                story = toks[i + 1]
                prio = toks[i + 2]
                rows_out.append((epic_id, epic_name, us_id, story, prio))
                i += 3
            continue
        i += 1

    out = [
        "% --- Product backlog (rebuilt from Word export) ---",
        "\\begin{longtable}{@{}p{0.7cm}p{3.0cm}p{1.1cm}p{8.0cm}p{1.3cm}@{}}",
        "\\caption{Product backlog du projet}\\label{tab:product-backlog}\\\\",
        "\\toprule",
        "\\textbf{ID} & \\textbf{Fonctionnalité} & \\textbf{US} & \\textbf{User story} & \\textbf{Priorité} \\\\",
        "\\midrule",
        "\\endfirsthead",
        "\\multicolumn{5}{c}{\\tablename\\ \\thetable{} — \\textit{(suite)}} \\\\",
        "\\toprule",
        "\\textbf{ID} & \\textbf{Fonctionnalité} & \\textbf{US} & \\textbf{User story} & \\textbf{Priorité} \\\\",
        "\\midrule",
        "\\endhead",
        "\\midrule",
        "\\multicolumn{5}{r}{\\textit{Suite page suivante\\ldots}} \\\\",
        "\\endfoot",
        "\\bottomrule",
        "\\endlastfoot",
    ]
    for r in rows_out:
        out.append(" & ".join(tex_escape(c) for c in r) + " \\\\")
    out.append("\\end{longtable}")

    dest = Path(__file__).resolve().parent.parent / "tables" / "chapitre-02-product-backlog.tex"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("Wrote", dest, "rows", len(rows_out))


if __name__ == "__main__":
    main()
