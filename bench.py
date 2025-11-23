"""Lightweight parsing benchmark for fragment parsing engines.

Compares BeautifulSoup with the built-in html.parser ("bs4") versus lxml
("lxml") for our actual parsing workload (soup creation + parse_pdf_fragments).

Usage examples:
  python bench.py                           # benchmark all guide/*.html, both engines
  python bench.py --files guide/simple.html # limit to specific files
  python bench.py --iterations 50           # increase iterations (defaults to 20)
  python bench.py --engine lxml             # only lxml, or --engine bs4|both
"""

from __future__ import annotations

import argparse
import glob
import os
import statistics as stats
import time
from typing import List

from lib.parser import parse_fragment
import platform
import os
from typing import Optional

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None  # type: ignore


def load_files(paths: List[str] | None) -> List[str]:
    """Resolve input files.

    If no paths supplied, defaults to all HTML files in ./guide.
    """
    if not paths:
        return sorted(glob.glob(os.path.join("guide", "*.html")))
    out: List[str] = []
    for p in paths:
        if os.path.isdir(p):
            out.extend(sorted(glob.glob(os.path.join(p, "*.html"))))
        else:
            out.append(p)
    return out


def bench_file(path: str, engine: str, iterations: int) -> float:
    """Benchmark parse_fragment(html, engine) for one file.

    Returns the average time per iteration (seconds).
    """
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    times: List[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        _ = parse_fragment(content, engine=engine)
        dt = time.perf_counter() - t0
        times.append(dt)
    return stats.mean(times)

def get_system_info() -> dict:
    """Collect basic system info to annotate benchmark results.

    Attempts to use psutil for RAM; falls back to /proc/meminfo on Linux.
    CPU model best-effort (platform.processor() or /proc/cpuinfo on Linux).
    """
    os_str = platform.platform()
    py_ver = platform.python_version()
    cores = os.cpu_count() or 1

    cpu_model = platform.processor() or platform.machine()
    if (not cpu_model or cpu_model in ("x86_64", "AMD64", "arm64", "aarch64")) and platform.system() == "Linux":
        try:
            with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if "model name" in line:
                        cpu_model = line.split(":", 1)[1].strip()
                        break
        except Exception:
            pass

    ram_gb: Optional[float] = None
    if psutil is not None:
        try:
            ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 2)
        except Exception:
            ram_gb = None
    if ram_gb is None and platform.system() == "Linux":
        try:
            with open("/proc/meminfo", "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kB = int(line.split()[1])
                        ram_gb = round(kB / (1024 ** 2), 2)
                        break
        except Exception:
            pass
    if ram_gb is None:
        ram_gb = 0.0

    return {
        "os": os_str,
        "python": py_ver,
        "cpu": cpu_model,
        "cores": cores,
        "ram_gb": ram_gb,
    }


def run(files: List[str], iterations: int, engine: str):
    engines = ["lxml", "bs4", "bs4-lxml"] if engine == "both" else [engine]

    sysinfo = get_system_info()
    print("System info:")
    print(
        f"  OS: {sysinfo['os']}\n"
        f"  Python: {sysinfo['python']}\n"
        f"  CPU: {sysinfo['cpu']}\n"
        f"  Cores: {sysinfo['cores']}\n"
        f"  RAM: {sysinfo['ram_gb']} GiB\n"
    )
    print(f"Benchmarking {len(files)} file(s), iterations={iterations}, engines={engines}\n")

    results: dict[str, dict[str, float]] = {}
    for fp in files:
        results[fp] = {}
        for eng in engines:
            avg = bench_file(fp, eng, iterations)
            results[fp][eng] = avg
            print(f"{fp} [{eng}]  {avg*1000:.2f} ms/iter")
        if len(engines) == 3:
            a = results[fp].get("bs4")
            b = results[fp].get("lxml")
            if a is not None and b is not None and b > 0:
                speedup = a / b
                print(f"  -> speedup (bs4/lxml-native): {speedup:.2f}x")
        print()

    # Summary
    if len(files) > 1 and len(engines) == 3:
        bs4_avg = stats.mean([results[fp]["bs4"] for fp in files if "bs4" in results[fp]])
        lxml_avg = stats.mean([results[fp]["lxml"] for fp in files if "lxml" in results[fp]])
        print("Summary across files:")
        print(f"  bs4:       {bs4_avg*1000:.2f} ms/iter")
        print(f"  lxml native:{lxml_avg*1000:.2f} ms/iter")
        print(f"  speedup (bs4/lxml-native): {bs4_avg/lxml_avg:.2f}x")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Parse engine benchmark")
    p.add_argument("--files", action="append", help="HTML file(s) or directory; repeat to add more")
    p.add_argument("--iterations", type=int, default=20, help="Iterations per engine per file")
    p.add_argument(
        "--engine",
        choices=["bs4", "bs4-lxml", "lxml", "both"],
        default="both",
        help="Engines to benchmark",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    files = load_files(args.files)
    if not files:
        print("No files found to benchmark.")
    else:
        run(files, args.iterations, args.engine)