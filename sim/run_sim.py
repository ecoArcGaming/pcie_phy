import os
import sys
from pathlib import Path
from cocotb_tools.runner import get_runner

def test_dummy_runner():
    # Specify the Icarus Verilog simulator instead of xsim
    sim = "icarus"
    
    # Define our absolute paths
    sim_dir = Path(__file__).resolve().parent
    project_root = sim_dir.parent
    tb_dir = project_root / "tb"
    
    # Add the testbench directory to PYTHONPATH so Cocotb can find it
    sys.path.append(str(tb_dir))
    os.environ["PYTHONPATH"] = str(tb_dir) + os.pathsep + os.environ.get("PYTHONPATH", "")

    # Initialize the Cocotb runner
    runner = get_runner(sim)

    print(f"Compiling the RTL design with {sim}...")
    runner.build(
        sources=[project_root / "rtl" / "dummy.sv"],
        hdl_toplevel="dummy",
        always=True,
        build_dir=sim_dir / "sim_build"
    )

    print("Launching the Cocotb simulation...")
    runner.test(
        hdl_toplevel="dummy",
        test_module="test_dummy"
    )

if __name__ == "__main__":
    print("--- Starting Python Runner ---")
    test_dummy_runner()
    print("--- Runner Finished ---")