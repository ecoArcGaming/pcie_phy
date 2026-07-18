`timescale 1ns / 1ps
//============================================================================
// rx_pipe -- receive front-end across the clock-domain boundary.
//
//   rx_symbol (rx_clk, recovered) -> 8b/10b decoder -> elastic_buffer
//                                 -> decoded char (core_clk, local)
//
// The decoder runs in the recovered-clock domain; the elastic buffer bridges to
// the local core clock, absorbing the +/-ppm difference by adding/deleting SKP
// symbols. This is the in-link integration of the (Phase-2 unit-verified)
// elastic buffer with the real 8b/10b decoder.
//============================================================================
module rx_pipe (
    input  logic        rst_n,
    input  logic        rx_clk,       // recovered clock (write side)
    input  logic        core_clk,     // local clock (read side)

    input  logic [9:0]  rx_symbol,
    input  logic        rx_valid,

    output logic [7:0]  data_out,     // decoded char, core_clk domain
    output logic        k_out,
    output logic        valid_out,

    output logic        code_err,     // rx_clk domain
    output logic        disp_err,
    output logic        overflow,
    output logic        underflow,
    output logic [5:0]  fill_level,
    output logic [15:0] add_count,
    output logic [15:0] del_count
);
    wire [7:0] dec_data;
    wire       dec_k, dec_valid;

    dec8b10b u_dec (
        .clk (rx_clk), .rst_n,
        .valid_in (rx_valid), .data_in (rx_symbol),
        .data_out (dec_data), .k_out (dec_k), .valid_out (dec_valid),
        .code_err (code_err), .disp_err (disp_err)
    );

    elastic_buffer u_eb (
        .rst_n,
        .wr_clk (rx_clk), .wr_en (dec_valid), .wr_data (dec_data), .wr_k (dec_k),
        .rd_clk (core_clk),
        .rd_data (data_out), .rd_k (k_out), .rd_valid (valid_out),
        .overflow (overflow), .underflow (underflow),
        .fill_level (fill_level), .add_count (add_count), .del_count (del_count)
    );
endmodule
