import os
import sys
from pathlib import Path

from cocotb_tools.runner import get_runner


def test_encoder_runner():
    sim = "icarus"

    sim_dir = Path(__file__).resolve().parent
    project_root = sim_dir.parent
    tb_dir = project_root / "tb"

    sys.path.append(str(tb_dir))
    os.environ["PYTHONPATH"] = str(tb_dir) + os.pathsep + os.environ.get("PYTHONPATH", "")

    runner = get_runner(sim)

    print("Compiling encoder_8b10b with Icarus Verilog...")
    runner.build(
        sources=[project_root / "rtl" / "encoder_8b10b.sv"],
        hdl_toplevel="encoder_8b10b",
        always=True,
        build_dir=sim_dir / "sim_build_encoder",
    )

    print("Launching cocotb simulation...")
    runner.test(
        hdl_toplevel="encoder_8b10b",
        test_module="test_encoder_8b10b",
    )


if __name__ == "__main__":
    print("--- encoder_8b10b test runner ---")
    test_encoder_runner()
    print("--- done ---")
