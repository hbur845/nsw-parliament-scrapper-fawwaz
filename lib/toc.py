"""TOC retrieval and traversal utilities.

Provides functions to fetch the table of contents (TOC) for a given `pdfid`,
and helpers to traverse or extract topics from the TOC tree.
"""

import json
from typing import Iterator, List, Optional, Tuple

from .api import http, TOC, TOCItems, DocumentIDTitlePair


def get_toc(pdf_id: str) -> TOC:
    """Retrieve table of contents from API based on `pdf_id`.

    Endpoint: POST /api/hansard/search/daily/tableofcontentsbydate/{pdf_id}
    The API returns a JSON string; we `json.loads` to get the list structure.
    """
    api_base_url = "https://api.parliament.nsw.gov.au/api/hansard/search/daily/tableofcontentsbydate"

    response = http(f"{api_base_url}/{pdf_id}", "POST")
    response.raise_for_status()

    # The API returns a JSON-encoded string; decode robustly even if content-type is odd.
    body = response.text
    if not body or not body.strip():
        raise ValueError("Empty TOC response body")
    try:
        first = json.loads(body)
    except json.JSONDecodeError:
        # Fallback to requests' JSON parser if server mislabels encoding
        first = response.json()
    # First level often returns a JSON string; decode again if needed
    return json.loads(first) if isinstance(first, str) else first


def zip_toc_and_id(items: TOCItems) -> List[DocumentIDTitlePair]:
    """Extract document IDs and titles from TOC items (top-level proceedings).

    Produces a lightweight index of pairs: { doc_id, title }.
    """
    zipped = [
        {"doc_id": item.get("item", [{}])[0].get("docid"), "title": item.get("name")}
        for item in items
    ]
    return zipped


def walk_topics(toc_root: dict) -> Iterator[Tuple[dict, dict]]:
    """Yield every (proceeding, topic) pair from a TOC root.

    How it works:
    - Iterates over `toc_root['item']` for items with type == 'Proceeding'.
    - For each proceeding, iterates its `item` list and yields Topic dicts.
    - Skips anything not shaped as a Topic.
    """
    for proceeding in toc_root.get("item", []) or []:
        if proceeding.get("type") != "Proceeding":
            continue
        for topic in proceeding.get("item", []) or []:
            if topic.get("type") == "Topic":
                yield proceeding, topic


def find_topic_branch(toc_root: dict, target_docid: str) -> Optional[dict]:
    """Return a minimal tree containing only the Proceeding with the target Topic.

    How it works:
    - Walks top-level `Proceeding` items and scans their `item` list for a `Topic`
      whose `docid` matches `target_docid`.
    - When found, returns a new tree: Root → that Proceeding → only the matched Topic.
    - If not found, returns None.
    """
    for proceeding in toc_root.get("item", []):
        if proceeding.get("type") != "Proceeding":
            continue
        for topic in proceeding.get("item", []) or []:
            if topic.get("type") == "Topic" and topic.get("docid") == target_docid:
                # Build minimal root → proceeding → [topic]
                new_topic = dict(topic)  # shallow copy before augmentation
                new_proceeding = {
                    "name": proceeding.get("name"),
                    "type": proceeding.get("type"),
                    "expanded": proceeding.get("expanded", False),
                    "item": [new_topic],
                }
                return {
                    "pdfid": toc_root.get("pdfid"),
                    "type": toc_root.get("type"),
                    "expanded": toc_root.get("expanded", False),
                    "date": toc_root.get("date"),
                    "chamber": toc_root.get("chamber"),
                    "draft": toc_root.get("draft", False),
                    "item": [new_proceeding],
                }
    return None
