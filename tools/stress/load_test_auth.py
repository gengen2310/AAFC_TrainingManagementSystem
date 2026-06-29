#!/usr/bin/env python3
"""Load test — authentication endpoint.

Tests concurrent login requests to find throughput and failure behaviour.
Measures: success rate, average/max latency, rate-limit behaviour.

Usage:
    python tools/stress/load_test_auth.py [--concurrency N] [--requests N]

Default: 20 concurrent workers, 100 total requests.
"""
import argparse
import statistics
import time
import threading

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    raise

BASE = "http://localhost:8000"
CODE = "ADMIN703"

results = {"ok": 0, "fail": 0, "rate_limited": 0, "times_ms": []}
lock = threading.Lock()


def do_login():
    start = time.perf_counter()
    try:
        r = requests.post(f"{BASE}/api/auth/login", json={"code": CODE}, timeout=10)
        ms = (time.perf_counter() - start) * 1000
        with lock:
            results["times_ms"].append(ms)
            if r.status_code == 200:
                results["ok"] += 1
            elif r.status_code == 429:
                results["rate_limited"] += 1
            else:
                results["fail"] += 1
    except Exception as e:
        with lock:
            results["fail"] += 1
            print(f"  Error: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--requests", type=int, default=100)
    args = parser.parse_args()

    print(f"\nLoad test — auth login (concurrency={args.concurrency}, requests={args.requests})")
    print("=" * 60)

    batch_size = args.concurrency
    total = args.requests
    sent = 0
    wall_start = time.perf_counter()

    while sent < total:
        batch = min(batch_size, total - sent)
        threads = [threading.Thread(target=do_login) for _ in range(batch)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        sent += batch

    wall_ms = (time.perf_counter() - wall_start) * 1000
    times = results["times_ms"]
    print(f"\n  Total requests  : {total}")
    print(f"  Successful      : {results['ok']}")
    print(f"  Rate-limited    : {results['rate_limited']}")
    print(f"  Failed          : {results['fail']}")
    if times:
        print(f"  Avg latency     : {statistics.mean(times):.1f}ms")
        print(f"  Median latency  : {statistics.median(times):.1f}ms")
        print(f"  Max latency     : {max(times):.1f}ms")
        print(f"  p95 latency     : {sorted(times)[int(len(times)*0.95)]:.1f}ms")
    print(f"  Total wall time : {wall_ms:.0f}ms")
    print(f"  Throughput      : {total / (wall_ms / 1000):.1f} req/s")
    print()
    if results["rate_limited"] > 0:
        print("  Note: rate limiting triggered as expected for repeated failed logins.")
    if results["fail"] > 0:
        print(f"  WARNING: {results['fail']} unexpected failures.")


if __name__ == "__main__":
    main()
