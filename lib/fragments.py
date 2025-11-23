"""Fetching fragment HTML for Topics.

This module provides:
- Network fetch to retrieve fragment HTML by `docid`.
- A conservative parser that extracts a minimal, structured representation
  (title/subtitle and blocks for speeches/paragraphs) for downstream use.
"""

import json
import time
from typing import Tuple

from .api import http


def get_pdf_fragments(
    doc_id: str,
    *,
    retries: int = 3,
    retry_status_codes: Tuple[int, ...] = (502,),
    initial_delay_seconds: float = 3.0,
    backoff: float = 2.0
) -> str:
    """Fetch Topic fragment HTML by `doc_id` and return raw HTML string.

    Resilience:
    - Retries when receiving a response with status in `retry_status_codes`
      (default: 502 Bad Gateway).
    - Uses exponential backoff between attempts.

    How it works:
    - Calls: POST /api/hansard/search/daily/fragment/html/{doc_id}
    - Response JSON is a stringified JSON; we `json.loads` it then take
      `DocumentHtml` and parse it as HTML.
    - `parse_engine` selects the BeautifulSoup parser: "lxml" (default) or "bs4".
    """
    api_base_url = (
        "https://api.parliament.nsw.gov.au/api/hansard/search/daily/fragment/html"
    )

    delay = initial_delay_seconds
    attempt = 0
    while True:
        attempt += 1
        response = http(f"{api_base_url}/{doc_id}", "POST")
        status = response.status_code
        if status in retry_status_codes and retries >= 0:
            if retries == 0:
                # Last attempt already used; raise for caller to handle
                response.raise_for_status()
            # Sleep and retry
            time.sleep(delay)
            delay *= backoff
            retries -= 1
            continue

        # For non-retry statuses, raise if not OK
        response.raise_for_status()

        # Robustly decode possible double-encoded JSON payload
        body = response.text
        if not body or not body.strip():
            raise ValueError("Empty fragment response body")

        try:
            first = json.loads(body)
        except json.JSONDecodeError:
            first = response.json()

        obj = json.loads(first) if isinstance(first, str) else first
        # See guide/fragment.json
        html_content = obj["DocumentHtml"]

        # Return raw HTML; parser selection is done upstream
        return html_content
