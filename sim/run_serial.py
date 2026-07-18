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

    print("Compiling phy_link_serial (serial channel + bit errors)...")
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
                 rtl_dir / "serial_channel.sv",
                 rtl_dir / "phy_link_serial.sv"],
        hdl_toplevel="phy_link_serial",
        includes=[rtl_dir],
        always=True,
        build_dir=sim_dir / "sim_build_serial",
    )
    runner.test(hdl_toplevel="phy_link_serial", test_module="test_serial")


if __name__ == "__main__":
    print("--- serial channel test runner ---")
    main()
    print("--- done ---")
