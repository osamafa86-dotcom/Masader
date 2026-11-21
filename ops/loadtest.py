"""Small load test: concurrent readers on the public pages. Prints latency percentiles and errors.

    python ops/loadtest.py --base http://localhost:3000 --concurrency 20 --requests 600
"""

import argparse
import asyncio
import random
import statistics
import time

import httpx

PATHS = ["/", "/articles/1", "/articles/3", "/articles/4", "/sources", "/topics", "/glossary", "/dossiers",
         "/search?q=%D8%B1%D8%AF%D8%B9", "/search?q=deterrence&mode=semantic", "/trends/2026-11", "/feed.xml"]


async def worker(client, queue, results):
    while True:
        try:
            path = queue.get_nowait()
        except asyncio.QueueEmpty:
            return
        t = time.perf_counter()
        try:
            r = await client.get(path)
            results.append((path, r.status_code, time.perf_counter() - t))
        except httpx.HTTPError:
            results.append((path, 0, time.perf_counter() - t))


async def main(base: str, concurrency: int, n: int) -> None:
    queue: asyncio.Queue = asyncio.Queue()
    for _ in range(n):
        queue.put_nowait(random.choice(PATHS))
    results: list = []
    started = time.perf_counter()
    async with httpx.AsyncClient(base_url=base, timeout=30, follow_redirects=True) as client:
        await asyncio.gather(*(worker(client, queue, results) for _ in range(concurrency)))
    elapsed = time.perf_counter() - started
    lat = sorted(r[2] * 1000 for r in results)
    errors = [r for r in results if r[1] >= 400 or r[1] == 0]
    pct = lambda q: lat[min(len(lat) - 1, int(q * len(lat)))]  # noqa: E731
    print(f"{len(results)} requests, {concurrency} concurrent, {elapsed:.1f}s, {len(results) / elapsed:.0f} req/s")
    print(f"latency ms: p50 {pct(0.5):.0f}  p95 {pct(0.95):.0f}  p99 {pct(0.99):.0f}  max {lat[-1]:.0f}  mean {statistics.mean(lat):.0f}")
    print(f"errors: {len(errors)}" + (f"  e.g. {errors[0][0]} -> {errors[0][1]}" if errors else ""))
    slowest = {}
    for path, _, s in results:
        slowest[path] = max(slowest.get(path, 0), s * 1000)
    for path, ms in sorted(slowest.items(), key=lambda x: -x[1])[:4]:
        print(f"  slowest {path}: {ms:.0f} ms")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:3000")
    ap.add_argument("--concurrency", type=int, default=20)
    ap.add_argument("--requests", type=int, default=600)
    a = ap.parse_args()
    asyncio.run(main(a.base, a.concurrency, a.requests))
