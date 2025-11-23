"""Parsing engines for Hansard fragments.

Supported engines:
- "bs4": BeautifulSoup with built-in html.parser
- "bs4-lxml": BeautifulSoup with lxml parser
- "lxml": native lxml.html (no BeautifulSoup)

Provides a single entry point `parse_fragment(html, engine)` that returns the
normalized structure used by storage writers.
"""

from __future__ import annotations

from typing import Any, Dict

from bs4 import BeautifulSoup
from lxml import html as lxml_html


def _parse_with_bs4(html: str, parser: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, parser)

    def text_or_none(el):
        return el.get_text(strip=True) if el else None

    title = text_or_none(soup.find("p", class_="SubDebate-H"))
    subtitle = text_or_none(soup.find("p", class_="SubSubDebate-H"))

    blocks: list[dict[str, Any]] = []
    for p in soup.find_all("p"):
        cls = " ".join(p.get("class", []))
        speaker_el = (
            p.find(class_="MemberSpeech-H")
            or p.find(class_="MemberUpper-H")
            or p.find(class_="OfficeUpper-H")
        )
        time_el = p.find(class_="Time-H")
        if speaker_el:
            blocks.append(
                {
                    "type": "speech",
                    "speaker": text_or_none(speaker_el),
                    "time": text_or_none(time_el),
                    "text": p.get_text(" ", strip=True),
                }
            )
            continue

        if "Normal-P" in cls or "NormalItalics-P" in cls or "NormalBold-P" in cls:
            style = (
                "NormalItalics"
                if "NormalItalics-P" in cls
                else "NormalBold"
                if "NormalBold-P" in cls
                else "Normal"
            )
            blocks.append({"type": "paragraph", "style": style, "text": p.get_text(" ", strip=True)})

    return {"title": title, "subtitle": subtitle, "blocks": blocks}


def _parse_with_lxml_native(html: str) -> Dict[str, Any]:
    tree = lxml_html.fromstring(html)

    def has_class(el, name: str) -> bool:
        cls = el.get("class") or ""
        token = f" {name} "
        return token in (" " + " ".join(cls.split()) + " ")

    def text_content(el) -> str:
        return " ".join(el.itertext()).strip()

    # Title and subtitle
    title_el = tree.xpath('//p[contains(concat(" ", normalize-space(@class), " "), " SubDebate-H ")][1]')
    subtitle_el = tree.xpath('//p[contains(concat(" ", normalize-space(@class), " "), " SubSubDebate-H ")][1]')
    title = text_content(title_el[0]) if title_el else None
    subtitle = text_content(subtitle_el[0]) if subtitle_el else None

    blocks: list[dict[str, Any]] = []
    for p in tree.xpath("//p"):
        # Detect speaker/time
        speaker_nodes = p.xpath(
            ".//*[contains(concat(' ', normalize-space(@class), ' '), ' MemberSpeech-H ') or "
            "contains(concat(' ', normalize-space(@class), ' '), ' MemberUpper-H ') or "
            "contains(concat(' ', normalize-space(@class), ' '), ' OfficeUpper-H ')]"
        )
        time_nodes = p.xpath(".//*[contains(concat(' ', normalize-space(@class), ' '), ' Time-H ')]")
        if speaker_nodes:
            blocks.append(
                {
                    "type": "speech",
                    "speaker": text_content(speaker_nodes[0]),
                    "time": text_content(time_nodes[0]) if time_nodes else None,
                    "text": text_content(p),
                }
            )
            continue

        # Paragraph styles
        if has_class(p, "Normal-P") or has_class(p, "NormalItalics-P") or has_class(p, "NormalBold-P"):
            style = "Normal"
            if has_class(p, "NormalItalics-P"):
                style = "NormalItalics"
            elif has_class(p, "NormalBold-P"):
                style = "NormalBold"
            blocks.append({"type": "paragraph", "style": style, "text": text_content(p)})

    return {"title": title, "subtitle": subtitle, "blocks": blocks}


def parse_fragment(html: str, engine: str = "lxml") -> Dict[str, Any]:
    """Parse a fragment HTML string using the selected engine.

    - engine = "bs4": BeautifulSoup with html.parser
    - engine = "bs4-lxml": BeautifulSoup with lxml parser
    - engine = "lxml": native lxml.html
    """
    eng = engine.lower()
    if eng == "bs4":
        return _parse_with_bs4(html, "html.parser")
    if eng == "bs4-lxml":
        return _parse_with_bs4(html, "lxml")
    if eng == "lxml":
        return _parse_with_lxml_native(html)
    # Fallback to lxml
    return _parse_with_lxml_native(html)

