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

    print("Compiling link_top (phy + mac stub, full datapath)...")
    runner.build(
        sources=[rtl_dir / "encoder_8b10b.sv",
                 rtl_dir / "dec8b10b.sv",
                 rtl_dir / "scrambler.sv",
                 rtl_dir / "descrambler.sv",
                 rtl_dir / "ordered_set_gen.sv",
                 rtl_dir / "ordered_set_parser.sv",
                 rtl_dir / "ltssm.sv",
                 rtl_dir / "phy_top.sv",
                 rtl_dir / "mac_stub.sv",
                 rtl_dir / "link_top.sv"],
        hdl_toplevel="link_top",
        includes=[rtl_dir],
        always=True,
        build_dir=sim_dir / "sim_build_data",
    )
    runner.test(hdl_toplevel="link_top", test_module="test_data_integrity")


if __name__ == "__main__":
    print("--- data-integrity test runner ---")
    main()
    print("--- done ---")
