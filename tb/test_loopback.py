"""
Loopback test (Phase 3): a link_trainer held in Loopback echoes its RX symbol
stream back out on TX. DUT = link_trainer with loopback_req asserted.
"""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

CLK_PERIOD_NS = 10


@cocotb.test()
async def test_loopback_echo(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())

    # Hold loopback asserted through reset so the LTSSM parks in LOOPBACK.
    dut.speed_change_req.value = 0
    dut.loopback_req.value = 1
    dut.rx_data.value = 0
    dut.rx_k.value = 0
    dut.rx_valid.value = 0
    dut.rst_n.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    # let the state reach LOOPBACK and loopback_active assert
    for _ in range(3):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
    assert int(dut.loopback_active.value) == 1, "did not enter Loopback"

    rng = random.Random(0x10057)
    checks = 0
    for _ in range(500):
        d = rng.randrange(256)
        k = 1 if rng.random() < 0.2 else 0
        v = 1 if rng.random() < 0.9 else 0
        dut.rx_data.value = d
        dut.rx_k.value = k
        dut.rx_valid.value = v

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        # The registered echo, read after the capturing edge, reflects the rx
        # driven this cycle.
        assert int(dut.tx_valid.value) == v, "tx_valid echo mismatch"
        if v:
            assert int(dut.tx_data.value) == d, "tx_data echo mismatch"
            assert int(dut.tx_k.value) == k, "tx_k echo mismatch"
            checks += 1

    assert checks > 100, f"too few echo checks: {checks}"
    dut._log.info(f"loopback echoed {checks} valid symbols correctly")
