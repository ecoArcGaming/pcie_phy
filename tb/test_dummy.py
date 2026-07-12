import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def test_dummy_inverter(dut):
    """Test that the Cocotb + Icarus toolchain is communicating"""

    dut._log.info("Starting dummy test...")

    # Drive input to 0
    dut.a.value = 0
    await Timer(10, unit="ns")

    # Check output is 1
    assert dut.b.value == 1, f"Expected 1, got {dut.b.value}"
    dut._log.info("0 -> 1 inversion passed")

    # Drive input to 1
    dut.a.value = 1
    await Timer(10, unit="ns")
    
    # Check output is 0
    assert dut.b.value == 0, f"Expected 0, got {dut.b.value}"
    dut._log.info("1 -> 0 inversion passed")
    
    dut._log.info("Toolchain verification complete!")
