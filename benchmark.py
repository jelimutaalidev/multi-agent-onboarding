"""
Benchmark - CLI untuk performance testing pipeline onboarding.

Mengukur latensi, throughput, dan statistik pipeline end-to-end dengan
mode sequential dan concurrent.

Contoh penggunaan:
    python benchmark.py --runs 5 --account-type Futures
    python benchmark.py --runs 10 --concurrent --output benchmark.json
    python benchmark.py --runs 20 --format csv --output results.csv
"""

import os
import sys
import csv
import json
import time
import argparse
import statistics
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

if not os.getenv("GOOGLE_API_KEY"):
    print("[ERROR] GOOGLE_API_KEY tidak ditemukan!")
    print("   Silakan set GOOGLE_API_KEY di file .env")
    sys.exit(1)

from src.graph import run_pipeline  # noqa: E402

ACCOUNT_TYPES = ["Stocks", "ETF", "Futures", "Options", "Margin", "Forex", "Crypto"]


def run_single_benchmark(image_path: str, account_type: str) -> dict:
    start_time = time.monotonic()
    success = True
    error = None

    try:
        run_pipeline(image_path, account_type)
    except Exception as e:
        success = False
        error = str(e)

    duration_ms = (time.monotonic() - start_time) * 1000

    return {
        "duration_ms": duration_ms,
        "success": success,
        "error": error,
        "account_type": account_type,
        "timestamp": datetime.now().isoformat(),
    }


def calculate_statistics(results: list[dict]) -> dict:
    durations = [r["duration_ms"] for r in results]
    success_count = sum(1 for r in results if r["success"])
    total_count = len(results)

    stats = {
        "total_runs": total_count,
        "successful_runs": success_count,
        "failed_runs": total_count - success_count,
        "success_rate": success_count / total_count if total_count > 0 else 0,
        "min_ms": min(durations) if durations else 0,
        "max_ms": max(durations) if durations else 0,
        "avg_ms": statistics.mean(durations) if durations else 0,
        "median_ms": statistics.median(durations) if durations else 0,
    }

    if len(durations) >= 2:
        stats["stddev_ms"] = statistics.stdev(durations)
    else:
        stats["stddev_ms"] = 0

    sorted_durations = sorted(durations)
    if sorted_durations:
        p50_idx = int(len(sorted_durations) * 0.50)
        p95_idx = int(len(sorted_durations) * 0.95)
        p99_idx = int(len(sorted_durations) * 0.99)

        stats["p50_ms"] = sorted_durations[min(p50_idx, len(sorted_durations) - 1)]
        stats["p95_ms"] = sorted_durations[min(p95_idx, len(sorted_durations) - 1)]
        stats["p99_ms"] = sorted_durations[min(p99_idx, len(sorted_durations) - 1)]
    else:
        stats["p50_ms"] = 0
        stats["p95_ms"] = 0
        stats["p99_ms"] = 0

    total_time_s = sum(durations) / 1000 if durations else 1
    stats["throughput_per_second"] = (
        success_count / total_time_s if total_time_s > 0 else 0
    )

    return stats


def export_json(output_path: str, results: list[dict], stats: dict):
    data = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "total_runs": stats["total_runs"],
            "successful_runs": stats["successful_runs"],
            "failed_runs": stats["failed_runs"],
        },
        "statistics": stats,
        "results": results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    print(f"[EXPORT] JSON saved to: {output_path}")


def export_csv(output_path: str, results: list[dict], stats: dict):
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["run", "timestamp", "account_type", "duration_ms", "success", "error"]
        )

        for i, r in enumerate(results, 1):
            writer.writerow(
                [
                    i,
                    r["timestamp"],
                    r["account_type"],
                    f"{r['duration_ms']:.2f}",
                    r["success"],
                    r.get("error", ""),
                ]
            )

        writer.writerow([])
        writer.writerow(["Statistic", "Value"])
        writer.writerow(["Total Runs", stats["total_runs"]])
        writer.writerow(["Success Rate", f"{stats['success_rate']:.2%}"])
        writer.writerow(["Min (ms)", f"{stats['min_ms']:.2f}"])
        writer.writerow(["Max (ms)", f"{stats['max_ms']:.2f}"])
        writer.writerow(["Avg (ms)", f"{stats['avg_ms']:.2f}"])
        writer.writerow(["Median (ms)", f"{stats['median_ms']:.2f}"])
        writer.writerow(["P50 (ms)", f"{stats['p50_ms']:.2f}"])
        writer.writerow(["P95 (ms)", f"{stats['p95_ms']:.2f}"])
        writer.writerow(["P99 (ms)", f"{stats['p99_ms']:.2f}"])
        writer.writerow(["Std Dev (ms)", f"{stats['stddev_ms']:.2f}"])
        writer.writerow(["Throughput (req/s)", f"{stats['throughput_per_second']:.2f}"])

    print(f"[EXPORT] CSV saved to: {output_path}")


def print_stats(stats: dict):
    print("\n" + "=" * 60)
    print("[BENCHMARK] Results")
    print("=" * 60)
    print(f"   Total Runs     : {stats['total_runs']}")
    print(f"   Successful     : {stats['successful_runs']}")
    print(f"   Failed         : {stats['failed_runs']}")
    print(f"   Success Rate   : {stats['success_rate']:.2%}")
    print("-" * 60)
    print(f"   Min Latency    : {stats['min_ms']:.2f} ms")
    print(f"   Max Latency    : {stats['max_ms']:.2f} ms")
    print(f"   Avg Latency    : {stats['avg_ms']:.2f} ms")
    print(f"   Median Latency : {stats['median_ms']:.2f} ms")
    print(f"   Std Dev        : {stats['stddev_ms']:.2f} ms")
    print("-" * 60)
    print(f"   P50 Latency    : {stats['p50_ms']:.2f} ms")
    print(f"   P95 Latency    : {stats['p95_ms']:.2f} ms")
    print(f"   P99 Latency    : {stats['p99_ms']:.2f} ms")
    print("-" * 60)
    print(f"   Throughput     : {stats['throughput_per_second']:.2f} req/s")
    print("=" * 60)


def run_benchmark(args):
    image_path = args.image_path
    account_type = args.account_type
    runs = args.runs
    concurrent = args.concurrent
    output = args.output
    fmt = args.format

    if not Path(image_path).exists():
        print(f"[ERROR] File tidak ditemukan: {image_path}")
        sys.exit(1)

    print("=" * 60)
    print("[BENCHMARK] Pipeline Performance Test")
    print("=" * 60)
    print(f"   Image      : {image_path}")
    print(f"   Account    : {account_type}")
    print(f"   Runs       : {runs}")
    print(f"   Mode       : {'Concurrent' if concurrent else 'Sequential'}")
    print("=" * 60)

    results = []

    if concurrent:
        max_workers = min(runs, 8)
        print(f"\n[MODE] Concurrent ({max_workers} workers)...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(run_single_benchmark, image_path, account_type): i
                for i in range(runs)
            }

            for i, future in enumerate(as_completed(futures), 1):
                result = future.result()
                results.append(result)
                status = "[OK]" if result["success"] else "[FAIL]"
                print(f"   [{i}/{runs}] {status} {result['duration_ms']:.2f} ms")
    else:
        print("\n[MODE] Sequential...")

        for i in range(1, runs + 1):
            result = run_single_benchmark(image_path, account_type)
            results.append(result)
            status = "[OK]" if result["success"] else "[FAIL]"
            print(f"   [{i}/{runs}] {status} {result['duration_ms']:.2f} ms")

    stats = calculate_statistics(results)
    print_stats(stats)

    if output:
        if fmt == "json":
            export_json(output, results, stats)
        elif fmt == "csv":
            export_csv(output, results, stats)

    return results, stats


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark pipeline onboarding untuk performance testing"
    )
    parser.add_argument(
        "image_path",
        nargs="?",
        default="test_images/sample_ktp.png",
        help="Path ke foto dokumen identitas (default: test_images/sample_ktp.png)",
    )
    parser.add_argument(
        "--runs", "-n", type=int, default=5, help="Jumlah run benchmark (default: 5)"
    )
    parser.add_argument(
        "--account-type",
        "-a",
        default="Futures",
        choices=ACCOUNT_TYPES,
        help="Jenis akun untuk benchmark (default: Futures)",
    )
    parser.add_argument(
        "--concurrent",
        "-c",
        action="store_true",
        help="Jalankan secara concurrent (ThreadPoolExecutor)",
    )
    parser.add_argument("--output", "-o", help="Path output file (JSON atau CSV)")
    parser.add_argument(
        "--format",
        "-f",
        choices=["json", "csv"],
        default="json",
        help="Format output (default: json)",
    )

    args = parser.parse_args()

    if args.output:
        output_path = Path(args.output)
        if args.format == "csv" and not output_path.suffix:
            args.output = str(output_path) + ".csv"
        elif args.format == "json" and not output_path.suffix:
            args.output = str(output_path) + ".json"

    run_benchmark(args)


if __name__ == "__main__":
    main()
