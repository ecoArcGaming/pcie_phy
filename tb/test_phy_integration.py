"""
Phase 4 integration test: two phy_tops (full digital datapath -- ordered sets +
scrambler + 8b/10b) connected back-to-back must train to L0, negotiate Link/Lane
numbers, and perform the Gen2 speed change, all with zero decoder errors (which
proves the 8b/10b + scrambler chain is bit-exact end to end).

DUT = phy_link. State encoding matches ltssm.sv:
    0 DETECT 1 POLLING 2 CONFIG_LW 3 CONFIG_CMP 4 L0
    5 RCVR_LOCK 6 RCVR_CFG 7 RCVR_SPEED 8 LOOPBACK
"""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

CLK_PERIOD_NS = 10
DETECT, POLLING, CONFIG_LW, CONFIG_CMP, L0 = 0, 1, 2, 3, 4
RCVR_LOCK, RCVR_CFG, RCVR_SPEED = 5, 6, 7
CYCLE_BUDGET = 12000


async def _reset(dut):
    dut.sc_req_a.value = 0
    dut.lb_req_b.value = 0
    dut.rst_n.value = 0
    for _ in range(4):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


async def _step_check_clean(dut):
    """Advance one cycle and assert neither side reports a decoder error."""
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    assert int(dut.err_a.value) == 0, "node A decoder error (code/disp)"
    assert int(dut.err_b.value) == 0, "node B decoder error (code/disp)"


@cocotb.test()
async def test_train_through_datapath(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await _reset(dut)

    seen_a, seen_b = set(), set()
    reached = None
    for cyc in range(CYCLE_BUDGET):
        await _step_check_clean(dut)
        seen_a.add(int(dut.state_a.value))
        seen_b.add(int(dut.state_b.value))
        if int(dut.up_a.value) and int(dut.up_b.value):
            reached = cyc
            break
    assert reached is not None, (
        f"did not reach L0; state_a={int(dut.state_a.value)} "
        f"state_b={int(dut.state_b.value)}"
    )
    dut._log.info(f"trained to L0 through full datapath at cycle {reached}")

    for who, seen in (("A", seen_a), ("B", seen_b)):
        assert {DETECT, POLLING, CONFIG_LW, CONFIG_CMP, L0} <= seen, \
            f"{who} skipped states: {sorted(seen)}"
    assert int(dut.link_a.value) == 1 and int(dut.lane_a.value) == 0
    assert int(dut.link_b.value) == 1 and int(dut.lane_b.value) == 0
    assert int(dut.rate_a.value) == 0 and int(dut.rate_b.value) == 0

    for _ in range(200):
        await _step_check_clean(dut)
        assert int(dut.up_a.value) and int(dut.up_b.value), "dropped L0"


@cocotb.test()
async def test_speed_change_through_datapath(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await _reset(dut)

    reached = None
    for _ in range(CYCLE_BUDGET):
        await _step_check_clean(dut)
        if int(dut.up_a.value) and int(dut.up_b.value):
            reached = True
            break
    assert reached, "did not reach initial L0"

    dut.sc_req_a.value = 1
    await RisingEdge(dut.clk)
    dut.sc_req_a.value = 0

    saw_speed = False
    reached_5g = None
    for cyc in range(CYCLE_BUDGET):
        await _step_check_clean(dut)
        if RCVR_SPEED in (int(dut.state_a.value), int(dut.state_b.value)):
            saw_speed = True
        if (int(dut.up_a.value) and int(dut.up_b.value)
                and int(dut.rate_a.value) and int(dut.rate_b.value)):
            reached_5g = cyc
            break
    assert saw_speed, "never entered RCVR_SPEED"
    assert reached_5g is not None, "did not reach L0 at 5.0 GT/s"
    dut._log.info(f"speed-changed to 5.0 GT/s through full datapath at cycle {reached_5g}")

    assert int(dut.link_a.value) == 1 and int(dut.link_b.value) == 1
    for _ in range(200):
        await _step_check_clean(dut)
        assert int(dut.up_a.value) and int(dut.up_b.value), "dropped L0"
        assert int(dut.rate_a.value) and int(dut.rate_b.value), "rate fell back"
