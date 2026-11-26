"""
Export the report drafts in docs/ as PDF files into docs/pdf/.

Rule: whenever a draft in docs/ is written or changed, its PDF is
exported again, so that the group always reads the current version.

For a draft that marks its text with two lines of "---", only the text between
them is exported (the section itself, without the working notes around it).
The Markdown is turned into HTML (mistune) and printed by headless Chrome.
The layout is a plain A4 page; it approximates the length in the chair's
template but does not replace it.

Reads:  docs/proposal.md, docs/proposal_draft.md, docs/report_*.md, docs/group_decision_sheet.md
Writes: docs/pdf/<same name>.pdf

Usage: python tools/export_pdf.py                 # all drafts
       python tools/export_pdf.py docs/report_data_section.md
"""
from datetime import date
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import mistune

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
PDF_DIR = DOCS / "pdf"
DRAFTS = ["proposal.md", "proposal_draft.md", "report_*.md", "group_decision_sheet.md"]
CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]
CSS = """
@page { size: A4; margin: 2.5cm; }
body { font-family: "Times New Roman", Times, serif; font-size: 11pt; line-height: 1.35; color: #000; }
h1 { font-size: 16pt; } h2 { font-size: 14pt; margin-top: 1.2em; } h3 { font-size: 12pt; margin-top: 1em; }
h1, h2, h3 { break-after: avoid; }
p, li { text-align: justify; } p { margin: 0.5em 0; }
table { border-collapse: collapse; width: 100%; font-size: 9pt; margin: 0.6em 0; break-inside: avoid; }
th, td { border-top: 0.5pt solid #777; border-bottom: 0.5pt solid #777; padding: 2pt 5pt; text-align: left; vertical-align: top; }
th { border-top: 1pt solid #000; border-bottom: 1pt solid #000; }
img { max-width: 78%; display: block; margin: 0.4em auto; break-inside: avoid; }
code { font-family: Menlo, monospace; font-size: 8.5pt; }
.note { font-size: 8.5pt; color: #555; border-bottom: 0.5pt solid #999; padding-bottom: 3pt; margin-bottom: 1em; }
"""


def section_text(markdown: str) -> str:
    """The text between the first two '---' lines, or the whole file if there are none."""
    parts = re.split(r"^---\s*$", markdown, flags=re.MULTILINE)
    return parts[1] if len(parts) >= 3 else markdown


def find_chrome() -> str:
    for candidate in CHROME_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    raise FileNotFoundError("No Chrome, Chromium or Edge found; add its path to CHROME_CANDIDATES.")


def page_count(pdf: Path) -> int:
    return len(re.findall(rb"/Type\s*/Page[^s]", pdf.read_bytes()))


def export(source: Path) -> Path:
    body = mistune.create_markdown(plugins=["table", "strikethrough"])(section_text(source.read_text(encoding="utf-8")))
    note = f"Draft, exported {date.today().isoformat()} from {source.relative_to(ROOT)}. Plain layout, not the chair's template."
    html = (f'<!doctype html><html><head><meta charset="utf-8"><base href="{DOCS.as_uri()}/">'
            f"<style>{CSS}</style></head><body><div class=\"note\">{note}</div>{body}</body></html>")
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    target = PDF_DIR / (source.stem + ".pdf")
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "draft.html"
        page.write_text(html, encoding="utf-8")
        subprocess.run([find_chrome(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        "--allow-file-access-from-files", f"--user-data-dir={tmp}/profile",
                        f"--print-to-pdf={target}", page.as_uri()],
                       check=True, capture_output=True, timeout=120)
    return target


def main() -> None:
    sources = [Path(a).resolve() for a in sys.argv[1:]] or sorted(f for pattern in DRAFTS for f in DOCS.glob(pattern))
    for source in sources:
        target = export(source)
        print(f"{target.relative_to(ROOT)}: {page_count(target)} pages")


if __name__ == "__main__":
    main()
