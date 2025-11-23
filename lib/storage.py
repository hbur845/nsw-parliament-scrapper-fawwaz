"""JSON output writers and storage helpers.

Creates a single large augmented TOC file per `pdfid` at `storage/<pdfid>.json`.
Optionally displays a progress bar while fetching topic fragments.
"""

import json
from pathlib import Path
from typing import Dict, List

from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

from .fragments import get_pdf_fragments
from .parser import parse_fragment
from .toc import walk_topics


def augment_all_topics_and_write(
    pdf_id: str,
    toc_root: dict,
    *,
    show_progress: bool = True,
    max_workers: int = 12,
    parse_engine: str = "lxml",
) -> Path:
    """Fetch fragments for all Topics concurrently and write one large file.

    Performance strategies implemented:
    - Concurrency: bounded ThreadPool (default 12 workers) to overlap network I/O.
    - Single Session pooling (in `lib.api.http`) to keep connections warm.
    - Fast parsing: default `lxml` parser; switchable via `parse_engine` ("lxml" or "bs4").

    Output:
    - Large: `storage/<pdfid>.json` containing [augmented_toc_root]

    Behavior on errors:
    - If a topic fails (e.g., 502 even after retries), we log a clear warning and continue.
    """
    # Collect all topics with a docid
    topics: List[dict] = [
        topic for _proc, topic in walk_topics(toc_root) if topic.get("docid")
    ]

    def fetch_and_parse(topic: dict) -> Dict[str, object]:
        docid = topic["docid"]
        html = get_pdf_fragments(docid)
        return {"rawHTML": html, "parsed": parse_fragment(html, engine=parse_engine)}

    pbar = (
        tqdm(total=len(topics), desc=f"Fetching topics for {pdf_id}")
        if show_progress
        else None
    )

    try:
        # Create a thread pool to fetch and parse topics concurrently
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            # Map futures to topics for result association
            future_map = {pool.submit(fetch_and_parse, t): t for t in topics}
            # As each future completes, augment the corresponding topic
            for fut in as_completed(future_map):
                topic = future_map[fut]
                try:
                    data = fut.result()
                    topic["data"] = data
                except Exception as e:
                    topic_name = (topic.get("name") or "<unknown topic>").strip()
                    docid = topic.get("docid")
                    print(
                        f"Warning: The topic '{topic_name}' with document id '{docid}' failed to fetch after retries. "
                        f"Error: {e}. Skipping."
                    )
                finally:
                    if pbar:
                        pbar.update(1)
    finally:
        if pbar:
            pbar.close()

    # Write large file with the fully augmented toc_root
    storage_dir = Path("storage")
    storage_dir.mkdir(parents=True, exist_ok=True)

    large_path = storage_dir / f"{pdf_id}.json"
    with large_path.open("w", encoding="utf-8") as f:
        json.dump([toc_root], f, ensure_ascii=False, indent=2)
    return large_path
