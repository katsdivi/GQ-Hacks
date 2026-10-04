"""Build and check the StaleLine note.

Steps: regenerate derived inputs (make_tables.py), compile main.tex with tectonic, then check:
  - every \\val{key} used in main.tex (and generated tables) is defined in numbers.tex / extra.tex / phantom.tex
  - no em dash, en dash or "--" in main.tex                                   (FAIL)
  - "Polymarket" only as "polymarket.com" or "Polymarket US"                   (FAIL)
  - page of \\label{endofbody} from main.aux <= 5                               (FAIL)
  - SURNAME / CHECK TITLE placeholders                                         (WARN)
  - LaTeX overfull boxes / missing figures from the log                        (REPORT)
  - digits typed in main.tex outside \\val, \\ref, \\label, preamble            (REPORT)
Also writes numbers_sheet.md (one row per key used). Exit code 1 on any FAIL.

Usage: python3 check_note.py [--no-compile]
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TECTONIC = "/opt/homebrew/bin/tectonic"  # override with env NOTE_TEX=pdflatex
MAX_BODY_PAGES = 5
KEY_FILES = ("numbers.tex", "extra.tex", "phantom.tex", "fmt.tex", "v4_numbers.tex")
DEF_RE = re.compile(r"\\defval\{([^}]*)\}\{(.*)\}\s*(?:%\s*(.*))?$")


def defined_keys() -> dict[str, tuple[str, str, str]]:
    keys: dict[str, tuple[str, str, str]] = {}
    for fn in KEY_FILES:
        for line in (HERE / fn).read_text().splitlines():
            m = DEF_RE.match(line.strip())
            if m:
                keys[m.group(1)] = (m.group(2), fn, (m.group(3) or "").strip())
    return keys


def used_keys(text: str) -> list[str]:
    out: list[str] = []
    for m in re.finditer(r"\\val\{([^}]*)\}", text):
        if m.group(1) not in out and m.group(1) != "#1" and m.group(1) != "#2":
            out.append(m.group(1))
    for m in re.finditer(r"\\ci\{([^}]*)\}\{([^}]*)\}", text):
        for g in m.groups():
            if g not in out and not g.startswith("#"):
                out.append(g)
    return out


def body(text: str) -> str:
    return text.split(r"\begin{document}", 1)[1]


def main() -> int:
    fails, warns = [], []
    subprocess.run([sys.executable, str(HERE / "make_tables.py")], check=True)
    subprocess.run([sys.executable, str(HERE / "make_fmt.py")], check=True)
    if "--no-compile" not in sys.argv:
        if os.environ.get("NOTE_TEX") == "pdflatex":
            for _ in range(3):
                r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "main.tex"], cwd=HERE,
                                   capture_output=True, text=True)
            for _ in range(2):
                subprocess.run(["pdflatex", "-interaction=nonstopmode", "appendix.tex"], cwd=HERE,
                               capture_output=True, text=True)
        else:
            subprocess.run([TECTONIC, "appendix.tex"], cwd=HERE, capture_output=True, text=True)
            r = subprocess.run([TECTONIC, "--keep-intermediates", "--keep-logs", "main.tex"], cwd=HERE,
                               capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stdout[-3000:], r.stderr[-3000:])
            fails.append("tectonic compile failed")
    tex = (HERE / "main.tex").read_text()
    keys = defined_keys()
    used = used_keys(tex)
    app = HERE / "appendix.tex"
    if app.exists():
        for k_ in used_keys(app.read_text()):
            if k_ not in used:
                used.append(k_)
    missing = [k for k in used if k not in keys]
    print(f"keys used in main.tex: {len(used)}; missing: {len(missing)}")
    for k in missing:
        print(f"  MISSING {k}")
    if missing:
        fails.append(f"{len(missing)} missing keys")

    for i, line in enumerate(tex.splitlines(), 1):
        if "\u2014" in line or "\u2013" in line or "--" in line:
            fails.append(f"dash on main.tex line {i}")
        prose = re.sub(r"\\(val|ci)\{[^}]*\}(\{[^}]*\})?", "", line)
        for m in re.finditer(r"polymarket", prose, re.I):
            rest = prose[m.end():]
            if not (rest.startswith(".com") or rest.startswith(" US") or rest.startswith("~US")):
                fails.append(f"bare Polymarket on main.tex line {i}: ...{prose[max(0, m.start() - 20):m.end() + 20]}...")
        for ph in ("SURNAME", "CHECK TITLE"):
            if ph in line:
                warns.append(f"placeholder {ph} on main.tex line {i}")

    if "RESULTS COMMITTED" in (HERE / "extra.tex").read_text():
        fails.append("a post-hoc search branch now has results: update the note text before submitting")

    aux = HERE / "main.aux"
    page = None
    if aux.exists():
        m = re.search(r"\\newlabel\{endofbody\}\{\{[^}]*\}\{(\d+)\}", aux.read_text())
        page = int(m.group(1)) if m else None
    print(f"body ends on page: {page}")
    if page is None:
        fails.append("endofbody label not found in main.aux")
    elif page > MAX_BODY_PAGES:
        fails.append(f"body is {page} pages (> {MAX_BODY_PAGES})")
    pdf = HERE / "main.pdf"
    if pdf.exists():
        try:
            from pypdf import PdfReader
            n = len(PdfReader(str(pdf)).pages)
        except Exception:
            m2 = re.search(rb"/Type\s*/Pages[^>]*?/Count\s+(\d+)", pdf.read_bytes())
            n = int(m2.group(1)) if m2 else None
        print(f"main.pdf total pages: {n}")
        if n is not None and n > MAX_BODY_PAGES:
            fails.append(f"main.pdf has {n} pages in total (> {MAX_BODY_PAGES})")

    log = HERE / "main.log"
    if log.exists():
        lt = log.read_text(errors="replace")
        over = re.findall(r"Overfull \\hbox \(([\d.]+)pt too wide\)[^\n]*lines? (\d+)", lt)
        print(f"overfull hboxes: {len(over)}" + (": " + ", ".join(f"{w}pt at line {l}" for w, l in over) if over else ""))
        miss_fig = re.findall(r"File `([^']+)' not found", lt)
        print(f"missing figures: {miss_fig or 'none'}")
        if miss_fig:
            fails.append("missing figures")

    # digits typed in the document body outside commands that take keys or labels
    b = body(tex)
    b = re.sub(r"\\(val|ref|label|input|includegraphics|ci)(\[[^]]*\])?\{[^}]*\}(\{[^}]*\})?", "", b)
    b = re.sub(r"%.*", "", b)
    digit_lines = [l.strip() for l in b.splitlines() if re.search(r"\d", l)]
    print(f"lines with typed digits in body: {len(digit_lines)}")
    for l in digit_lines:
        for m in re.finditer(r"[^\s]*\d[^\s]*", l):
            print(f"  typed: {m.group(0)}")

    # numbers sheet
    num_json = {}
    rows = ["# Numbers sheet (note/main.tex)", "",
            "Generated by check_note.py. One row per key used in main.tex. Source column = the key file's comment "
            "(file and column/field). Check each row against its source and initial it.", "",
            "| key | value | key file | source (file: column/row) | checked by |", "|---|---|---|---|---|"]
    for k in used:
        v, fn, src = keys.get(k, ("MISSING", "", ""))
        v = v.replace("|", "\\|")
        rows.append(f"| `{k}` | {v} | {fn} | {src} | |")
    (HERE / "numbers_sheet.md").write_text("\n".join(rows) + "\n")
    print(f"numbers_sheet.md: {len(used)} rows")

    for w in warns:
        print("WARN", w)
    for f_ in fails:
        print("FAIL", f_)
    print("RESULT:", "FAIL" if fails else "PASS")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
