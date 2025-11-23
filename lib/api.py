import requests
from requests.adapters import HTTPAdapter

from fake_useragent import UserAgent
from typing import Dict, Literal, List, Optional, TypedDict, Union


class TOCMemberItem(TypedDict):
    id: str
    name: str
    type: Literal["Member"]
    xref: str


class TOCItem(TypedDict):
    id: Optional[str]
    name: str
    docid: Optional[str]
    type: Literal["Proceeding", "Topic", "Subproceeding"]
    expanded: bool
    item: Optional["TOCItemsUnion"]


class TOCRoot(TypedDict):
    pdfid: str
    type: Literal["Root"]
    expanded: bool
    date: str
    chamber: str
    draft: bool
    item: "TOCItems"

class DocumentIDTitlePair(TypedDict):
    doc_id: str
    title: str

TOC = List[TOCRoot]
TOCItems = List["TOCItem"]
TOCItemsUnion = List[Union["TOCItem", "TOCMemberItem"]]


def generate_browser_profile() -> Dict[str, str]:
    """Generate consistent browser headers that match a realistic User-Agent.

    This is called once per process and applied to a single reusable Session,
    so we keep connections warm (HTTP keep-alive) and avoid per-request jitter.
    """
    ua = UserAgent()
    user_agent = ua.random

    # Parse the User-Agent to extract browser and OS info
    if "Chrome" in user_agent:
        if "Windows" in user_agent:
            platform = '"Windows"'
        elif "Mac" in user_agent:
            platform = '"macOS"'
        else:
            platform = '"Linux"'
        # Extract Chrome version
        chrome_version = user_agent.split("Chrome/")[1].split(".")[0] if "Chrome/" in user_agent else "140"
        sec_ch_ua = f'"Chromium";v="{chrome_version}", "Google Chrome";v="{chrome_version}", "Not=A?Brand";v="24"'
    elif "Firefox" in user_agent:
        sec_ch_ua = '"Firefox";v="128"'
        if "Windows" in user_agent:
            platform = '"Windows"'
        elif "Mac" in user_agent:
            platform = '"macOS"'
        else:
            platform = '"Linux"'
    else:  # Safari or other
        sec_ch_ua = '"Safari";v="17"'
        platform = '"macOS"'

    return {
        "user-agent": user_agent,
        "sec-ch-ua": sec_ch_ua,
        "sec-ch-ua-platform": platform,
        "sec-ch-ua-mobile": "?0",
    }


# A single reusable Session with connection pooling keeps requests fast.
_SESSION: Optional[requests.Session] = None  # type: ignore[assignment]


def _init_session() -> requests.Session:
    """Configure and return a global requests.Session with pooling and headers.

    - Mounts an HTTPAdapter with a larger pool size to support concurrency.
    - Applies stable browser headers once (keep-alive, gzip, user-agent, etc.).
    """
    global _SESSION
    if _SESSION is not None:
        return _SESSION

    s = requests.Session()

    adapter = HTTPAdapter(pool_connections=32, pool_maxsize=32)
    s.mount("https://", adapter)
    s.mount("http://", adapter)

    base_headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "accept-language": "en-US,en;q=0.8",
        "accept-encoding": "gzip, deflate",
        "content-type": "application/json",
        "connection": "keep-alive",
        "origin": "https://www.parliament.nsw.gov.au",
        "priority": "u=1, i",
        "referer": "https://www.parliament.nsw.gov.au/",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "sec-gpc": "1",
    }
    base_headers.update(generate_browser_profile())
    s.headers.update(base_headers)

    _SESSION = s
    return s


def http(url, method="GET", **kwargs):
    """Make a request using a single pooled Session with stable headers.

    Notes
    - No artificial per-request sleep — we are I/O-bound, so concurrency + pooling wins.
    - A `content-length: 0` header is added for empty POSTs to match the site’s expectations.
    - Custom headers can be provided via `headers=...` and will be merged per request.
    """
    session = _init_session()

    headers = kwargs.pop("headers", {}) or {}
    # Handle content-length for empty body on POST
    if method.upper() == "POST" and not kwargs.get("data") and not kwargs.get("json"):
        headers.setdefault("content-length", "0")

    if headers:
        # Merge per-request headers over session defaults
        request_headers = dict(session.headers)
        request_headers.update(headers)
    else:
        request_headers = None

    response = session.request(method, url, headers=request_headers, **kwargs)
    return response
