`timescale 1ns / 1ps
//============================================================================
// mac_stub -- thin MAC traffic generator + data-integrity scoreboard.
//
// TX: once link_up, drive an incrementing byte counter as payload (one byte
//     per clock). This is the "data mover" for a PHY-scope project -- it
//     exercises the trained datapath without a DLL/TL.
// RX: check the received payload is byte-exact. Because scrambling recovers the
//     exact bytes on a clean channel, consecutive received bytes must differ by
//     +1 (mod 256). A settling window (SKIP bytes) is ignored first, to skip
//     the L0-entry boundary (in-flight ordered-set tail + pipeline latency).
//
// seq_error latches high on any non-consecutive received byte -> data corruption.
//============================================================================
module mac_stub #(
    parameter int SKIP = 64        // received bytes to ignore after link-up
) (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        link_up,

    // payload to the PHY
    output logic [7:0]  tx_data,
    output logic        tx_valid,

    // payload from the PHY
    input  logic [7:0]  rx_data,
    input  logic        rx_valid,

    // status
    output logic [31:0] tx_count,
    output logic [31:0] rx_count,
    output logic        seq_error
);
    logic [7:0]  txc;
    logic [7:0]  expected;
    logic        have_first;
    logic [31:0] skipped;

    assign tx_data  = txc;
    assign tx_valid = link_up;

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            txc <= 8'd0; tx_count <= 32'd0; rx_count <= 32'd0;
            seq_error <= 1'b0; expected <= 8'd0; have_first <= 1'b0;
            skipped <= 32'd0;
        end else begin
            if (link_up) begin
                txc      <= txc + 8'd1;
                tx_count <= tx_count + 32'd1;
            end
            if (rx_valid) begin
                if (skipped < SKIP[31:0]) begin
                    skipped <= skipped + 32'd1;    // settle past the boundary
                end else begin
                    rx_count <= rx_count + 32'd1;
                    if (have_first && rx_data != expected) seq_error <= 1'b1;
                    expected   <= rx_data + 8'd1;
                    have_first <= 1'b1;
                end
            end
        end
    end

endmodule
