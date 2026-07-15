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

    print("Compiling ordered_set_parser...")
    runner.build(
        sources=[rtl_dir / "ordered_set_parser.sv"],
        hdl_toplevel="ordered_set_parser",
        always=True,
        build_dir=sim_dir / "sim_build_os_parser",
    )
    runner.test(hdl_toplevel="ordered_set_parser",
                test_module="test_ordered_set_parser")


if __name__ == "__main__":
    print("--- ordered_set_parser test runner ---")
    main()
    print("--- done ---")
