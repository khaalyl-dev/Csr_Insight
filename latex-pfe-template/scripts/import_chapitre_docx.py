#!/usr/bin/env python3
"""Import Chapitre.docx → chapters/chapitre-0{1,2,3}-*.tex + figures/chapitre-{01,02,03}/."""
from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

DOCX = Path(__file__).resolve().parent.parent / "Chapitre.docx"
ROOT = DOCX.parent
OUT_MEDIA = ROOT / "figures" / "chapitre-doc"
OUT_CH = ROOT / "chapters"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def q(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def tex_escape(s: str) -> str:
    s = s.replace("\\", "\\textbackslash{}")
    s = s.replace("{", "\\{").replace("}", "\\}")
    s = s.replace("$", "\\$").replace("&", "\\&").replace("%", "\\%")
    s = s.replace("#", "\\#").replace("_", "\\_")
    s = s.replace("^", "\\textasciicircum{}").replace("~", "\\textasciitilde{}")
    return s


def para_style(p):
    for child in p:
        if q(child.tag) != "pPr":
            continue
        for c2 in child:
            if q(c2.tag) == "pStyle":
                return c2.get(f"{{{W_NS}}}val")
    return None


def para_text(p) -> str:
    parts = []
    for node in p.iter():
        if q(node.tag) == "t" and node.text:
            parts.append(node.text)
        if q(node.tag) == "tab":
            parts.append("\t")
    return "".join(parts).strip()


def blip_embeds(p) -> list[str]:
    ids: list[str] = []
    for el in p.iter():
        if q(el.tag) == "blip":
            rid = el.get(f"{{{R_NS}}}embed")
            if rid:
                ids.append(rid)
    return ids


def load_rels(z: zipfile.ZipFile) -> dict[str, str]:
    rels_xml = z.read("word/_rels/document.xml.rels")
    root = ET.fromstring(rels_xml)
    out: dict[str, str] = {}
    for rel in root:
        if rel.tag.split("}")[-1] != "Relationship":
            continue
        rid = rel.get("Id")
        target = rel.get("Target")
        typ = rel.get("Type", "")
        if rid and target and "image" in typ:
            out[rid] = "word/" + target.replace("\\", "/")
    return out


def extract_media(z: zipfile.ZipFile, rels: dict[str, str]) -> None:
    OUT_MEDIA.mkdir(parents=True, exist_ok=True)
    for rid, target in rels.items():
        name = Path(target).name
        dest = OUT_MEDIA / name
        try:
            dest.write_bytes(z.read(target))
        except KeyError:
            pass


def strip_heading_num(text: str, level: int) -> str:
    """Remove Word numbering like 1.2.3 from heading text (LaTeX adds its own)."""
    if level == 2:
        text = re.sub(r"^\d+\.\d+\s+", "", text)
    elif level == 3:
        text = re.sub(r"^\d+\.\d+\.\d+\s+", "", text)
    elif level == 4:
        text = re.sub(r"^\d+\.\d+\.\d+\.\d+\s+", "", text)
    return text.strip()


def chapter_title_from_title_line(line: str) -> str:
    """Titre affiché après « Chapitre n : » ou « Chapitre n Sprint k : »."""
    line = line.strip()
    m = re.match(r"^Chapitre\s+\d+(?:\s+Sprint\s+\d+)?\s*:\s*(.+)$", line, re.I)
    if m:
        return m.group(1).strip()
    if ":" in line:
        return line.split(":", 1)[1].strip()
    return line


def is_toc_row(text: str) -> bool:
    if "\t" not in text:
        return False
    return bool(re.match(r"^\d+\.\d+", text))


def para_to_latex(
    style: str | None,
    text: str,
    embeds: list[str],
    rels: dict[str, str],
    fig_counter: list[int],
    chap_idx: int,
) -> list[str]:
    lines: list[str] = []
    if embeds:
        for rid in embeds:
            path = rels.get(rid)
            if not path:
                continue
            name = Path(path).name
            # Par défaut, ranger les images par chapitre (01/02/03) au lieu d'un dossier unique
            rel = f"figures/chapitre-{chapter_num:02d}/{name}"
            fig_counter[0] += 1
            lab = f"fig:doc-ch{chap_idx + 1}-{fig_counter[0]}"
            cap = ""
            if re.match(r"^Figure\s+", text, re.I):
                cap = tex_escape(text)
                text = ""
            lines.append("\\begin{figure}[H]")
            lines.append("  \\centering")
            lines.append(f"  \\includegraphics[width=0.92\\linewidth]{{{rel}}}")
            if cap:
                lines.append(f"  \\caption{{{cap}}}")
            else:
                lines.append("  \\caption{Illustration (import depuis le document Word).}")
            lines.append(f"  \\label{{{lab}}}")
            lines.append("\\end{figure}")
        if text and not re.match(r"^Figure\s+", text, re.I):
            lines.append(tex_escape(text))
            lines.append("")
        return lines

    if not text:
        return lines

    if style == "Heading2":
        t = strip_heading_num(text, 2)
        lines.append(f"\\section{{{tex_escape(t)}}}")
        lines.append("")
    elif style == "Heading3":
        t = strip_heading_num(text, 3)
        lines.append(f"\\subsection{{{tex_escape(t)}}}")
        lines.append("")
    elif style == "Heading4":
        t = strip_heading_num(text, 4)
        lines.append(f"\\subsubsection{{{tex_escape(t)}}}")
        lines.append("")
    elif style == "Heading1":
        if text:
            lines.append(f"\\section*{{{tex_escape(text)}}}")
            lines.append("\\addcontentsline{toc}{section}{" + tex_escape(text) + "}")
            lines.append("")
    else:
        if is_toc_row(text):
            return lines
        lines.append(tex_escape(text))
        lines.append("")
    return lines


def main() -> None:
    z = zipfile.ZipFile(DOCX)
    rels = load_rels(z)
    extract_media(z, rels)

    doc_root = ET.fromstring(z.read("word/document.xml"))
    paras: list[tuple[str | None, str, list[str]]] = []
    for p in doc_root.iter():
        if q(p.tag) != "p":
            continue
        st = para_style(p)
        txt = para_text(p)
        emb = blip_embeds(p)
        paras.append((st, txt, emb))

    # Commencer au premier style « Title » (ne pas s’arrêter aux Heading du sommaire Word)
    i0 = 0
    for i, (st, txt, _) in enumerate(paras):
        if st == "Title":
            i0 = i
            break

    chunks: list[list[tuple[str | None, str, list[str]]]] = []
    cur: list[tuple[str | None, str, list[str]]] = []
    for (st, txt, emb) in paras[i0:]:
        if st == "Title":
            if cur:
                chunks.append(cur)
            cur = [(st, txt, emb)]
        else:
            cur.append((st, txt, emb))
    if cur:
        chunks.append(cur)

    out_specs = [
        ("chapitre-01-etude-prealable.tex", "chapitre-01"),
        ("chapitre-02-fondation-initiation.tex", "chapitre-02"),
        ("chapitre-03-sprint1-utilisateurs.tex", "chapitre-03"),
    ]

    for idx, chunk in enumerate(chunks):
        if idx >= len(out_specs):
            break
        fname, _slug = out_specs[idx]
        first = chunk[0]
        if first[0] != "Title":
            title = f"Chapitre {idx + 1}"
        else:
            title = chapter_title_from_title_line(first[1])
        body: list[str] = [
            f"% Importé depuis Chapitre.docx (partie {idx + 1})",
            f"\\chapter{{{tex_escape(title)}}}",
            "",
        ]
        figc = [0]
        for st, txt, emb in chunk[1:]:
            body.extend(para_to_latex(st, txt, emb, rels, figc, idx))

        text = "\n".join(body).rstrip() + "\n"
        (OUT_CH / fname).write_text(text, encoding="utf-8")
        print("Wrote", OUT_CH / fname)

    z.close()
    print("Media →", OUT_MEDIA)


if __name__ == "__main__":
    main()
