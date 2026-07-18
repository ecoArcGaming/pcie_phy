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
        sources=[rtl_dir / "dec8b10b.sv"],
        hdl_toplevel="dec8b10b", includes=[rtl_dir], always=True,
        build_dir=sim_dir / "sim_build_ber",
    )
    runner.test(hdl_toplevel="dec8b10b", test_module="test_ber")


if __name__ == "__main__":
    print("--- BER / error-detection ---")
    main()
    print("--- done ---")
