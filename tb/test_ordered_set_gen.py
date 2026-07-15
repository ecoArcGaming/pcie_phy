"""
Golden cocotb tests for rtl/ordered_set_gen.sv (Phase 2, test-first).

DUT contract
------------
    start                 : pulse (when idle) to emit the selected ordered set.
    os_type[2:0]          : OS_TS1/TS2/SKP/EIOS/FTS/EIEOS (see model).
    link_num/lane_num/n_fts/rate_id/train_ctl : TS1/TS2 field bytes.
    link_pad/lane_pad     : send PAD (K23.7) instead of Link/Lane number.
    data_out[7:0], k_out  : emitted character; valid while valid_out=1.
    busy                  : high while emitting.
    done                  : 1-cycle pulse on the final symbol.

The first symbol appears the cycle after `start`. Oracle: model_ordered_sets.
"""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

import model_ordered_sets as m

CLK_PERIOD_NS = 10


async def _start_clock(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())


async def _reset(dut):
    dut.rst_n.value = 0
    dut.start.value = 0
    dut.os_type.value = 0
    for sig in ("link_num", "lane_num", "n_fts", "rate_id", "train_ctl"):
        getattr(dut, sig).value = 0
    dut.link_pad.value = 0
    dut.lane_pad.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


async def emit(dut, os_type, link=0, lane=0, n_fts=0, rate_id=0, train_ctl=0,
               link_pad=False, lane_pad=False):
    """Pulse start, collect the emitted (byte, k) stream until `done`."""
    dut.os_type.value = os_type
    dut.link_num.value = link
    dut.lane_num.value = lane
    dut.n_fts.value = n_fts
    dut.rate_id.value = rate_id
    dut.train_ctl.value = train_ctl
    dut.link_pad.value = 1 if link_pad else 0
    dut.lane_pad.value = 1 if lane_pad else 0

    dut.start.value = 1
    await RisingEdge(dut.clk)          # latches request
    dut.start.value = 0

    got = []
    for _ in range(64):                # safety bound
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        if int(dut.valid_out.value) == 1:
            got.append((int(dut.data_out.value), int(dut.k_out.value)))
        if int(dut.done.value) == 1:
            break
    return got


async def _check(dut, os_type, **kw):
    got = await emit(dut, os_type, **kw)
    exp = m.build(os_type, **kw)
    assert got == exp, (
        f"os_type={os_type}: got {[(f'{b:02X}',k) for b,k in got]} "
        f"!= exp {[(f'{b:02X}',k) for b,k in exp]}"
    )
    return got


@cocotb.test()
async def test_ts1(dut):
    await _start_clock(dut)
    await _reset(dut)
    await _check(dut, m.OS_TS1, link=1, lane=2, n_fts=8, rate_id=0x02, train_ctl=0x00)


@cocotb.test()
async def test_ts1_with_pad(dut):
    """Unconfigured Link/Lane numbers are sent as PAD (K23.7)."""
    await _start_clock(dut)
    await _reset(dut)
    await _check(dut, m.OS_TS1, link_pad=True, lane_pad=True, n_fts=255)


@cocotb.test()
async def test_ts2(dut):
    await _start_clock(dut)
    await _reset(dut)
    await _check(dut, m.OS_TS2, link=5, lane=0, rate_id=0x02, train_ctl=0x20)


@cocotb.test()
async def test_skp(dut):
    await _start_clock(dut)
    await _reset(dut)
    await _check(dut, m.OS_SKP)


@cocotb.test()
async def test_eios(dut):
    await _start_clock(dut)
    await _reset(dut)
    await _check(dut, m.OS_EIOS)


@cocotb.test()
async def test_fts(dut):
    await _start_clock(dut)
    await _reset(dut)
    await _check(dut, m.OS_FTS)


@cocotb.test()
async def test_eieos(dut):
    await _start_clock(dut)
    await _reset(dut)
    await _check(dut, m.OS_EIEOS)


@cocotb.test()
async def test_back_to_back(dut):
    """Two ordered sets emitted in sequence; busy/done frame each correctly."""
    await _start_clock(dut)
    await _reset(dut)
    await _check(dut, m.OS_TS1, link=3, lane=1, rate_id=0x02)
    # After done, the generator must be idle and ready for the next request.
    assert int(dut.busy.value) == 0, "still busy after done"
    await _check(dut, m.OS_SKP)
    await _check(dut, m.OS_EIEOS)
