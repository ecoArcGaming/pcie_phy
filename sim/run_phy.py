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

    print("Compiling phy_link (full digital datapath)...")
    runner.build(
        sources=[rtl_dir / "encoder_8b10b.sv",
                 rtl_dir / "dec8b10b.sv",
                 rtl_dir / "scrambler.sv",
                 rtl_dir / "descrambler.sv",
                 rtl_dir / "ordered_set_gen.sv",
                 rtl_dir / "ordered_set_parser.sv",
                 rtl_dir / "ltssm.sv",
                 rtl_dir / "phy_top.sv",
                 rtl_dir / "phy_link.sv"],
        hdl_toplevel="phy_link",
        includes=[rtl_dir],          # for dec8b10b_rom.svh
        always=True,
        build_dir=sim_dir / "sim_build_phy",
    )
    runner.test(hdl_toplevel="phy_link", test_module="test_phy_integration")


if __name__ == "__main__":
    print("--- phy integration test runner ---")
    main()
    print("--- done ---")
