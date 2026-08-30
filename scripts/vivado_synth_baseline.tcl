set script_dir [file dirname [file normalize [info script]]]
set repo_root [file dirname $script_dir]
set project_file [file join $repo_root fpga pcie_phy.xpr]

open_project $project_file

set_property top phy_link_serial [current_fileset]
update_compile_order -fileset sources_1

reset_run synth_1
launch_runs synth_1 -jobs 4
wait_on_run synth_1

set synth_status [get_property STATUS [get_runs synth_1]]
puts "synth_1 STATUS: $synth_status"

open_run synth_1 -name synth_1
report_utilization -file [file join $repo_root fpga synth_utilization.rpt]
report_timing_summary -file [file join $repo_root fpga synth_timing_summary.rpt]
