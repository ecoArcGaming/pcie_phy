set script_dir [file dirname [file normalize [info script]]]
set repo_root [file dirname $script_dir]
set fpga_dir [file join $repo_root fpga]

source [file join $script_dir vivado_synth_direct.tcl]

opt_design
report_timing_summary -file [file join $fpga_dir impl_post_opt_timing_summary.rpt]

place_design
report_utilization -file [file join $fpga_dir impl_post_place_utilization.rpt]
report_timing_summary -file [file join $fpga_dir impl_post_place_timing_summary.rpt]

phys_opt_design
route_design

report_route_status -file [file join $fpga_dir impl_route_status.rpt]
report_drc -file [file join $fpga_dir impl_drc.rpt]
report_utilization -file [file join $fpga_dir impl_post_route_utilization.rpt]
report_timing_summary -file [file join $fpga_dir impl_post_route_timing_summary.rpt]
write_checkpoint -force [file join $fpga_dir impl_post_route.dcp]
