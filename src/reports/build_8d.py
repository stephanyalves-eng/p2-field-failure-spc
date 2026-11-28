"""Build the 8D deliverables: the Ishikawa figure and reports/8D.pdf from reports/8D.md.

Usage:
    python -m src.reports.build_8d

The Markdown file is the source of truth. The PDF renderer supports only what 8D.md uses:
headings (#, ##, ###), paragraphs, bullet and numbered lists, tables, images, **bold** and
[text](url) links.
"""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from reportlab import rl_config  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    Image,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.plots import (  # noqa: E402
    CONTEXT,
    MONO,
    SERIES_1,
    TEXT,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
    _finish,
)

SAGE_100 = "#E4ECE7"  # --surface-accent, table headers
BORDER = "#D6D8D2"  # --border-default
FOREST_900 = "#0B302B"  # --surface-inverse
IVORY = "#F5F4EC"  # --text-inverse

# Fixed timestamps and document id, so rebuilding the PDF from the same source gives the same bytes.
rl_config.invariant = 1

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"

# Ishikawa content mirrors the D4 table in 8D.md. (H) marks a hypothesis.
ISHIKAWA = {
    "Material": ["Look-alike coax terminals (H)", "Either terminal fits either cavity (H)"],
    "Method": ["Insertion relies on operator choice (H)", "No error-proofing step (H)"],
    "Man": ["Terminals inserted into each\nother's cavities (H)"],
    "Machine": ["End-of-line test checks continuity,\nnot cavity position (H)"],
    "Measurement": [
        "Some swapped cars passed\nfield calibration (F, S3)",
        "Detection assumed, not verified (H)",
    ],
    "Environment": ["No supported candidate"],
}
EFFECT = "Fisheye and narrow\ncamera feeds swapped\n(F, S1)"


def ishikawa_figure(path: Path) -> Path:
    """Fishbone diagram: three bones above and three below the spine, effect in an inverse
    (Deep Forest) module, category names as mono eyebrows, square data nodes at the joints."""
    fig, ax = plt.subplots(figsize=(12, 6.9))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 6)
    ax.axis("off")
    ax.plot([0.4, 9.55], [3, 3], color=TEXT, lw=1.5)
    ax.text(
        9.7,
        3,
        EFFECT,
        va="center",
        ha="left",
        fontsize=10,
        fontweight="medium",
        color=IVORY,
        linespacing=1.4,
        bbox={"boxstyle": "square,pad=0.6", "fc": FOREST_900, "ec": FOREST_900, "lw": 0},
    )
    top = ["Material", "Method", "Man"]
    bottom = ["Machine", "Measurement", "Environment"]
    xs = [2.2, 5.0, 7.8]
    for row, sign in ((top, 1), (bottom, -1)):
        for x, name in zip(xs, row, strict=True):
            end_y = 3 + sign * 2.3
            ax.plot([x - 1.0, x], [end_y, 3], color=SERIES_1, lw=1.5)
            ax.plot(x, 3, marker="s", ms=6, color=SERIES_1)
            ax.text(
                x - 1.0,
                end_y + sign * 0.25,
                name.upper(),
                ha="center",
                va="center",
                fontsize=8.5,
                fontfamily=MONO,
                fontweight="medium",
                color=TEXT_TERTIARY,
            )
            for i, cause in enumerate(ISHIKAWA[name]):
                frac = 0.35 + 0.4 * i
                cx = x - 1.0 * (1 - frac)
                cy = 3 + sign * 2.3 * (1 - frac)
                ax.plot([cx - 0.25, cx], [cy, cy], color=CONTEXT, lw=1)
                fact = "(F" in cause
                ax.text(
                    cx - 0.3,
                    cy,
                    cause,
                    ha="right",
                    va="center",
                    fontsize=7.8,
                    color=TEXT if fact else TEXT_SECONDARY,
                )
    return _finish(
        fig,
        "Ishikawa (6M): recall 22V-317, swapped camera terminals",
        path,
        eyebrow="8D · Root cause",
        source="NHTSA recall 22V-317 documents; (F) published fact, (H) hypothesis",
    )


def _inline(text: str) -> str:
    """Escape XML and convert **bold** and [text](url) to reportlab markup."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<link href="\2" color="#2F6B5B">\1</link>', text
    )
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)  # relative links: keep the text
    text = re.sub(
        r"(?<![\"'>])(https?://[^\s|)<]+)", r'<link href="\1" color="#2F6B5B">\1</link>', text
    )
    return text


def markdown_to_flowables(md: str, base: Path) -> list:
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9.5, leading=12.5)
    cell = ParagraphStyle("cell", parent=body, fontSize=8, leading=10)
    heads = {1: styles["Title"], 2: styles["Heading2"], 3: styles["Heading3"]}
    flow: list = []
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if m := re.match(r"^(#{1,3}) (.*)", line):
            flow.append(Paragraph(_inline(m.group(2)), heads[len(m.group(1))]))
            i += 1
        elif m := re.match(r"^!\[[^\]]*\]\(([^)]+)\)", line):
            img = Image(str(base / m.group(1)))
            scale = (A4[0] - 4 * cm) / img.drawWidth
            img.drawWidth *= scale
            img.drawHeight *= scale
            flow += [img, Spacer(1, 6)]
            i += 1
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                    rows.append([Paragraph(_inline(c), cell) for c in cells])
                i += 1
            width = A4[0] - 4 * cm
            # Column width proportional to the longest text in each column, at least 12%.
            lengths = [max(len(r[k].text) for r in rows) for k in range(len(rows[0]))]
            shares = [max(n / sum(lengths), 0.12) for n in lengths]
            col = [width * x / sum(shares) for x in shares]
            table = Table(rows, colWidths=col, repeatRows=1)
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(SAGE_100)),
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor(BORDER)),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )
            flow += [table, Spacer(1, 8)]
        elif re.match(r"^(- |\d+\. )", line):
            numbered = bool(re.match(r"^\d+\. ", line))
            items = []
            while i < len(lines) and re.match(r"^(- |\d+\. )", lines[i]):
                text = re.sub(r"^(- |\d+\. )", "", lines[i])
                items.append(ListItem(Paragraph(_inline(text), body)))
                i += 1
            flow += [
                ListFlowable(
                    items,
                    bulletType="1" if numbered else "bullet",
                    start=None if not numbered else 1,
                    leftIndent=12,
                ),
                Spacer(1, 4),
            ]
        else:
            para = [line]
            i += 1
            while (
                i < len(lines)
                and lines[i].strip()
                and not re.match(r"^(#|\||- |\d+\. |!\[)", lines[i])
            ):
                para.append(lines[i])
                i += 1
            flow += [Paragraph(_inline(" ".join(para)), body), Spacer(1, 4)]
    return flow


def build_pdf(md_path: Path, pdf_path: Path) -> Path:
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title="8D report: recall 22V-317",
    )
    doc.build(markdown_to_flowables(md_path.read_text(encoding="utf-8"), md_path.parent))
    return pdf_path


def main() -> None:
    ishikawa_figure(REPORTS / "figures" / "8d_ishikawa.png")
    build_pdf(REPORTS / "8D.md", REPORTS / "8D.pdf")
    print("wrote reports/figures/8d_ishikawa.png and reports/8D.pdf")


if __name__ == "__main__":
    main()
