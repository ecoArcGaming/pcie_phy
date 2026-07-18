`timescale 1ns / 1ps
//============================================================================
// serial_channel -- behavioral model of the serial link between two PHYs.
//
// Carries 10-bit symbols with one cycle of "wire" delay and supports bit-error
// injection: err_mask is XORed into the symbol (per valid symbol), flipping the
// selected bit(s). Drive err_mask=0 for a clean channel; set a bit to inject a
// single-bit error, or several bits for a burst. This is the impairment hook
// for fault-injection and the Phase-5 BER sweep.
//
// (Comma alignment / ppm + elastic buffer are modeled separately; this channel
// keeps symbol framing intact and focuses on bit errors.)
//============================================================================
module serial_channel (
    input  logic        clk,
    input  logic        rst_n,
    input  logic [9:0]  tx_symbol,
    input  logic        tx_valid,
    input  logic [9:0]  err_mask,     // bits to flip in the current symbol
    output logic [9:0]  rx_symbol,
    output logic        rx_valid
);
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            rx_symbol <= 10'b0;
            rx_valid  <= 1'b0;
        end else begin
            rx_valid  <= tx_valid;
            rx_symbol <= tx_valid ? (tx_symbol ^ err_mask) : tx_symbol;
        end
    end
endmodule
