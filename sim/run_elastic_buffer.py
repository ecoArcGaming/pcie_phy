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

    print("Compiling elastic_buffer...")
    runner.build(
        sources=[rtl_dir / "elastic_buffer.sv"],
        hdl_toplevel="elastic_buffer",
        always=True,
        build_dir=sim_dir / "sim_build_ebuf",
    )
    runner.test(hdl_toplevel="elastic_buffer", test_module="test_elastic_buffer")


if __name__ == "__main__":
    print("--- elastic_buffer test runner ---")
    main()
    print("--- done ---")
