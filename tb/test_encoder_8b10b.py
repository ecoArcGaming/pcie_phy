"""
cocotb tests for rtl/encoder_8b10b.sv

DUT contract
------------
    clk        : rising-edge clock
    rst_n      : active-low synchronous reset; resets running disparity to
                 NEG (-1) and clears valid_out.
    valid_in   : input character valid this cycle (RD only advances on valid).
    data_in[7:0]: character, {H G F E D C B A} (bit0 = A = LSB).
    k_in       : 1 = control (K) symbol.
    data_out[9:0]: encoded symbol; data_out[9] = a = first bit on the wire,
                 data_out[0] = j = last. (int value == int(model_string, 2).)
    valid_out  : registered, follows valid_in by one clock.
    code_err   : registered; 1 when k_in asserted with an invalid control code.

Latency: 1 clock. The symbol driven while valid_in=1 appears on data_out after
the next rising edge.

The reference model (tb/model_8b10b.py) is the source of truth; it self-tests
its own tables against published K-symbol constants at import.
"""
import os
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

from model_8b10b import encode, is_valid_k, NEG, POS

CLK_PERIOD_NS = 10


async def _start_clock(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())

async def _reset(dut):
    dut.rst_n.value = 0
    dut.valid_in.value = 0
    dut.data_in.value = 0
    dut.k_in.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


def _flip_byte(rd, want):
    """A data byte whose encoding drives running disparity from rd to want."""
    if rd == want:
        return None
    for b in range(256):
        _, nrd, _ = encode(b, False, rd)
        if nrd == want:
            return b
    raise AssertionError("no disparity-flipping byte found")


def build_targets(targets):
    """Build a symbol stream that presents each (byte, k, want_rd) target with
    the requested starting disparity, inserting data 'flipper' symbols as
    needed. Returns the stream; running disparity starts at NEG (post-reset)."""
    stream, rd = [], NEG
    for byte, k, want in targets:
        fb = _flip_byte(rd, want)
        if fb is not None:
            stream.append((fb, False))
            _, rd, _ = encode(fb, False, rd)
        stream.append((byte, k))
        _, rd, _ = encode(byte, k, rd)
    return stream


async def run_stream(dut, symbols):
    """Drive `symbols` (list of (byte, k)) one per clock and check each encoded
    output against the reference model, threading running disparity from NEG."""
    rd = NEG
    dut.valid_in.value = 1
    for byte, k in symbols:
        dut.data_in.value = byte
        dut.k_in.value = 1 if k else 0
        exp_str, rd, exp_err = encode(byte, k, rd)
        exp_int = int(exp_str, 2)

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")   # let registered outputs settle past NBA

        assert int(dut.valid_out.value) == 1, "valid_out deasserted mid-stream"
        got = int(dut.data_out.value)
        assert got == exp_int, (
            f"byte=0x{byte:02X} k={int(k)} rd_in->{rd}: "
            f"got {got:010b}, expected {exp_int:010b} ({exp_str})"
        )
        # Explicit line-code invariant (also implied by the golden match).
        assert bin(got).count("1") in (4, 5, 6), f"bad ones-count: {got:010b}"
        assert int(dut.code_err.value) == (1 if exp_err else 0), (
            f"byte=0x{byte:02X} k={int(k)}: code_err mismatch"
        )
    dut.valid_in.value = 0


@cocotb.test()
async def test_reset_and_idle(dut):
    """valid_out is low after reset and while valid_in is deasserted."""
    await _start_clock(dut)
    await _reset(dut)
    assert int(dut.valid_out.value) == 0, "valid_out should be 0 after reset"
    for _ in range(4):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        assert int(dut.valid_out.value) == 0, "valid_out high with valid_in=0"



@cocotb.test()
async def test_exhaustive_data(dut):
    """All 256 data bytes, driven twice so each is encoded from varying RD."""
    await _start_clock(dut)
    await _reset(dut)
    stream = [(b, False) for b in range(256)] * 2
    await run_stream(dut, stream)


@cocotb.test()
async def test_all_data_bytes_both_disparities(dut):
    """Every data byte encoded from BOTH RD- and RD+ starting disparity."""
    await _start_clock(dut)
    await _reset(dut)
    targets = [(b, False, rd) for b in range(256) for rd in (NEG, POS)]
    await run_stream(dut, build_targets(targets))


@cocotb.test()
async def test_all_k_codes_both_disparities(dut):
    """All 12 valid control symbols from both starting disparities."""
    await _start_clock(dut)
    await _reset(dut)
    ks = [(28, y) for y in range(8)] + [(x, 7) for x in (23, 27, 29, 30)]
    targets = [((y << 5) | x, True, rd) for (x, y) in ks for rd in (NEG, POS)]
    await run_stream(dut, build_targets(targets))


@cocotb.test()
async def test_dx_a7_alternate(dut):
    """D.x.7 alternate (D.x.A7) selection: x in {17,18,20} at RD-, x in
    {11,13,14} at RD+ take the alternate; the opposite RD takes the primary.
    Both branches are exercised for each x."""
    await _start_clock(dut)
    await _reset(dut)
    targets = []
    for x in (17, 18, 20, 11, 13, 14):
        byte = (7 << 5) | x
        targets.append((byte, False, NEG))
        targets.append((byte, False, POS))
    await run_stream(dut, build_targets(targets))


@cocotb.test()
async def test_invalid_k_sets_code_err(dut):
    """k_in with a non-control code raises code_err; valid K does not."""
    await _start_clock(dut)
    await _reset(dut)
    stream = []
    for byte in range(256):
        x, y = byte & 0x1F, (byte >> 5) & 0x7
        if not is_valid_k(x, y):          # invalid control codes -> err
            stream.append((byte, True))
    # run_stream already asserts code_err matches the model for every symbol.
    await run_stream(dut, stream)


@cocotb.test()
async def test_random_stream(dut):
    """Long randomized mix of data and valid control symbols."""
    await _start_clock(dut)
    await _reset(dut)
    rng = random.Random(0xC0FFEE)
    valid_ks = [(28, y) for y in range(8)] + [(x, 7) for x in (23, 27, 29, 30)]
    stream = []
    for _ in range(3000):
        if rng.random() < 0.15:
            x, y = rng.choice(valid_ks)
            stream.append(((y << 5) | x, True))
        else:
            stream.append((rng.randrange(256), False))
    await run_stream(dut, stream)
