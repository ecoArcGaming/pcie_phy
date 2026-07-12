`timescale 1ns / 1ps
//============================================================================
// descrambler -- receive-side PCIe scrambler. Scrambling is XOR against a
// deterministic sequence, so descrambling is structurally identical to
// scrambling; this is a thin alias of `scrambler` for RX-path readability.
//============================================================================
module descrambler (
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
    scrambler u_scrambler (.*);
endmodule
