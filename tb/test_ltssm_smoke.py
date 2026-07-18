"""
LTSSM tests: two link_trainers wired back-to-back train to L0 (with Link/Lane
negotiation), then perform the Gen2 speed change (2.5 -> 5.0 GT/s) via Recovery.

DUT = link_pair. State encoding matches ltssm.sv:
    0 DETECT  1 POLLING  2 CONFIG_LW  3 CONFIG_CMP  4 L0
    5 RCVR_LOCK  6 RCVR_CFG  7 RCVR_SPEED  8 LOOPBACK
Node A is downstream (assigns Link=1/Lane=0); node B is upstream (adopts them).
"""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

CLK_PERIOD_NS = 10
DETECT, POLLING, CONFIG_LW, CONFIG_CMP, L0 = 0, 1, 2, 3, 4
RCVR_LOCK, RCVR_CFG, RCVR_SPEED, LOOPBACK = 5, 6, 7, 8
CYCLE_BUDGET = 5000


async def _reset(dut):
    dut.sc_req_a.value = 0
    dut.lb_req_b.value = 0
    dut.rst_n.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


async def _wait_both_l0(dut, budget=CYCLE_BUDGET):
    seen_a, seen_b = set(), set()
    for cyc in range(budget):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        seen_a.add(int(dut.state_a.value))
        seen_b.add(int(dut.state_b.value))
        if int(dut.up_a.value) == 1 and int(dut.up_b.value) == 1:
            return cyc, seen_a, seen_b
    return None, seen_a, seen_b


@cocotb.test()
async def test_train_and_negotiate(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await _reset(dut)

    reached, seen_a, seen_b = await _wait_both_l0(dut)
    assert reached is not None, (
        f"link did not reach L0; state_a={int(dut.state_a.value)} "
        f"state_b={int(dut.state_b.value)}"
    )
    dut._log.info(f"both reached L0 at cycle {reached}")

    for who, seen in (("A", seen_a), ("B", seen_b)):
        assert {DETECT, POLLING, CONFIG_LW, CONFIG_CMP, L0} <= seen, \
            f"{who} skipped states: visited {sorted(seen)}"

    # Link/Lane numbers negotiated: downstream assigned 1/0, upstream adopted.
    assert int(dut.link_a.value) == 1 and int(dut.lane_a.value) == 0, \
        f"A numbers wrong: link={int(dut.link_a.value)} lane={int(dut.lane_a.value)}"
    assert int(dut.link_b.value) == 1 and int(dut.lane_b.value) == 0, \
        f"B did not adopt numbers: link={int(dut.link_b.value)} lane={int(dut.lane_b.value)}"

    for _ in range(200):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        assert int(dut.up_a.value) == 1 and int(dut.up_b.value) == 1, "dropped L0"
    assert int(dut.rate_a.value) == 0 and int(dut.rate_b.value) == 0


@cocotb.test()
async def test_speed_change(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await _reset(dut)

    reached, _, _ = await _wait_both_l0(dut)
    assert reached is not None, "did not reach initial L0"
    assert int(dut.rate_a.value) == 0 and int(dut.rate_b.value) == 0

    dut.sc_req_a.value = 1
    await RisingEdge(dut.clk)
    dut.sc_req_a.value = 0

    saw_rcv_a = saw_rcv_b = saw_speed = False
    reached_5g = None
    for cyc in range(CYCLE_BUDGET):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        sa, sb = int(dut.state_a.value), int(dut.state_b.value)
        if sa in (RCVR_LOCK, RCVR_CFG, RCVR_SPEED): saw_rcv_a = True
        if sb in (RCVR_LOCK, RCVR_CFG, RCVR_SPEED): saw_rcv_b = True
        if RCVR_SPEED in (sa, sb): saw_speed = True
        if (int(dut.up_a.value) and int(dut.up_b.value)
                and int(dut.rate_a.value) and int(dut.rate_b.value)):
            reached_5g = cyc
            break

    assert saw_rcv_a and saw_rcv_b, "a side never entered Recovery"
    assert saw_speed, "never entered RCVR_SPEED"
    assert reached_5g is not None, "did not reach L0 at 5.0 GT/s"
    dut._log.info(f"reached L0 at 5.0 GT/s at cycle {reached_5g}")

    # Link/Lane numbers preserved across the speed change.
    assert int(dut.link_a.value) == 1 and int(dut.link_b.value) == 1
    for _ in range(200):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        assert int(dut.up_a.value) and int(dut.up_b.value), "dropped L0"
        assert int(dut.rate_a.value) and int(dut.rate_b.value), "rate fell back"
