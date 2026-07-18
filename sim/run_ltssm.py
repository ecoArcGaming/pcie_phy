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

    core = [rtl_dir / "ordered_set_gen.sv",
            rtl_dir / "ordered_set_parser.sv",
            rtl_dir / "ltssm.sv",
            rtl_dir / "link_trainer.sv"]

    print("Compiling LTSSM link_pair...")
    runner.build(
        sources=core + [rtl_dir / "link_pair.sv"],
        hdl_toplevel="link_pair",
        always=True,
        build_dir=sim_dir / "sim_build_ltssm",
    )
    runner.test(hdl_toplevel="link_pair", test_module="test_ltssm_smoke")

    print("Compiling link_trainer for loopback...")
    runner.build(
        sources=core,
        hdl_toplevel="link_trainer",
        always=True,
        build_dir=sim_dir / "sim_build_loopback",
    )
    runner.test(hdl_toplevel="link_trainer", test_module="test_loopback")


if __name__ == "__main__":
    print("--- LTSSM smoke test runner ---")
    main()
    print("--- done ---")
