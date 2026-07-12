import os
import sys
from pathlib import Path

from cocotb_tools.runner import get_runner


def test_decoder_runner():
    sim = "icarus"

    sim_dir = Path(__file__).resolve().parent
    project_root = sim_dir.parent
    tb_dir = project_root / "tb"
    rtl_dir = project_root / "rtl"

    sys.path.append(str(tb_dir))
    os.environ["PYTHONPATH"] = str(tb_dir) + os.pathsep + os.environ.get("PYTHONPATH", "")

    runner = get_runner(sim)

    print("Compiling dec8b10b with Icarus Verilog...")
    runner.build(
        sources=[rtl_dir / "dec8b10b.sv"],
        hdl_toplevel="dec8b10b",
        # rtl/ on the include path so `include "dec8b10b_rom.svh" resolves at
        # compile time (avoids $readmemb runtime path quirks on Windows).
        includes=[rtl_dir],
        always=True,
        build_dir=sim_dir / "sim_build_decoder",
    )

    print("Launching cocotb simulation...")
    runner.test(
        hdl_toplevel="dec8b10b",
        test_module="test_dec8b10b",
    )


if __name__ == "__main__":
    print("--- dec8b10b test runner ---")
    test_decoder_runner()
    print("--- done ---")
