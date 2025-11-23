import os
import argparse

from lib.url import parse_ids_from_url
from lib.toc import get_toc
from lib.storage import augment_all_topics_and_write


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments.

    --workers: number of parallel fetch threads to use (network I/O workers)
    --url: Hansard page URL; pass multiple times to process several days
    --parse-engine: parsing engine (lxml|bs4), defaults to lxml
    --no-progress: disable tqdm progress bar
    """
    parser = argparse.ArgumentParser(description="Legislative Assembly Hansard NSW scraper")
    parser.add_argument("--workers", type=int, default=None, help="Number of concurrent fetch workers (threads)")
    parser.add_argument("--url", action="append", required=True, help="Hansard URL to scrape (repeatable)")
    parser.add_argument(
        "--parse-engine",
        choices=["lxml", "bs4", "bs4-lxml"],
        default="lxml",
        help="Parsing engine to use (lxml=native, bs4, bs4-lxml)",
    )
    parser.add_argument("--no-progress", action="store_true", help="Disable progress bar")
    return parser.parse_args()


def resolve_workers(cli_workers: int | None, default: int = 12) -> int:
    """Resolve the worker count from CLI, environment, or default.

    Env vars checked: WORKERS, HANSARD_WORKERS. Value is the number of threads
    used to fetch topics concurrently (network I/O).
    """
    if cli_workers is not None:
        return max(1, cli_workers)
    env = os.getenv("WORKERS") or os.getenv("HANSARD_WORKERS")
    if env:
        try:
            return max(1, int(env))
        except ValueError:
            pass
    return default


def main():
    args = parse_args()
    urls: list[str] = args.url

    print("Scrapping the page(s)...")

    # Collect unique pdfids from provided URLs
    pdf_ids: list[str] = []
    seen = set()
    for u in urls:
        pdf_id, _ = parse_ids_from_url(u)
        if pdf_id not in seen:
            seen.add(pdf_id)
            pdf_ids.append(pdf_id)

    workers = resolve_workers(args.workers)
    print(f"Using workers: {workers}")

    for pdf_id in pdf_ids:
        print(f"\nProcessing pdfid: {pdf_id}")
        # Retrieve TOC for the day (pdf_id)
        print("Retrieving Table of Contents...")
        toc = get_toc(pdf_id)
        if not isinstance(toc, list) or len(toc) == 0:
            print(f"Warning: TOC response is not a non-empty list for pdfid={pdf_id}; skipping.")
            continue
        toc_root = toc[0]

        # Build the large output (entire day with data per Topic)
        print("Augmenting topics and writing outputs...")
        large_path = augment_all_topics_and_write(
            pdf_id,
            toc_root,
            show_progress=not args.no_progress,
            max_workers=workers,
            parse_engine=args.parse_engine,
        )
        print(f"Wrote: {large_path}")

    print("\nDone!")


if __name__ == "__main__":
    main()
