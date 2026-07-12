`timescale 1ns / 1ps
//============================================================================
// encoder_8b10b -- 8b/10b line encoder
//
// One 8-bit character (+ K control flag) -> one 10-bit symbol, with running
// disparity (RD) tracked across characters. Registered, 1-clock latency.
//
// Bit/transmit order: data_out = {a,b,c,d,e,i,f,g,h,j}; data_out[9] = a is the
// first bit on the wire. The 5b/6b sub-block (a..i) encodes data_in[4:0]; the
// 3b/4b sub-block (f..j) encodes data_in[7:5].
//
// Control symbols use their published (comma) 3b/4b forms and are emitted from
// a direct table of the 12 valid K codes (K.28.0-7, K.{23,27,29,30}.7).
// Data uses single (RD-independent) 3b/4b codes for y in {1,2,5,6} -- which is
// what keeps decode unambiguous -- and RD-dependent codes for y in {0,3,4,7}.
//
//============================================================================
module encoder_8b10b (
    input  logic        clk,
    input  logic        rst_n,      // active-low sync reset; RD -> negative
    input  logic        valid_in,   // input character valid (RD advances here)
    input  logic [7:0]  data_in,    // {H G F E D C B A}, bit0 = A = LSB
    input  logic        k_in,       // 1 = control (K) symbol
    output logic [9:0]  data_out,   // {a,b,c,d,e,i,f,g,h,j}; [9] = a = first
    output logic        valid_out,  // registered, follows valid_in by 1 clock
    output logic        code_err    // registered; 1 = invalid control code
);

    // RD encoding: 1'b0 = negative (-1), 1'b1 = positive (+1).
    logic rd;

    wire [4:0] x = data_in[4:0];
    wire [2:0] y = data_in[7:5];

    // 5b/6b: RD=-1 (minus) code

    logic [5:0] c6m;    // {a b c d e i}, a = c6m[5]
    always_comb begin
        case (x)
            5'd0 : c6m = 6'b100111; 5'd1 : c6m = 6'b011101;
            5'd2 : c6m = 6'b101101; 5'd3 : c6m = 6'b110001;
            5'd4 : c6m = 6'b110101; 5'd5 : c6m = 6'b101001;
            5'd6 : c6m = 6'b011001; 5'd7 : c6m = 6'b111000;
            5'd8 : c6m = 6'b111001; 5'd9 : c6m = 6'b100101;
            5'd10: c6m = 6'b010101; 5'd11: c6m = 6'b110100;
            5'd12: c6m = 6'b001101; 5'd13: c6m = 6'b101100;
            5'd14: c6m = 6'b011100; 5'd15: c6m = 6'b010111;
            5'd16: c6m = 6'b011011; 5'd17: c6m = 6'b100011;
            5'd18: c6m = 6'b010011; 5'd19: c6m = 6'b110010;
            5'd20: c6m = 6'b001011; 5'd21: c6m = 6'b101010;
            5'd22: c6m = 6'b011010; 5'd23: c6m = 6'b111010;
            5'd24: c6m = 6'b110011; 5'd25: c6m = 6'b100110;
            5'd26: c6m = 6'b010110; 5'd27: c6m = 6'b110110;
            5'd28: c6m = 6'b001110; 5'd29: c6m = 6'b101110;
            5'd30: c6m = 6'b011110; 5'd31: c6m = 6'b101011;
            default: c6m = 6'b000000;
        endcase
    end


    wire [3:0] n_c6m = c6m[0] + c6m[1] + c6m[2] + c6m[3] + c6m[4] + c6m[5];
    wire [5:0] c6p = (n_c6m != 4'd3) ? ~c6m
                   : (x == 5'd7)     ? ~c6m
                   :                    c6m;

    wire [5:0] c6  = (rd == 1'b0) ? c6m : c6p;
    wire [3:0] n_c6 = c6[0] + c6[1] + c6[2] + c6[3] + c6[4] + c6[5];
    wire rd6 = (n_c6 == 4'd3) ? rd : (n_c6 > 4'd3);

    
    // 3b/4b (data path). Single codes for y in {1,2,5,6}; RD-dependent
    // (minus/complement) for y in {0,3,4,7}. y=7 may take the alternate form
    // (D.x.A7) to avoid a run of five: RD- for x in {17,18,20}, RD+ for
    // x in {11,13,14}.
    
    logic use_alt;
    always_comb begin
        use_alt = 1'b0;
        if (y == 3'd7) begin
            if      (rd6 == 1'b0 && (x==5'd17 || x==5'd18 || x==5'd20)) use_alt = 1'b1;
            else if (rd6 == 1'b1 && (x==5'd11 || x==5'd13 || x==5'd14)) use_alt = 1'b1;
        end
    end

    logic [3:0] c4;     // {f g h j}, f = c4[3]
    logic [3:0] c4m;
    always_comb begin
        c4m = 4'b0000;
        case (y)
            3'd1: c4 = 4'b1001;                            // single
            3'd2: c4 = 4'b0101;                            // single
            3'd5: c4 = 4'b1010;                            // single
            3'd6: c4 = 4'b0110;                            // single
            default: begin                                 // y in {0,3,4,7}
                case (y)
                    3'd0: c4m = 4'b1011;
                    3'd3: c4m = 4'b1100;
                    3'd4: c4m = 4'b1101;
                    3'd7: c4m = use_alt ? 4'b0111 : 4'b1110;
                    default: c4m = 4'b0000;
                endcase
                c4 = (rd6 == 1'b0) ? c4m : ~c4m;
            end
        endcase
    end

    // RD after the 4b sub-block (used for the data path).
    wire [3:0] n_c4 = c4[0] + c4[1] + c4[2] + c4[3];
    wire rd4 = (n_c4 == 4'd2) ? rd6 : (n_c4 > 4'd2);

    wire [9:0] data_word = {c6, c4};

    
    // Control (K) symbols: direct table of the 12 valid codes.
    logic        k_valid;
    logic [9:0]  k_neg, k_pos;
    always_comb begin
        k_valid = 1'b0;
        k_neg   = 10'b0;
        k_pos   = 10'b0;
        if (x == 5'd28) begin
            k_valid = 1'b1;
            case (y)
                3'd0: begin k_neg = 10'b0011110100; k_pos = 10'b1100001011; end
                3'd1: begin k_neg = 10'b0011111001; k_pos = 10'b1100000110; end
                3'd2: begin k_neg = 10'b0011110101; k_pos = 10'b1100001010; end
                3'd3: begin k_neg = 10'b0011110011; k_pos = 10'b1100001100; end
                3'd4: begin k_neg = 10'b0011110010; k_pos = 10'b1100001101; end
                3'd5: begin k_neg = 10'b0011111010; k_pos = 10'b1100000101; end
                3'd6: begin k_neg = 10'b0011110110; k_pos = 10'b1100001001; end
                3'd7: begin k_neg = 10'b0011111000; k_pos = 10'b1100000111; end
            endcase
        end else if (y == 3'd7 &&
                     (x==5'd23 || x==5'd27 || x==5'd29 || x==5'd30)) begin
            k_valid = 1'b1;
            case (x)
                5'd23: begin k_neg = 10'b1110101000; k_pos = 10'b0001010111; end
                5'd27: begin k_neg = 10'b1101101000; k_pos = 10'b0010010111; end
                5'd29: begin k_neg = 10'b1011101000; k_pos = 10'b0100010111; end
                5'd30: begin k_neg = 10'b0111101000; k_pos = 10'b1000010111; end
            endcase
        end
    end

    wire        k_ok    = k_in & k_valid;
    wire [9:0]  k_word  = (rd == 1'b0) ? k_neg : k_pos;

    // RD after a control symbol (from its 10-bit disparity).
    wire [3:0] n_kw = k_word[0] + k_word[1] + k_word[2] + k_word[3] + k_word[4]
                    + k_word[5] + k_word[6] + k_word[7] + k_word[8] + k_word[9];
    wire rdk = (n_kw == 4'd5) ? rd : (n_kw > 4'd5);

    
    // Output select. Invalid K falls back to the data encoding (with error),
    wire [9:0] out_next    = k_ok ? k_word : data_word;
    wire       rd_next     = k_ok ? rdk    : rd4;
    wire       code_err_c  = k_in & ~k_valid;

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            rd        <= 1'b0;      // start negative
            data_out  <= 10'b0;
            valid_out <= 1'b0;
            code_err  <= 1'b0;
        end else begin
            valid_out <= valid_in;
            if (valid_in) begin
                data_out <= out_next;
                code_err <= code_err_c;
                rd       <= rd_next;
            end else begin
                code_err <= 1'b0;
            end
        end
    end

endmodule
