#!/usr/bin/env python3
"""
Full cocotb regression for the PCIe PHY.

Runs every block's runner (sim/run_*.py) as a subprocess, parses the cocotb
"TESTS=.. PASS=.. FAIL=.. SKIP=.." summary line(s) from each, aggregates the
totals, prints a table, and exits non-zero if anything failed.

Usage:
    python scripts/regress.py            # run everything
    python scripts/regress.py ltssm enc  # run only suites whose name matches
"""
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIM = ROOT / "sim"

# (display name, runner script)
SUITES = [
    ("toolchain",          SIM / "run_sim.py"),
    ("8b10b-encoder",      SIM / "run_encoder.py"),
    ("8b10b-decoder",      SIM / "run_decoder.py"),
    ("scrambler",          SIM / "run_scrambler.py"),
    ("ordered-set-gen",    SIM / "run_ordered_set_gen.py"),
    ("ordered-set-parser", SIM / "run_ordered_set_parser.py"),
    ("elastic-buffer",     SIM / "run_elastic_buffer.py"),
    ("ltssm",              SIM / "run_ltssm.py"),
    ("phy-integration",    SIM / "run_phy.py"),
    ("data-integrity",     SIM / "run_data.py"),
]

SUMMARY_RE = re.compile(r"TESTS=(\d+) PASS=(\d+) FAIL=(\d+) SKIP=(\d+)")
PER_SUITE_TIMEOUT = 300   # seconds


def _kill_stray_vvp():
    """Best-effort cleanup of a simulator left behind by a timed-out suite."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/IM", "vvp.exe"],
                       capture_output=True)
    else:
        subprocess.run(["pkill", "-f", "vvp"], capture_output=True)


def _gen_rom():
    gen = ROOT / "scripts" / "gen_dec_rom.py"
    if gen.exists():
        subprocess.run([sys.executable, str(gen)], capture_output=True)


def run_suite(name, runner):
    """Return (name, tests, passed, failed, seconds, status)."""
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, str(runner)],
                           capture_output=True, text=True,
                           timeout=PER_SUITE_TIMEOUT)
        out = p.stdout + p.stderr
        rc = p.returncode
    except subprocess.TimeoutExpired as e:
        _kill_stray_vvp()
        return name, 0, 0, 1, time.time() - t0, "TIMEOUT"

    tests = passed = failed = skipped = 0
    found = False
    for m in SUMMARY_RE.finditer(out):
        found = True
        tests   += int(m.group(1))
        passed  += int(m.group(2))
        failed  += int(m.group(3))
        skipped += int(m.group(4))

    if not found:
        status = "ERROR" if rc != 0 else "NO-TESTS"
        return name, 0, 0, 1 if rc != 0 else 0, time.time() - t0, status

    status = "PASS" if (failed == 0 and rc == 0) else "FAIL"
    return name, tests, passed, failed, time.time() - t0, status


def main():
    argv = sys.argv[1:]
    suites = SUITES
    if argv:
        suites = [(n, r) for (n, r) in SUITES
                  if any(a.lower() in n.lower() for a in argv)]
        if not suites:
            print(f"no suites match {argv}; known: {[n for n, _ in SUITES]}")
            return 2

    print("Regenerating decode ROM...")
    _gen_rom()
    print(f"Running {len(suites)} suite(s)...\n")

    rows = []
    for name, runner in suites:
        row = run_suite(name, runner)
        rows.append(row)
        _, t, p, f, dt, st = row
        print(f"  {st:8}  {name:20}  tests={t:<3} pass={p:<3} fail={f:<3}  {dt:5.1f}s")

    tot_t = sum(r[1] for r in rows)
    tot_p = sum(r[2] for r in rows)
    tot_f = sum(r[3] for r in rows)
    ok = all(r[5] == "PASS" for r in rows)

    print("\n" + "=" * 60)
    if ok:
        print(f"ALL PASS  --  {tot_p}/{tot_t} tests in {len(rows)} suites")
    else:
        bad = [r[0] for r in rows if r[5] != "PASS"]
        print(f"FAILURES  --  {tot_p}/{tot_t} passed, {tot_f} failed; "
              f"problem suites: {', '.join(bad)}")
    print("=" * 60)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
