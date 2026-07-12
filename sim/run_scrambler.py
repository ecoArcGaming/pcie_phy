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

    # 1) Standalone scrambler.
    print("Compiling scrambler...")
    runner.build(
        sources=[rtl_dir / "scrambler.sv"],
        hdl_toplevel="scrambler",
        always=True,
        build_dir=sim_dir / "sim_build_scrambler",
    )
    runner.test(hdl_toplevel="scrambler", test_module="test_scrambler")

    # 2) Loopback: scramble -> descramble identity.
    print("Compiling scrambler loopback...")
    runner.build(
        sources=[rtl_dir / "scrambler.sv",
                 rtl_dir / "descrambler.sv",
                 rtl_dir / "scrambler_loopback.sv"],
        hdl_toplevel="scrambler_loopback",
        always=True,
        build_dir=sim_dir / "sim_build_scrambler_lb",
    )
    runner.test(hdl_toplevel="scrambler_loopback",
                test_module="test_scrambler_loopback")


if __name__ == "__main__":
    print("--- scrambler test runner ---")
    main()
    print("--- done ---")
