#!/usr/bin/env python3
"""Small utility to report CPU and RSS for Gunicorn master and workers.

This script looks for processes whose command line contains all target
substrings (by default: "gunicorn" and "app.main:app"). It then samples CPU
usage and memory (RSS), sorts processes, and prints a compact report in a
formatted table.

Notes:
    * Requires the ``psutil`` and ``tabulate`` packages.
    * No changes were made to the program logic—only formatting and
      documentation per PEP 8.
"""

import time

import psutil
from tabulate import tabulate


TARGET_SUBSTRINGS = ("gunicorn", "app.main:app")


def is_target(proc):
    """Return True if the given process matches the target command criteria.

    Args:
        proc (psutil.Process): A process instance to inspect.

    Returns:
        bool: ``True`` if all substrings in ``TARGET_SUBSTRINGS`` appear in the
        space-joined command line of the process, otherwise ``False``.

    Notes:
        Any ``psutil.NoSuchProcess`` or ``psutil.AccessDenied`` errors are
        handled and treated as a non-match.
    """
    try:
        cmd = " ".join(proc.cmdline() or [])
        return all(s in cmd for s in TARGET_SUBSTRINGS)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def fmt_mb(bytes_):
    """Format a byte count as a human-readable string in megabytes.

    Args:
        bytes_ (int): Size in bytes.

    Returns:
        str: Size formatted as ``"{value:.1f} MB"``.
    """
    return f"{bytes_ / (1024 * 1024):.1f} MB"


def main():
    """Collect and print CPU and memory stats for target processes.

    The function:
        1. Iterates all processes and filters them with :func:`is_target`.
        2. Primes CPU measurement for accuracy and sleeps briefly.
        3. Gathers CPU%, RSS, PID/PPID, and command line for each process.
        4. Sorts rows to show the master first (by PPID) and then workers by
           memory usage.
        5. Prints a formatted table and overall totals.
    """
    procs = [
        p
        for p in psutil.process_iter(["pid", "ppid", "name", "cmdline"])
        if is_target(p)
    ]

    # Accurate CPU% measurement requires sampling across a short interval.
    for p in procs:
        try:
            p.cpu_percent(None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    time.sleep(0.3)

    rows = []
    for p in procs:
        try:
            cpu = p.cpu_percent(None)
            mem = p.memory_info().rss
            rows.append(
                {
                    "Role": "MASTER" if p.ppid() == 1 else "worker",
                    "PID": p.pid,
                    "PPID": p.ppid(),
                    "CPU %": f"{cpu:.1f}",
                    "RAM": fmt_mb(mem),
                    "Command": " ".join(p.cmdline() or []),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Sort with the master (PPID == 1) first, then workers by memory usage (desc).
    rows.sort(key=lambda r: (r["PPID"] != 1, -int(r["RAM"].split()[0].replace('.', ''))))

    total_rss = sum(p.memory_info().rss for p in procs if p.is_running())
    total_cpu = sum(p.cpu_percent(None) for p in procs if p.is_running())

    print("Master + workers (sorted):")
    print(tabulate(rows, headers="keys", tablefmt="pretty"))

    print("\nTotals:")
    print(f"  Processes: {len(rows)} (expect 6 = 1 master + 5 workers)")
    print(f"  CPU sum : {total_cpu:.1f}%")
    print(f"  RAM sum : {fmt_mb(total_rss)}")


if __name__ == "__main__":
    main()
