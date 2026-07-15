"""
Golden cocotb tests for rtl/ordered_set_parser.sv (Phase 2, test-first).

Drives decoded (data_in, k_in) characters and collects the os_valid / os_error
pulses as an event list, comparing against model_os_parser.parse_stream. Events:
    ('good', os_type, fields)   fields = (link,lane,nfts,rate,train,
                                          link_pad,lane_pad) for TS1/TS2 else None
    ('error',)
"""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

import model_ordered_sets as m
from model_os_parser import parse_stream

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


async def run_parser(dut, pairs):
    """Feed (byte, k) pairs one per clock; return the collected event list."""
    events = []
    for i in range(len(pairs) + 2):            # +2 idle cycles to settle
        if i < len(pairs):
            byte, k = pairs[i]
            dut.valid_in.value = 1
            dut.data_in.value = byte
            dut.k_in.value = 1 if k else 0
        else:
            dut.valid_in.value = 0

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        if int(dut.os_valid.value) == 1:
            ot = int(dut.os_type.value)
            if ot in (m.OS_TS1, m.OS_TS2):
                fields = (int(dut.ts_link.value), int(dut.ts_lane.value),
                          int(dut.ts_nfts.value), int(dut.ts_rate.value),
                          int(dut.ts_train.value),
                          bool(int(dut.ts_link_pad.value)),
                          bool(int(dut.ts_lane_pad.value)))
            else:
                fields = None
            events.append(('good', ot, fields))
        if int(dut.os_error.value) == 1:
            events.append(('error',))
    dut.valid_in.value = 0
    return events


async def _check(dut, pairs):
    got = await run_parser(dut, pairs)
    exp = parse_stream(pairs)
    assert got == exp, f"\n got={got}\n exp={exp}"
    return got


@cocotb.test()
async def test_each_type(dut):
    """Each generated ordered set is detected and classified correctly."""
    await _start_clock(dut)
    await _reset(dut)
    await _check(dut, m.ts1(link=1, lane=2, n_fts=8, rate_id=2, train_ctl=0x20))
    await _check(dut, m.ts2(link=5))
    await _check(dut, m.skp_os())
    await _check(dut, m.eios())
    await _check(dut, m.fts_os())
    await _check(dut, m.eieos())


@cocotb.test()
async def test_ts_pad(dut):
    """Unconfigured Link/Lane (PAD) set the pad flags."""
    await _start_clock(dut)
    await _reset(dut)
    await _check(dut, m.ts1(link_pad=True, lane_pad=True, n_fts=255))


@cocotb.test()
async def test_back_to_back(dut):
    """A run of consecutive ordered sets yields one event each, in order."""
    await _start_clock(dut)
    await _reset(dut)
    stream = (m.ts1(link=3, lane=1, rate_id=2) + m.skp_os() + m.ts2()
              + m.eieos() + m.eios() + m.fts_os())
    await _check(dut, stream)


@cocotb.test()
async def test_malformed(dut):
    """Corrupted bodies and an interrupting COM produce error events."""
    await _start_clock(dut)
    await _reset(dut)
    # SKP body with a wrong symbol.
    await _check(dut, [(m.COM, True), (m.SKP, True), (0x00, False), (m.SKP, True)])
    # TS with one identifier symbol wrong.
    ts = list(m.ts1(link=1)); ts[10] = (m.TS2_ID, False)
    await _check(dut, ts)
    # COM interrupts a partial set, then a clean SKP.
    await _check(dut, [(m.COM, True), (0x11, False), (m.COM, True),
                       (m.SKP, True), (m.SKP, True), (m.SKP, True)])


@cocotb.test()
async def test_fuzz(dut):
    """Random mix of full ordered sets and noise; RTL must match the model
    event-for-event (valid and malformed alike)."""
    await _start_clock(dut)
    await _reset(dut)
    rng = random.Random(0xF0F0)
    noise_bytes = [m.COM, m.SKP, m.IDL, m.FTS, m.EIE, m.PAD,
                   m.TS1_ID, m.TS2_ID, 0x00, 0x55, 0xAA, 0xFF]
    builders = [lambda: m.ts1(link=rng.randrange(256), lane=rng.randrange(32),
                              n_fts=rng.randrange(256), rate_id=rng.randrange(256),
                              train_ctl=rng.randrange(256)),
                lambda: m.ts2(link=rng.randrange(256)),
                m.skp_os, m.eios, m.fts_os, m.eieos]
    stream = []
    for _ in range(400):
        if rng.random() < 0.4:
            stream += rng.choice(builders)()          # a full valid set
        else:
            b = rng.choice(noise_bytes)               # a noise symbol
            k = True if b in (m.COM, m.SKP, m.IDL, m.FTS, m.EIE, m.PAD) else \
                rng.random() < 0.3
            stream.append((b, k))
    await _check(dut, stream)
