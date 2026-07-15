`timescale 1ns / 1ps
//============================================================================
// elastic_buffer -- PCIe RX elastic buffer with SKP add/delete.
//
// A 32-deep dual-clock (asynchronous) FIFO that bridges the recovered-clock
// write domain (symbols from the deserializer/decoder) to the local-clock read
// domain. It absorbs the +/-ppm difference between the two clocks by adjusting
// the number of SKP symbols (K28.0) in SKP ordered sets:
//   * DELETE a SKP when the buffer is too full  (consume it, don't forward).
//   * ADD    a SKP when the buffer is too empty  (forward an extra, don't pop).
// Only SKP symbols are touched, so data is never lost or duplicated.
//
// Standard gray-code pointer synchronization is used across the two domains.
// The operating point is centred near DEPTH/2 with a narrow add/delete deadband
// so that the ~4 entries of margin consumed by CDC synchronization latency
// (each side sees the other pointer a couple of clocks stale) sit comfortably
// inside the depth -- keeping the buffer clear of both the full and empty rails.
//
// Depth is fixed at 32 (6-bit pointers) to keep the gray<->binary logic simple.
//============================================================================
module elastic_buffer (
    input  logic        rst_n,

    // write side (recovered-clock domain)
    input  logic        wr_clk,
    input  logic        wr_en,
    input  logic [7:0]  wr_data,
    input  logic        wr_k,

    // read side (local-clock domain)
    input  logic        rd_clk,
    output logic [7:0]  rd_data,
    output logic        rd_k,
    output logic        rd_valid,

    // status (sticky; add/del counters for observability)
    output logic        overflow,
    output logic        underflow,
    output logic [5:0]  fill_level,
    output logic [15:0] add_count,
    output logic [15:0] del_count
);
    localparam logic [7:0] SKP  = 8'h1C;   // K28.0
    localparam logic [5:0] INIT = 6'd16;   // centre fill before forwarding
    localparam logic [5:0] HIGH = 6'd18;   // above this -> delete a SKP
    localparam logic [5:0] LOW  = 6'd14;   // below this -> add a SKP

    logic [8:0] mem [0:31];                // {k, data[7:0]}

    // ---- write domain --------------------------------------------------
    logic [5:0] wbin, wgray;
    logic [5:0] rq1, rq2;                  // read gray, synced into wr domain
    logic       wfull;                     // REGISTERED (breaks the comb loop)

    wire        wr_do      = wr_en & ~wfull;
    wire [5:0]  wbin_nxt   = wbin + (wr_do ? 6'd1 : 6'd0);
    wire [5:0]  wgray_nxt  = wbin_nxt ^ (wbin_nxt >> 1);
    // full when next write gray equals read gray with top two bits inverted
    wire        wfull_next = (wgray_nxt == {~rq2[5:4], rq2[3:0]});

    always_ff @(posedge wr_clk) begin
        if (!rst_n) begin
            wbin <= 6'd0; wgray <= 6'd0; rq1 <= 6'd0; rq2 <= 6'd0;
            wfull <= 1'b0; overflow <= 1'b0;
        end else begin
            rq1 <= rgray; rq2 <= rq1;
            if (wr_do) mem[wbin[4:0]] <= {wr_k, wr_data};
            wbin  <= wbin_nxt;
            wgray <= wgray_nxt;
            wfull <= wfull_next;
            if (wr_en & wfull) overflow <= 1'b1;           // sticky
        end
    end

    // ---- read domain ---------------------------------------------------
    logic [5:0] rbin, rgray;
    logic [5:0] wq1, wq2;                   // write gray, synced into rd domain
    logic       started;

    // gray -> binary for the synced write pointer (6-bit)
    wire [5:0] wq2_bin;
    assign wq2_bin[5] = wq2[5];
    assign wq2_bin[4] = wq2[5] ^ wq2[4];
    assign wq2_bin[3] = wq2[5] ^ wq2[4] ^ wq2[3];
    assign wq2_bin[2] = wq2[5] ^ wq2[4] ^ wq2[3] ^ wq2[2];
    assign wq2_bin[1] = wq2[5] ^ wq2[4] ^ wq2[3] ^ wq2[2] ^ wq2[1];
    assign wq2_bin[0] = wq2[5] ^ wq2[4] ^ wq2[3] ^ wq2[2] ^ wq2[1] ^ wq2[0];

    wire [5:0] fill   = wq2_bin - rbin;     // entries available (slightly stale)
    wire       rempty = (rgray == wq2);
    wire [8:0] head   = mem[rbin[4:0]];
    wire       head_k = head[8];
    wire [7:0] head_d = head[7:0];
    wire       is_skp = head_k & (head_d == SKP);

    wire [5:0] rbin_nxt  = rbin + 6'd1;
    wire [5:0] rgray_nxt = rbin_nxt ^ (rbin_nxt >> 1);

    assign fill_level = fill;

    always_ff @(posedge rd_clk) begin
        if (!rst_n) begin
            rbin <= 6'd0; rgray <= 6'd0; wq1 <= 6'd0; wq2 <= 6'd0;
            started <= 1'b0; underflow <= 1'b0;
            rd_valid <= 1'b0; rd_data <= 8'h0; rd_k <= 1'b0;
            add_count <= 16'd0; del_count <= 16'd0;
        end else begin
            wq1 <= wgray; wq2 <= wq1;
            rd_valid <= 1'b0;

            if (!started) begin
                if (fill >= INIT) started <= 1'b1;      // centre, then forward
            end else if (rempty) begin
                underflow <= 1'b1;                       // sticky
            end else if (is_skp && fill >= HIGH) begin
                // DELETE: consume the SKP without forwarding it.
                rbin <= rbin_nxt; rgray <= rgray_nxt;
                del_count <= del_count + 16'd1;
            end else if (is_skp && fill <= LOW) begin
                // ADD: forward an extra SKP without consuming.
                rd_valid <= 1'b1; rd_data <= SKP; rd_k <= 1'b1;
                add_count <= add_count + 16'd1;
            end else begin
                // normal: forward and consume one symbol.
                rd_valid <= 1'b1; rd_data <= head_d; rd_k <= head_k;
                rbin <= rbin_nxt; rgray <= rgray_nxt;
            end
        end
    end

endmodule
