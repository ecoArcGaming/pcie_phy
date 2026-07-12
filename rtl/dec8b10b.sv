`timescale 1ns / 1ps
//============================================================================
// dec8b10b -- 8b/10b line decoder (inverse of encoder_8b10b).
//
// One 10-bit symbol -> one 8-bit character (+ K flag), with running-disparity
// tracking for error detection. Registered, 1-clock latency.
//
// Bit/transmit order: data_in = {a,b,c,d,e,i,f,g,h,j}; data_in[9] = a is the
// first bit on the wire (same convention as the encoder's data_out).
//
// The data value / K flag are a pure function of the 10-bit codeword and come
// straight from a decode ROM (rtl/dec8b10b_rom.svh, generated from the golden
// reference model by scripts/gen_dec_rom.py). This sidesteps the fact that
// sub-block decode is disparity-ambiguous for control symbols (e.g. K.28.2 and
// K.28.5 share a 3b/4b sub-block).
//
// Running disparity is tracked separately, only to detect errors:
//   code_err : the codeword is not a legal 8b/10b symbol.
//   disp_err : a sub-block's disparity is inconsistent with the incoming RD
//              (a +disparity block seen at RD+, or -disparity at RD-). The
//              decoded data is still produced (it does not depend on RD).
//============================================================================
module dec8b10b (
    input  logic        clk,
    input  logic        rst_n,      // active-low sync reset; RD -> negative
    input  logic        valid_in,   // input symbol valid (RD advances here)
    input  logic [9:0]  data_in,    // {a,b,c,d,e,i,f,g,h,j}; [9] = a = first
    output logic [7:0]  data_out,   // decoded character {H G F E D C B A}
    output logic        k_out,      // 1 = control (K) symbol
    output logic        valid_out,  // registered, follows valid_in by 1 clock
    output logic        code_err,   // registered; 1 = illegal codeword
    output logic        disp_err    // registered; 1 = running-disparity error
);

    // Decode ROM: {valid, k, data[7:0]} indexed by the 10-bit codeword.
    logic [9:0] rom [0:1023];
    initial begin
        `include "dec8b10b_rom.svh"
    end

    wire [9:0] entry    = rom[data_in];
    wire       e_valid  = entry[9];
    wire       e_k      = entry[8];
    wire [7:0] e_data   = entry[7:0];

    // RD encoding: 1'b0 = negative (-1), 1'b1 = positive (+1).
    logic rd;

    wire [5:0] s6 = data_in[9:4];   // 5b/6b sub-block {a b c d e i}
    wire [3:0] s4 = data_in[3:0];   // 3b/4b sub-block {f g h j}

    function automatic [3:0] cnt6(input logic [5:0] v);
        cnt6 = v[0] + v[1] + v[2] + v[3] + v[4] + v[5];
    endfunction
    function automatic [3:0] cnt4(input logic [3:0] v);
        cnt4 = v[0] + v[1] + v[2] + v[3];
    endfunction

    // Running-disparity walk through the two sub-blocks.
    logic rd1, rd2, e6, e4;
    always_comb begin
        // 6b: 3 ones = balanced, >3 = +2 (legal only at RD-), <3 = -2 (RD+).
        if (cnt6(s6) == 4'd3)      begin rd1 = rd;   e6 = 1'b0;        end
        else if (cnt6(s6) > 4'd3)  begin rd1 = 1'b1; e6 = (rd == 1'b1); end
        else                       begin rd1 = 1'b0; e6 = (rd == 1'b0); end
        // 4b: 2 ones = balanced, >2 = +2, <2 = -2.
        if (cnt4(s4) == 4'd2)      begin rd2 = rd1;  e4 = 1'b0;         end
        else if (cnt4(s4) > 4'd2)  begin rd2 = 1'b1; e4 = (rd1 == 1'b1); end
        else                       begin rd2 = 1'b0; e4 = (rd1 == 1'b0); end
    end

    wire code_err_c = ~e_valid;
    wire disp_err_c = e6 | e4;

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            rd        <= 1'b0;      // start negative
            data_out  <= 8'b0;
            k_out     <= 1'b0;
            valid_out <= 1'b0;
            code_err  <= 1'b0;
            disp_err  <= 1'b0;
        end else begin
            valid_out <= valid_in;
            if (valid_in) begin
                data_out <= e_data;
                k_out    <= e_k;
                code_err <= code_err_c;
                disp_err <= disp_err_c;
                rd       <= rd2;
            end else begin
                code_err <= 1'b0;
                disp_err <= 1'b0;
            end
        end
    end

endmodule
