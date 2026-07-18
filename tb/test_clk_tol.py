"""
Phase 5: clock-tolerance sweep on rx_pipe (decoder + elastic buffer).

Runs an SKP-bearing stream at several write/read ppm offsets and records whether
the elastic buffer survives (no over/underflow). The largest surviving offset is
the clock-tolerance limit. Results -> sim/perf_results.json (clk_tol list).
"""
import json
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer, Event

from model_8b10b import encode, NEG
from model_ordered_sets import COM, SKP

CORE_PS = 10000
SKP_INTERVAL = 128
N = 4000
RESULTS = Path(__file__).resolve().parent.parent / "sim" / "perf_results.json"


def _stream(n):
    pairs, data = [], 0
    while len(pairs) < n:
        for _ in range(SKP_INTERVAL):
            pairs.append((data & 0xFF, False)); data = (data + 1) & 0xFF
        pairs += [(COM, True)] + [(SKP, True)] * 3
    pairs = pairs[:n]
    rd, syms = NEG, []
    for b, k in pairs:
        o, rd, _ = encode(b, k, rd); syms.append(int(o, 2))
    return syms


def _record(ppm, ok, adds, dels):
    data = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}
    data.setdefault("clk_tol", [])
    data["clk_tol"].append({"ppm": ppm, "survived": ok, "adds": adds, "dels": dels})
    RESULTS.write_text(json.dumps(data, indent=2))


async def _run(dut, rx_period_ps):
    cocotb.start_soon(Clock(dut.core_clk, CORE_PS, unit="ps").start())
    await Timer(3, unit="ns")
    cocotb.start_soon(Clock(dut.rx_clk, rx_period_ps, unit="ps").start())
    dut.rst_n.value = 0
    dut.rx_valid.value = 0
    dut.rx_symbol.value = 0
    await Timer(100, unit="ns")
    dut.rst_n.value = 1
    await Timer(20, unit="ns")

    syms = _stream(N)
    done = Event()

    async def writer():
        for s in syms:
            dut.rx_valid.value = 1
            dut.rx_symbol.value = s
            await RisingEdge(dut.rx_clk)
        dut.rx_valid.value = 0
        done.set()

    cocotb.start_soon(writer())
    while not done.is_set():
        await RisingEdge(dut.core_clk)
    await Timer(1, unit="ns")
    ok = (int(dut.overflow.value) == 0 and int(dut.underflow.value) == 0)
    return ok, int(dut.add_count.value), int(dut.del_count.value)


# ppm points (period in ps must be even). Both faster (delete) and slower (add).
_POINTS = [
    ("+200",   9998), ("+600",  9994), ("+1000", 9990),
    ("+2000",  9980), ("+5000", 9950), ("+10000", 9900),
    ("-1000", 10010), ("-5000", 10050),
]


def _mk(label, period):
    @cocotb.test(name=f"test_clk_tol_{label}")
    async def _t(dut):
        ok, adds, dels = await _run(dut, period)
        ppm = round((CORE_PS - period) / CORE_PS * 1e6)
        dut._log.info(f"ppm={ppm:+} survived={ok} adds={adds} dels={dels}")
        _record(ppm, ok, adds, dels)
    return _t


for _lbl, _per in _POINTS:
    globals()[f"clk_tol_{_lbl}"] = _mk(_lbl, _per)
