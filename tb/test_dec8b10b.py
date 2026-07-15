"""
Golden cocotb tests for rtl/dec8b10b.sv 

DUT contract
------------
    clk        : rising-edge clock
    rst_n      : active-low synchronous reset; RD -> NEG, clears valid_out.
    valid_in   : input symbol valid this cycle (RD advances on valid).
    data_in[9:0]: codeword {a..j}; data_in[9] = a = first on the wire.
    data_out[7:0]: decoded character {H G F E D C B A}.
    k_out      : 1 = control (K) symbol.
    valid_out  : registered, follows valid_in by one clock.
    code_err   : registered; 1 = illegal codeword.
    disp_err   : registered; 1 = running-disparity error.

Latency: 1 clock. Oracle: tb/model_8b10b.py (encode / decode_symbol), which
self-tests its tables (incl. all 1024 codewords) on import.
"""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

from model_8b10b import encode, decode_symbol, decode, NEG, POS

CLK_PERIOD_NS = 10


async def _start_clock(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())


async def _reset(dut):
    dut.rst_n.value = 0
    dut.valid_in.value = 0
    dut.data_in.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


def encode_stream(pairs):
    """Encode a list of (byte, k) into codeword ints, threading RD from NEG."""
    rd, cws = NEG, []
    for byte, k in pairs:
        out, rd, _ = encode(byte, k, rd)
        cws.append(int(out, 2))
    return cws


async def run_decode(dut, codewords, *, expect_clean=True):
    """Drive 10-bit codewords one per clock; check decode against the model,
    threading RD from NEG. If expect_clean, also assert no errors arise."""
    rd = NEG
    dut.valid_in.value = 1
    for cw in codewords:
        dut.data_in.value = cw
        cw_str = format(cw, "010b")
        byte, k, cerr, derr, rd = decode_symbol(cw_str, rd)

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        assert int(dut.valid_out.value) == 1, "valid_out deasserted mid-stream"
        assert int(dut.code_err.value) == int(cerr), f"{cw_str}: code_err"
        assert int(dut.disp_err.value) == int(derr), f"{cw_str}: disp_err"
        if not cerr:
            got = int(dut.data_out.value)
            assert got == byte, f"{cw_str}: data {got:08b} != {byte:08b}"
            assert int(dut.k_out.value) == int(k), f"{cw_str}: k_out"
        if expect_clean:
            assert not cerr and not derr, f"{cw_str}: unexpected error"
    dut.valid_in.value = 0


# --- tests -----------------------------------------------------------------
@cocotb.test()
async def test_reset_and_idle(dut):
    """valid_out low after reset and while valid_in is deasserted."""
    await _start_clock(dut)
    await _reset(dut)
    assert int(dut.valid_out.value) == 0
    for _ in range(4):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        assert int(dut.valid_out.value) == 0


@cocotb.test()
async def test_roundtrip_data(dut):
    """Encode every data byte (twice, for RD variation) and decode it back
    byte-exact with no errors; decoder RD stays locked to the encoder's."""
    await _start_clock(dut)
    await _reset(dut)
    pairs = [(b, False) for b in range(256)] * 2
    await run_decode(dut, encode_stream(pairs))


@cocotb.test()
async def test_roundtrip_k(dut):
    """Round-trip all 12 valid control symbols interleaved with data."""
    await _start_clock(dut)
    await _reset(dut)
    ks = [(28, y) for y in range(8)] + [(x, 7) for x in (23, 27, 29, 30)]
    pairs = []
    for x, y in ks:
        pairs.append(((y << 5) | x, True))
        pairs.append((0x55, False))      # a data byte between K's
    await run_decode(dut, encode_stream(pairs))


@cocotb.test()
async def test_roundtrip_random(dut):
    """Randomized data + control stream, decoded back clean."""
    await _start_clock(dut)
    await _reset(dut)
    rng = random.Random(0xDEC0DE)
    valid_ks = [(28, y) for y in range(8)] + [(x, 7) for x in (23, 27, 29, 30)]
    pairs = []
    for _ in range(500):
        if rng.random() < 0.15:
            x, y = rng.choice(valid_ks)
            pairs.append(((y << 5) | x, True))
        else:
            pairs.append((rng.randrange(256), False))
    await run_decode(dut, encode_stream(pairs))


@cocotb.test()
async def test_invalid_codewords(dut):
    """Every illegal 10-bit codeword raises code_err; every legal one does
    not. (Exhaustive over all 1024 words.)"""
    await _start_clock(dut)
    await _reset(dut)
    # Drive words that keep RD balanced-ish; correctness of code_err does not
    # depend on RD, and run_decode checks against the model per word.
    await run_decode(dut, list(range(1024)), expect_clean=False)


@cocotb.test()
async def test_disparity_error(dut):
    """A valid codeword whose sub-block disparity conflicts with the incoming
    RD raises disp_err -- but the data is still decoded correctly."""
    await _start_clock(dut)
    await _reset(dut)

    # D.00's RD+ form has a negative-disparity 6b sub-block; fed as the first
    # symbol (decoder RD = NEG) it is a disparity error, yet decodes to 0x00.
    cw = encode(0x00, False, POS)[0]
    b, k, cerr, derr, _ = decode_symbol(cw, NEG)
    assert derr and not cerr, "model sanity: expected a clean disparity error"

    dut.valid_in.value = 1
    dut.data_in.value = int(cw, 2)
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    assert int(dut.disp_err.value) == 1, "disp_err not raised"
    assert int(dut.code_err.value) == 0, "unexpected code_err"
    assert int(dut.data_out.value) == 0x00, "data not recovered under disp_err"
    assert int(dut.k_out.value) == 0
    dut.valid_in.value = 0
