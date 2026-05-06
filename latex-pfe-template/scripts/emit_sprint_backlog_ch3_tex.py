#!/usr/bin/env python3
"""Emit longtable for Sprint backlog (chapitre-03) — blocs ID + User story + (Tâche, desc, prio)*."""
import re
from pathlib import Path


def tex_escape(s: str) -> str:
    s = re.sub(r"(?<!\\)&", r"\\&", s)
    s = re.sub(r"(?<!\\)%", r"\\%", s)
    s = re.sub(r"(?<!\\)_", r"\\_", s)
    s = re.sub(r"(?<!\\)\$", r"\\$", s)
    s = re.sub(r"(?<!\\)#", r"\\#", s)
    return s


def main():
    p = Path(__file__).resolve().parent.parent / "chapters" / "chapitre-03-sprint1-utilisateurs.tex"
    lines = p.read_text(encoding="utf-8").splitlines()
    start = None
    for i, ln in enumerate(lines):
        if ln.strip() == "Priorité" and i + 1 < len(lines):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and lines[j].strip() == "1":
                start = j
                break
    stop = None
    for k in range(start or 0, len(lines)):
        if lines[k].startswith("\\section{Analyse"):
            stop = k
            break
    if start is None or stop is None:
        raise SystemExit("slice not found")
    toks = [lines[k].strip() for k in range(start, stop) if lines[k].strip()]

    rows_out = []
    i = 0
    while i < len(toks):
        if re.fullmatch(r"\d+", toks[i]) and i + 1 < len(toks):
            eid = toks[i]
            story = toks[i + 1]
            i += 2
            while i < len(toks) and re.match(r"^\d+\.\d+$", toks[i]):
                tid = toks[i]
                tdesc = toks[i + 1]
                prio = toks[i + 2]
                rows_out.append((eid, story, tid, tdesc, prio))
                i += 3
            continue
        i += 1

    out = [
        "% --- Sprint backlog — Authentification & Fondations ---",
        "\\begin{longtable}{@{}p{0.6cm}p{4.0cm}p{1.0cm}p{7.8cm}p{1.4cm}@{}}",
        "\\caption{Sprint backlog — Authentification \\& Fondations}\\label{tab:sprint-backlog-1}\\\\",
        "\\toprule",
        "\\textbf{ID} & \\textbf{User story} & \\textbf{Tâche} & \\textbf{Tâche (détail)} & \\textbf{Priorité} \\\\",
        "\\midrule",
        "\\endfirsthead",
        "\\multicolumn{5}{c}{\\tablename\\ \\thetable{} — \\textit{(suite)}} \\\\",
        "\\toprule",
        "\\textbf{ID} & \\textbf{User story} & \\textbf{Tâche} & \\textbf{Tâche (détail)} & \\textbf{Priorité} \\\\",
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

    dest = Path(__file__).resolve().parent.parent / "tables" / "chapitre-03-sprint-backlog.tex"
    dest.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("Wrote", dest, "rows", len(rows_out))


if __name__ == "__main__":
    main()
