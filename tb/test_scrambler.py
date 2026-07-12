"""
Golden cocotb tests for rtl/scrambler.sv (Phase 1, test-first).

DUT contract
------------
    clk, rst_n          : clock / active-low sync reset (LFSR -> 0xFFFF).
    scramble_en         : 0 = bypass (passthrough, LFSR held).
    valid_in            : input character valid this cycle.
    data_in[7:0], k_in  : character value + control flag.
    data_out[7:0], k_out: (de)scrambled character + passthrough K flag.
    valid_out           : registered, follows valid_in by one clock.

Latency: 1 clock. Oracle: tb/model_scrambler.py (self-tested on import against
the published PCIe output sequence and scramble->descramble identity).
"""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

from model_scrambler import Scrambler, COM, SKP, _GOLDEN

CLK_PERIOD_NS = 10


async def _start_clock(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())


async def _reset(dut, en=1):
    dut.scramble_en.value = en
    dut.valid_in.value = 0
    dut.data_in.value = 0
    dut.k_in.value = 0
    dut.rst_n.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


async def run_stream(dut, chars, en=1):
    """Drive (byte, k) chars one per clock; check data_out against a model
    instance mirroring the DUT."""
    model = Scrambler()
    dut.scramble_en.value = en
    dut.valid_in.value = 1
    for byte, k in chars:
        dut.data_in.value = byte
        dut.k_in.value = 1 if k else 0
        exp = model.process(byte, bool(k), en == 1)

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        assert int(dut.valid_out.value) == 1, "valid_out deasserted mid-stream"
        got = int(dut.data_out.value)
        assert got == exp, (
            f"in=0x{byte:02X} k={int(k)}: got 0x{got:02X}, exp 0x{exp:02X}"
        )
        assert int(dut.k_out.value) == int(k), "k_out mismatch"
    dut.valid_in.value = 0


@cocotb.test()
async def test_golden_sequence(dut):
    """Scrambling all-zero data reproduces the published PCIe sequence."""
    await _start_clock(dut)
    await _reset(dut)
    dut.valid_in.value = 1
    for i, exp in enumerate(_GOLDEN):
        dut.data_in.value = 0x00
        dut.k_in.value = 0
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        got = int(dut.data_out.value)
        assert got == exp, f"seq[{i}]: got 0x{got:02X}, exp 0x{exp:02X}"
    dut.valid_in.value = 0


@cocotb.test()
async def test_random_data(dut):
    """Random data stream matches the model byte-for-byte."""
    await _start_clock(dut)
    await _reset(dut)
    rng = random.Random(0x5C4A)
    await run_stream(dut, [(rng.randrange(256), False) for _ in range(1000)])


@cocotb.test()
async def test_mixed_com_skp_k(dut):
    """Mixed stream with COM (reset), SKP (no advance) and other control
    characters (advance, passthrough), all checked against the model."""
    await _start_clock(dut)
    await _reset(dut)
    rng = random.Random(0xC0FFEE)
    chars = []
    for _ in range(2000):
        r = rng.random()
        if r < 0.03:
            chars.append((COM, True))
        elif r < 0.08:
            chars.append((SKP, True))
        elif r < 0.20:
            chars.append((rng.randrange(256), True))   # other control
        else:
            chars.append((rng.randrange(256), False))  # data
    await run_stream(dut, chars)


@cocotb.test()
async def test_bypass(dut):
    """scramble_en = 0 passes data through unchanged."""
    await _start_clock(dut)
    await _reset(dut, en=0)
    rng = random.Random(0xB1)
    await run_stream(dut, [(rng.randrange(256), False) for _ in range(64)], en=0)
