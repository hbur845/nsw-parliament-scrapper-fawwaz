"""URL helpers for extracting identifiers from Hansard links.

Functions here focus on parsing `pdfid` and `docid` from the NSW Parliament
Hansard application URLs.
"""

from typing import Tuple


def parse_ids_from_url(url: str) -> Tuple[str, str]:
    """Parse `pdfid` and `docid` from a Hansard URL.

    How it works:
    - The Hansard app uses a hash route like `#/DateDisplay/<pdfid>/<docid>`.
    - We first try to split on `#/DateDisplay/` to reliably isolate the two IDs.
    - If that pattern is missing, we fall back to the last two URL segments.

    Returns a tuple of `(pdfid, docid)`.
    """
    marker = "#/DateDisplay/"
    if marker in url:
        tail = url.split(marker, 1)[1]
        parts = [p for p in tail.split("/") if p]
        if len(parts) >= 2:
            return parts[0], parts[1]

    # Fallback: take the last 2 segments of the URL
    parts = [p for p in url.split("/") if p]
    if len(parts) < 2:
        raise ValueError("URL does not contain enough segments to extract pdfid and docid")
    return parts[-2], parts[-1]

