import os
import sys
from pathlib import Path

from cocotb_tools.runner import get_runner


def main():
    sim = "icarus"
    sim_dir = Path(__file__).resolve().parent
    project_root = sim_dir.parent
    tb_dir = project_root / "tb"
    rtl_dir = project_root / "rtl"

    sys.path.append(str(tb_dir))
    os.environ["PYTHONPATH"] = str(tb_dir) + os.pathsep + os.environ.get("PYTHONPATH", "")

    runner = get_runner(sim)
    runner.build(
        sources=[rtl_dir / "dec8b10b.sv", rtl_dir / "elastic_buffer.sv",
                 rtl_dir / "rx_pipe.sv"],
        hdl_toplevel="rx_pipe", includes=[rtl_dir], always=True,
        build_dir=sim_dir / "sim_build_clktol",
    )
    runner.test(hdl_toplevel="rx_pipe", test_module="test_clk_tol")


if __name__ == "__main__":
    print("--- clock-tolerance sweep ---")
    main()
    print("--- done ---")
