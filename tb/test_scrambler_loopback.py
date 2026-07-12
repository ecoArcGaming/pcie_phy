"""
scramble -> descramble identity test for rtl/scrambler_loopback.sv.

Drives a mixed character stream (data + COM + SKP + other control) into a TX
scrambler feeding an RX descrambler, and asserts every character comes back
byte-exact (2-clock pipeline latency).
"""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

from model_scrambler import COM, SKP

CLK_PERIOD_NS = 10


@cocotb.test()
async def test_scramble_descramble_identity(dut):
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    dut.scramble_en.value = 1
    dut.valid_in.value = 0
    dut.data_in.value = 0
    dut.k_in.value = 0
    dut.rst_n.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

    rng = random.Random(0x1DEA)
    chars = []
    for _ in range(3000):
        r = rng.random()
        if r < 0.03:
            chars.append((COM, True))
        elif r < 0.08:
            chars.append((SKP, True))
        elif r < 0.20:
            chars.append((rng.randrange(256), True))
        else:
            chars.append((rng.randrange(256), False))

    driven = []
    captured = []
    # Drive all chars, then a few idle cycles to flush the 2-stage pipeline;
    # collect every cycle where the recovered output is valid.
    for i in range(len(chars) + 4):
        if i < len(chars):
            byte, k = chars[i]
            dut.valid_in.value = 1
            dut.data_in.value = byte
            dut.k_in.value = 1 if k else 0
            driven.append((byte, 1 if k else 0))
        else:
            dut.valid_in.value = 0

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        if int(dut.valid_out.value) == 1:
            captured.append((int(dut.data_out.value), int(dut.k_out.value)))

    assert captured == driven, (
        f"identity mismatch: {len(captured)} out vs {len(driven)} in; "
        f"first diff at "
        f"{next((i for i,(a,b) in enumerate(zip(captured,driven)) if a!=b), 'len')}"
    )
