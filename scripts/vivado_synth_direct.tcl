set script_dir [file dirname [file normalize [info script]]]
set repo_root [file dirname $script_dir]
set rtl_dir [file join $repo_root rtl]
set fpga_dir [file join $repo_root fpga]
set part_name xc7k70tfbv676-1
set top_name phy_link_serial

set_param general.maxThreads 4

set old_dir [pwd]
cd $rtl_dir
read_verilog -sv [glob -nocomplain *.sv]
cd $old_dir

set xdc_file [file join $fpga_dir pcie_phy.srcs constrs_1 new constraints.xdc]
if {[file exists $xdc_file] && [file size $xdc_file] > 0} {
    read_xdc $xdc_file
}

synth_design -top $top_name -part $part_name

report_utilization -file [file join $fpga_dir synth_direct_utilization.rpt]
report_timing_summary -file [file join $fpga_dir synth_direct_timing_summary.rpt]
write_checkpoint -force [file join $fpga_dir synth_direct.dcp]
