"""
Phase 4 data-integrity test: after the link trains to L0, both MAC stubs stream
payload through the full datapath (scrambler + 8b/10b) and scoreboard it
byte-exact. DUT = link_top.

seq_error latches if any received byte is not consecutive (corruption / drop /
dup); err_* latch on any 8b/10b decode error.
"""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

CLK_PERIOD_NS = 10
L0 = 4
CYCLE_BUDGET = 12000


async def _reset(dut):
    dut.rst_n.value = 0
    for _ in range(4):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


@cocotb.test()
async def test_payload_byte_exact(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await _reset(dut)

    # train to L0
    reached = None
    for cyc in range(CYCLE_BUDGET):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        assert int(dut.err_a.value) == 0 and int(dut.err_b.value) == 0, \
            "decoder error during training"
        if int(dut.up_a.value) and int(dut.up_b.value):
            reached = cyc
            break
    assert reached is not None, "did not reach L0"
    dut._log.info(f"trained to L0 at cycle {reached}; streaming payload...")

    # stream payload for a while, checking integrity continuously
    for _ in range(4000):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        assert int(dut.up_a.value) and int(dut.up_b.value), "dropped L0"
        assert int(dut.err_a.value) == 0 and int(dut.err_b.value) == 0, \
            "8b/10b decode error on a clean channel"
        assert int(dut.seq_error_a.value) == 0, "A: payload corrupted"
        assert int(dut.seq_error_b.value) == 0, "B: payload corrupted"

    rxa = int(dut.rx_count_a.value)
    rxb = int(dut.rx_count_b.value)
    dut._log.info(f"payload scoreboarded byte-exact: A rx={rxa}, B rx={rxb}")
    assert rxa > 1000 and rxb > 1000, \
        f"too little payload checked (A={rxa}, B={rxb})"
