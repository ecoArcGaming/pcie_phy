"""
Phase 5: 8b/10b error-detection characterization on dec8b10b.

Each trial: reset (resync running disparity), feed a few clean symbols to
establish RD, then feed one symbol with `nbits` flipped bits and check whether
the decoder flags an error within a short window (the flipped symbol plus a few
following ones -- a single-bit error perturbs the running disparity, which is
caught on that symbol or the next). 8b/10b detects ~100% of single-bit errors;
multi-bit detection is lower. Results -> sim/perf_results.json (ber).
"""
import json
import random
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

from model_8b10b import encode, NEG

CLK = 10
TRIALS = 400
RESULTS = Path(__file__).resolve().parent.parent / "sim" / "perf_results.json"


async def _reset(dut):
    dut.rst_n.value = 0
    dut.valid_in.value = 0
    dut.data_in.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


async def _measure(dut, nbits, seed):
    rng = random.Random(seed)
    detected = 0
    for _ in range(TRIALS):
        await _reset(dut)
        rd = NEG
        dut.valid_in.value = 1
        # prime: 3 clean symbols so the decoder RD is synced
        for _ in range(3):
            out, rd, _ = encode(rng.randrange(256), False, rd)
            dut.data_in.value = int(out, 2)
            await RisingEdge(dut.clk)
        # corrupt one symbol with nbits flips
        out, rd, _ = encode(rng.randrange(256), False, rd)
        mask = 0
        for pos in rng.sample(range(10), nbits):
            mask |= (1 << pos)
        dut.data_in.value = int(out, 2) ^ mask
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        hit = int(dut.code_err.value) or int(dut.disp_err.value)

        # window: the disparity perturbation is caught on a following symbol too
        for _ in range(4):
            out, rd, _ = encode(rng.randrange(256), False, rd)
            dut.data_in.value = int(out, 2)
            await RisingEdge(dut.clk)
            await Timer(1, unit="ns")
            hit = hit or int(dut.code_err.value) or int(dut.disp_err.value)

        if hit:
            detected += 1
        dut.valid_in.value = 0
    return detected / TRIALS


@cocotb.test()
async def test_error_detection(dut):
    cocotb.start_soon(Clock(dut.clk, CLK, unit="ns").start())

    ber = []
    for nbits in (1, 2, 3):
        frac = await _measure(dut, nbits, seed=0xB0 + nbits)
        dut._log.info(f"{nbits}-bit errors: detected {frac*100:.1f}%")
        ber.append({"nbits": nbits, "detected_frac": frac})

    data = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}
    data["ber"] = ber
    RESULTS.write_text(json.dumps(data, indent=2))
    assert ber[0]["detected_frac"] >= 0.99, \
        "8b/10b should detect ~all single-bit errors within a few symbols"
