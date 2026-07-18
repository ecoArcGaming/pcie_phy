"""
rx_pipe test: real 8b/10b decoder feeding the elastic buffer across a ppm clock
boundary. An encoded, SKP-bearing symbol stream is driven on the recovered
(write) clock; the decoded payload is read on the local (core) clock.

Asserts: byte-exact decoded payload (data bytes are consecutive), no over/under-
flow, and that the elastic buffer actually adds/deletes SKP under the ppm offset.
"""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer, Event

from model_8b10b import encode, NEG
from model_ordered_sets import COM, SKP

CORE_PERIOD_PS = 10000
SKP_INTERVAL = 128
N_SYMBOLS = 6000


def build_symbol_stream(n):
    """Counter data bytes with a SKP ordered set (COM + 3 SKP) every
    SKP_INTERVAL, encoded to 10-bit symbols (RD threaded from NEG)."""
    pairs, data = [], 0
    while len(pairs) < n:
        for _ in range(SKP_INTERVAL):
            pairs.append((data & 0xFF, False))
            data = (data + 1) & 0xFF
        pairs += [(COM, True)] + [(SKP, True)] * 3
    pairs = pairs[:n]

    rd, syms = NEG, []
    for byte, k in pairs:
        out, rd, _ = encode(byte, k, rd)
        syms.append(int(out, 2))
    return syms


async def _reset(dut):
    dut.rst_n.value = 0
    dut.rx_valid.value = 0
    dut.rx_symbol.value = 0
    await Timer(100, unit="ns")
    dut.rst_n.value = 1
    await Timer(20, unit="ns")


async def _writer(dut, syms, done_ev):
    for s in syms:
        dut.rx_valid.value = 1
        dut.rx_symbol.value = s
        await RisingEdge(dut.rx_clk)
    dut.rx_valid.value = 0
    done_ev.set()


async def _run(dut, rx_period_ps):
    cocotb.start_soon(Clock(dut.core_clk, CORE_PERIOD_PS, unit="ps").start())
    await Timer(3, unit="ns")   # phase-offset the recovered clock
    cocotb.start_soon(Clock(dut.rx_clk, rx_period_ps, unit="ps").start())
    await _reset(dut)

    syms = build_symbol_stream(N_SYMBOLS)
    done_ev = Event()
    cocotb.start_soon(_writer(dut, syms, done_ev))

    # capture decoded payload (data chars only) on the core clock
    expected = None
    checked = 0
    skipped = 0
    while not done_ev.is_set():
        await FallingEdge(dut.core_clk)
        if int(dut.valid_out.value) == 1 and int(dut.k_out.value) == 0:
            d = int(dut.data_out.value)
            if skipped < 64:
                skipped += 1
            else:
                if expected is not None:
                    assert d == expected, \
                        f"payload not byte-exact: got {d}, expected {expected}"
                    checked += 1
                expected = (d + 1) & 0xFF

    assert int(dut.overflow.value) == 0, "elastic buffer overflowed"
    assert int(dut.underflow.value) == 0, "elastic buffer underflowed"
    assert checked > 500, f"too little payload checked: {checked}"
    return int(dut.add_count.value), int(dut.del_count.value), checked


@cocotb.test()
async def test_write_faster(dut):
    """Recovered clock ~1000 ppm faster -> deletes; payload byte-exact."""
    adds, dels, n = await _run(dut, rx_period_ps=9990)
    dut._log.info(f"faster: adds={adds} dels={dels} checked={n}")
    assert dels > 0, "expected SKP deletions"


@cocotb.test()
async def test_write_slower(dut):
    """Recovered clock ~1000 ppm slower -> adds; payload byte-exact."""
    adds, dels, n = await _run(dut, rx_period_ps=10010)
    dut._log.info(f"slower: adds={adds} dels={dels} checked={n}")
    assert adds > 0, "expected SKP additions"
