"""
Phase 5 performance measurement on link_top (full datapath, MAC stubs).

Measures:
  * link-training time  (reset -> both L0), in cycles.
  * pipeline latency    (approx, first payload byte through the datapath).
  * effective throughput (L0 payload utilization -> MB/s at 2.5 / 5.0 GT/s).

Model timing: 1 clock = 1 symbol. Gen1 symbol time = 4 ns (2.5 GT/s / 10b),
Gen2 = 2 ns, i.e. per-lane ceilings of 250 / 500 MB/s. Metrics are logged and
written to sim/perf_results.json.
"""
import json
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

CLK_PERIOD_NS = 10
MAC_SKIP = 64          # mac_stub settling skip before counting rx
WINDOW = 4000          # throughput measurement window (cycles)

RESULTS = Path(__file__).resolve().parent.parent / "sim" / "perf_results.json"


def _save(update):
    data = {}
    if RESULTS.exists():
        data = json.loads(RESULTS.read_text())
    data.update(update)
    RESULTS.write_text(json.dumps(data, indent=2))


@cocotb.test()
async def test_perf(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    dut.rst_n.value = 0
    for _ in range(4):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

    # --- training time -------------------------------------------------
    train_cycles = 0
    while True:
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        train_cycles += 1
        if int(dut.up_a.value) and int(dut.up_b.value):
            break

    # --- latency (approx): cycles from L0 to first counted rx byte, minus
    #     the mac_stub settling skip ------------------------------------
    lat_cycles = 0
    while int(dut.rx_count_b.value) == 0:
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        lat_cycles += 1
    latency = max(lat_cycles - MAC_SKIP, 0)

    # --- throughput: payload utilization over a steady window ----------
    await Timer(1, unit="ns")
    rx0 = int(dut.rx_count_b.value)
    for _ in range(WINDOW):
        await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    rx1 = int(dut.rx_count_b.value)
    util = (rx1 - rx0) / WINDOW           # payload bytes per symbol
    mbps_gen1 = util * 250.0
    mbps_gen2 = util * 500.0

    dut._log.info(f"training time     : {train_cycles} cycles")
    dut._log.info(f"pipeline latency  : ~{latency} symbols")
    dut._log.info(f"L0 utilization    : {util*100:.1f}% of symbols carry payload")
    dut._log.info(f"throughput Gen1   : {mbps_gen1:.1f} MB/s (ceiling 250)")
    dut._log.info(f"throughput Gen2   : {mbps_gen2:.1f} MB/s (ceiling 500)")

    _save({
        "train_cycles": train_cycles,
        "latency_symbols": latency,
        "l0_utilization": util,
        "throughput_gen1_MBps": mbps_gen1,
        "throughput_gen2_MBps": mbps_gen2,
    })

    assert util > 0.9, "unexpectedly low L0 utilization"
