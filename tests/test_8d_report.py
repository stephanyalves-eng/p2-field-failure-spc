"""Honesty checks for reports/8D.md: every D-step statement is tagged, every source is linked."""

import re
from pathlib import Path

from src.reports.build_8d import _inline

REPORT = Path(__file__).resolve().parents[1] / "reports" / "8D.md"
TAG = re.compile(r"\[(F|H|A)\b[^\]]*\]")


def _d_step_lines() -> list[str]:
    lines = REPORT.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("## D1"))
    body = lines[start:]
    keep = []
    for i, line in enumerate(body):
        if not line.strip() or line.startswith("#") or line.startswith("!["):
            continue
        if re.fullmatch(r"\|(\s*:?-+:?\s*\|)+", line.strip()):
            continue  # table separator
        nxt = body[i + 1] if i + 1 < len(body) else ""
        if line.startswith("|") and re.fullmatch(r"\|(\s*:?-+:?\s*\|)+", nxt.strip()):
            continue  # table header
        keep.append(line)
    return keep


def test_every_d_step_statement_has_a_tag():
    untagged = [line for line in _d_step_lines() if not TAG.search(line)]
    assert untagged == []


def test_every_cited_source_is_defined_with_an_nhtsa_link():
    text = REPORT.read_text(encoding="utf-8")
    defined = dict(re.findall(r"^\| (S\d) \|.*\| (https://static\.nhtsa\.gov/\S+) \|$", text, re.M))
    fact_tags = " ".join(re.findall(r"\[F[^\]]*\]", text))
    cited = set(re.findall(r"\bS\d\b", fact_tags))
    assert cited, "no fact tags found"
    assert cited <= set(defined)


def test_inline_markup_escapes_and_links():
    out = _inline("a < b & **bold** [doc](https://x.org/a.pdf)")
    assert "&lt;" in out and "&amp;" in out
    assert "<b>bold</b>" in out
    assert '<link href="https://x.org/a.pdf" color="blue">doc</link>' in out
