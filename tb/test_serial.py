"""
Behavioral serial-channel test. DUT = phy_link_serial (two PHYs through
serial_channels with bit-error injection).

1. Clean channel: link trains and payload is byte-exact.
2. Bit-error injection: flipping bits on the wire makes the receiver's 8b/10b
   decoder raise code_err / disp_err (the errors are detected).
"""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

CLK_PERIOD_NS = 10
CYCLE_BUDGET = 12000


async def _reset(dut):
    dut.err_mask_a2b.value = 0
    dut.err_mask_b2a.value = 0
    dut.rst_n.value = 0
    for _ in range(4):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


async def _train(dut):
    for _ in range(CYCLE_BUDGET):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        if int(dut.up_a.value) and int(dut.up_b.value):
            return True
    return False


@cocotb.test()
async def test_clean_channel(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await _reset(dut)
    assert await _train(dut), "did not train over the serial channel"
    dut._log.info("trained over serial channel; streaming payload...")

    for _ in range(3000):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        assert int(dut.up_a.value) and int(dut.up_b.value), "dropped L0"
        assert int(dut.seq_error_a.value) == 0 and int(dut.seq_error_b.value) == 0, \
            "payload corrupted on a clean channel"
        assert int(dut.code_err_a.value) == 0 and int(dut.disp_err_a.value) == 0
        assert int(dut.code_err_b.value) == 0 and int(dut.disp_err_b.value) == 0

    assert int(dut.rx_count_a.value) > 1000 and int(dut.rx_count_b.value) > 1000
    dut._log.info(f"byte-exact over serial channel: "
                  f"A={int(dut.rx_count_a.value)} B={int(dut.rx_count_b.value)}")


@cocotb.test()
async def test_bit_error_detected(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await _reset(dut)
    assert await _train(dut), "did not train"

    # let payload flow cleanly for a bit
    for _ in range(200):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
    assert int(dut.code_err_b.value) == 0 and int(dut.disp_err_b.value) == 0, \
        "unexpected error before injection"

    # Inject a burst of bit flips on A->B for several symbols.
    err_seen = False
    for _ in range(40):
        dut.err_mask_a2b.value = 0x155     # flip multiple bits
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        if int(dut.code_err_b.value) or int(dut.disp_err_b.value):
            err_seen = True
    dut.err_mask_a2b.value = 0

    assert err_seen, "bit errors on the wire were not detected by the decoder"
    dut._log.info("bit-error injection detected by receiver 8b/10b decoder")


RCVR_LOCK, RCVR_CFG, RCVR_SPEED, L0 = 5, 6, 7, 4


@cocotb.test()
async def test_fault_triggers_recovery(dut):
    """A sustained error burst in L0 drives the LTSSM into Recovery; once the
    errors stop, the link retrains back to L0."""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await _reset(dut)
    assert await _train(dut), "did not train"

    # both stable in L0
    for _ in range(100):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
    assert int(dut.state_b.value) == L0, "B not in L0 before fault"

    # inject a sustained error burst on A->B
    saw_recovery = False
    for _ in range(80):
        dut.err_mask_a2b.value = 0x2AA
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        if int(dut.state_b.value) in (RCVR_LOCK, RCVR_CFG, RCVR_SPEED):
            saw_recovery = True
            break
    dut.err_mask_a2b.value = 0
    assert saw_recovery, "sustained errors did not drive B into Recovery"
    dut._log.info("fault drove B into Recovery; waiting for retrain...")

    # errors stopped -> link retrains back to L0
    relinked = False
    for _ in range(CYCLE_BUDGET):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        if int(dut.up_a.value) and int(dut.up_b.value):
            relinked = True
            break
    assert relinked, "link did not retrain to L0 after the fault"
    dut._log.info("link retrained to L0 after fault recovery")
