"""
Phase 5: measure the Gen2 speed-change time on phy_link.
train-to-L0 (2.5) and the 2.5 -> 5.0 recovery both reported, in cycles.
"""
import json
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

CLK_PERIOD_NS = 10
RESULTS = Path(__file__).resolve().parent.parent / "sim" / "perf_results.json"


def _save(update):
    data = {}
    if RESULTS.exists():
        data = json.loads(RESULTS.read_text())
    data.update(update)
    RESULTS.write_text(json.dumps(data, indent=2))


@cocotb.test()
async def test_speed_change_time(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    dut.sc_req_a.value = 0
    dut.lb_req_b.value = 0
    dut.rst_n.value = 0
    for _ in range(4):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

    train_cycles = 0
    while True:
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        train_cycles += 1
        if int(dut.up_a.value) and int(dut.up_b.value):
            break

    for _ in range(50):
        await RisingEdge(dut.clk)

    dut.sc_req_a.value = 1
    await RisingEdge(dut.clk)
    dut.sc_req_a.value = 0

    sc_cycles = 0
    while True:
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        sc_cycles += 1
        if (int(dut.up_a.value) and int(dut.up_b.value)
                and int(dut.rate_a.value) and int(dut.rate_b.value)):
            break

    dut._log.info(f"train-to-L0 (2.5) : {train_cycles} cycles")
    dut._log.info(f"speed change 2.5->5.0 : {sc_cycles} cycles")
    _save({"train_cycles_2g5": train_cycles, "speed_change_cycles": sc_cycles})
