# NSW Hansard Daily Scraper

Scrapes the NSW Parliament Hansard “Daily” pages. Given one or more Hansard URLs, it:

- Extracts `pdfid` and fetches the Table of Contents (TOC) for that day
- Fetches each Topic’s fragment HTML concurrently (bounded thread pool)
- Attaches scraped data to every Topic as both raw HTML and a minimal parsed structure
- Writes a single JSON file per day to `storage/{pdfid}.json`

## Features

- Fast: concurrent network fetching, a single pooled HTTP session, and `lxml` parsing
- Resilient: retries on HTTP 502 with exponential backoff; non‑fatal warnings per topic
- Flexible: process multiple days by repeating `--url`; tunable worker count

## How It Works

Instead of driving a browser with Selenium (heavy and slow), this tool talks directly to the Hansard backend APIs. There are two key APIs involved:

- Table of contents (TOC) API — returns the left sidenav structure for a given day:
  - POST `/api/hansard/search/daily/tableofcontentsbydate/{pdfid}`
  - Think of `pdfid` as a “book” identifier for that day’s sitting. Calling this gives you the full table of contents (proceedings, topics, etc.).
- Fragment (parsed PDF page) API — returns HTML for a specific topic page:
  - POST `/api/hansard/search/daily/fragment/html/{docid}`
  - Each “Topic” in the TOC includes a `docid` which acts like a page key. Using that `docid`, we fetch the parsed HTML of that topic’s content.

End‑to‑end flow:

- Parse `pdfid` (and an example `docid`) from the URLs you pass in. We deduplicate by `pdfid` so each day is processed once.
- Fetch the TOC for the day using the `pdfid` (“open the book’s index”).
- For each topic in the TOC that has a `docid`, fetch its fragment HTML (“open the page”) and parse it.
- Attach the raw HTML and a minimal parsed structure under the corresponding topic in memory and write a single file to `storage/{pdfid}.json`.

This approach is lighter, faster, and more reliable than scraping rendered pages, while still producing a rich dataset for offline processing.

Examples

- TOC API response example: [guide/toc.json](guide/toc.json)
- Fragment API response example: [guide/fragment.json](guide/fragment.json)

## Requirements

- Python 3.12+
- Dependencies in `requirements.txt`

## Install

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Usage (CLI)

```bash
python main.py --url "https://www.parliament.nsw.gov.au/Hansard/Pages/HansardFull.aspx#/DateDisplay/<pdfid>/<docid>"
```

You can pass multiple days by repeating `--url` (the tool deduplicates by `pdfid` and writes one file per day):

```bash
python main.py \
  --url "...#/DateDisplay/HANSARD-1323879322-160378/HANSARD-..." \
  --url "...#/DateDisplay/HANSARD-1323879322-160609/HANSARD-..."
```

Tunable workers, parser engine, and progress toggle:

```bash
python main.py --url "...#/DateDisplay/<pdfid>/<docid>" --workers 16 --parse-engine lxml --no-progress
```

Environment variables (alternative to `--workers`):

- `WORKERS` or `HANSARD_WORKERS` — number of concurrent fetch threads (network I/O workers). Example:

```bash
WORKERS=20 python main.py --url "...#/DateDisplay/<pdfid>/<docid>"
```

## Output

- One JSON file per day: `storage/{pdfid}.json`
- The file contains a list with a single TOC root. Each Topic includes a `data` object:

```json
{
  "name": "…",
  "type": "Topic",
  "docid": "HANSARD-…",
  "item": [ /* sub-items as provided by the TOC */ ],
  "data": {
    "rawHTML": "<fragment.text>…</fragment.text>",
    "parsed": {
      "title": "…",           // from SubDebate-H
      "subtitle": "…",        // from SubSubDebate-H
      "blocks": [              // minimal normalized content
        { "type": "speech", "speaker": "…", "time": "…", "text": "…" },
        { "type": "paragraph", "style": "Normal|NormalBold|NormalItalics", "text": "…" }
      ]
    }
  }
}
```

## Docker

The repo includes a Dockerfile using `astral/uv:python3.12-bookworm-slim`.

Build:

```bash
docker build -t nsw-scraper .
```

Run (persist results to host `./storage`):

```bash
docker run -it --rm \
  -v "$PWD/storage:/app/storage" \
  nsw-scraper \
  --url "https://www.parliament.nsw.gov.au/Hansard/Pages/HansardFull.aspx#/DateDisplay/<pdfid>/<docid>" \
  --workers 12 --parse-engine lxml

### Parse engine options

- `--parse-engine lxml` (default): native lxml.html
- `--parse-engine bs4`: BeautifulSoup with Python's built-in html.parser
- `--parse-engine bs4-lxml`: BeautifulSoup with the lxml parser
```

Multiple days:

```bash
docker run -it --rm \
  -v "$PWD/storage:/app/storage" \
  nsw-scraper \
  --url "...#/DateDisplay/HANSARD-1323879322-160378/HANSARD-..." \
  --url "...#/DateDisplay/HANSARD-1323879322-160609/HANSARD-..."
```

Disable progress bar:

```bash
docker run -it --rm -v "$PWD/storage:/app/storage" nsw-scraper --url "…" --no-progress
```

## Design Notes

- Networking: one pooled `requests.Session` with keep‑alive (see `lib/api.py`)
- Parsing: `BeautifulSoup(..., "lxml")` for speed and robustness (see `lib/fragments.py`)
- Concurrency: `ThreadPoolExecutor` with a bounded worker count (see `lib/storage.py`)
- Retries: 502 retry with exponential backoff for fragments; non‑fatal per‑topic warnings

## Benchmarks

Run the built‑in benchmark to compare parse engines on local HTML samples:

```bash
python bench.py                     # benchmark all guide/*.html, both engines
python bench.py --engine lxml       # only native lxml
python bench.py --iterations 50     # increase iterations
python bench.py --files guide/*.html
```

Bench results from a reference machine (see bench-result for raw output):

```
System info:
  OS: Linux-6.17.4-zen2-1-zen-x86_64-with-glibc2.42
  Python: 3.12.11
  CPU: 11th Gen Intel(R) Core(TM) i5-1135G7 @ 2.40GHz
  Cores: 8
  RAM: 15.41 GiB

Benchmarking 5 file(s), iterations=500, engines=['lxml', 'bs4', 'bs4-lxml']

guide/chat.html [lxml]  0.64 ms/iter
guide/chat.html [bs4]  3.15 ms/iter
guide/chat.html [bs4-lxml]  2.63 ms/iter
  -> speedup (bs4/lxml-native): 4.91x

guide/paper-2.html [lxml]  1.16 ms/iter
guide/paper-2.html [bs4]  6.35 ms/iter
guide/paper-2.html [bs4-lxml]  5.42 ms/iter
  -> speedup (bs4/lxml-native): 5.49x

guide/paper.html [lxml]  0.52 ms/iter
guide/paper.html [bs4]  2.56 ms/iter
guide/paper.html [bs4-lxml]  2.27 ms/iter
  -> speedup (bs4/lxml-native): 4.94x

guide/simple.html [lxml]  0.44 ms/iter
guide/simple.html [bs4]  1.74 ms/iter
guide/simple.html [bs4-lxml]  1.51 ms/iter
  -> speedup (bs4/lxml-native): 3.92x

guide/table.html [lxml]  5.40 ms/iter
guide/table.html [bs4]  32.66 ms/iter
guide/table.html [bs4-lxml]  24.80 ms/iter
  -> speedup (bs4/lxml-native): 6.04x

Summary across files:
  bs4:       9.29 ms/iter
  lxml native:1.63 ms/iter
  speedup (bs4/lxml-native): 5.69x
```

Interpretation:
- Native lxml is consistently faster than BeautifulSoup parsers.
- bs4-lxml improves over bs4(html.parser) but still trails native lxml.
- Real gains also come from concurrency and session reuse; parsing is only part of the total time.

## Troubleshooting

- Empty or invalid JSON from API: transient issues are retried; if they persist, try lowering `--workers` (e.g., 6–8) and re‑run.
- Rate limiting (e.g., 429): lower concurrency (`--workers 4`) or re‑run later.
- Progress rendering in some terminals: use `--no-progress`.
