`timescale 1ns / 1ps
//============================================================================
// scrambler_loopback -- test harness: TX scrambler feeding an RX descrambler.
// data_out is data_in recovered after 2 clocks (one per stage). Used by
// test_scrambler_loopback to prove scramble->descramble identity in RTL.
//============================================================================
module scrambler_loopback (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        scramble_en,
    input  logic        valid_in,
    input  logic [7:0]  data_in,
    input  logic        k_in,
    output logic [7:0]  data_out,
    output logic        k_out,
    output logic        valid_out
);
    wire [7:0] s_data;
    wire       s_k, s_valid;

    scrambler u_tx (
        .clk, .rst_n, .scramble_en,
        .valid_in (valid_in),
        .data_in  (data_in),
        .k_in     (k_in),
        .data_out (s_data),
        .k_out    (s_k),
        .valid_out(s_valid)
    );

    descrambler u_rx (
        .clk, .rst_n, .scramble_en,
        .valid_in (s_valid),
        .data_in  (s_data),
        .k_in     (s_k),
        .data_out (data_out),
        .k_out    (k_out),
        .valid_out(valid_out)
    );
endmodule
