import os
import sys
from pathlib import Path

from cocotb_tools.runner import get_runner

RTL = None


def _build_run(runner, sim_dir, rtl_dir, sources, top, testmod, build):
    runner.build(sources=sources, hdl_toplevel=top, includes=[rtl_dir],
                 always=True, build_dir=sim_dir / build)
    runner.test(hdl_toplevel=top, test_module=testmod)


def main():
    sim = "icarus"
    sim_dir = Path(__file__).resolve().parent
    project_root = sim_dir.parent
    tb_dir = project_root / "tb"
    rtl_dir = project_root / "rtl"

    sys.path.append(str(tb_dir))
    os.environ["PYTHONPATH"] = str(tb_dir) + os.pathsep + os.environ.get("PYTHONPATH", "")

    runner = get_runner(sim)
    core = [rtl_dir / f for f in
            ("encoder_8b10b.sv", "dec8b10b.sv", "scrambler.sv", "descrambler.sv",
             "ordered_set_gen.sv", "ordered_set_parser.sv", "ltssm.sv",
             "phy_top.sv", "mac_stub.sv")]

    print("Perf: training / throughput / latency (link_top)...")
    _build_run(runner, sim_dir, rtl_dir, core + [rtl_dir / "link_top.sv"],
               "link_top", "test_perf", "sim_build_perf")

    print("Perf: speed-change time (phy_link)...")
    _build_run(runner, sim_dir, rtl_dir, core + [rtl_dir / "phy_link.sv"],
               "phy_link", "test_perf_speed", "sim_build_perf_speed")


if __name__ == "__main__":
    print("--- perf runner ---")
    main()
    print("--- done ---")
