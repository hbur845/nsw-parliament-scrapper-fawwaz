"""URL helpers for extracting identifiers from Hansard links.

Functions here focus on parsing `pdfid` and `docid` from the NSW Parliament
Hansard application URLs.
"""

from typing import Tuple


def parse_ids_from_url(url: str) -> Tuple[str, str]:
    """Parse `pdfid` and `docid` from a Hansard URL.

    Accepts both of these forms:
    - Full: https://...#/DateDisplay/<pdfid>/<docid>
    - Pdf-only: https://...#/DateDisplay/<pdfid>

    Returns a tuple of `(pdfid, docid)`. If no `docid` is present, returns an
    empty string for the second element.
    """
    marker = "#/DateDisplay/"
    if marker in url:
        tail = url.split(marker, 1)[1]
        parts = [p for p in tail.split("/") if p]
        if len(parts) >= 2:
            return parts[0], parts[1]
        if len(parts) == 1:
            # Only pdfid present after DateDisplay
            return parts[0], ""

    # Fallback: try to find a segment that looks like a pdfid
    # Example segment pattern: HANSARD-1323879322-159901
    segments = [p for p in url.split("/") if p]
    for seg in reversed(segments):
        if seg.startswith("HANSARD-"):
            return seg, ""

    raise ValueError("Unable to extract pdfid from URL")
