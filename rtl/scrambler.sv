`timescale 1ns / 1ps

// scrambler -- PCIe Gen1/Gen2 data scrambler (PCIe Base Spec 4.2.3).
//
// 16-bit LFSR, G(X) = X^16 + X^5 + X^4 + X^3 + 1, seed 0xFFFF, advanced 8
// serial shifts per character. Scrambling is XOR against a deterministic
// sequence, so the SAME module descrambles on the receive side (see
// descrambler.sv). Registered, 1-clock latency.
//
// Per-character rules (character = 8-bit value + K flag):
//   COM (K28.5, 0xBC): pass through; LFSR (re)initialized to 0xFFFF.
//   SKP (K28.0, 0x1C): pass through; LFSR NOT advanced.
//   other control (K): pass through; LFSR advanced 8 shifts.
//   data (D):          XOR with scramble byte; LFSR advanced 8 shifts.
//   scramble_en = 0:   pass through; LFSR held (COM still re-initializes it).
//
// The scramble byte is applied LSB-first: data_in[i] XORs lfsr[15-i]. The
// parallel 8-shift equations below are generated/verified against the
// published output sequence (scripts/scr_gen -> golden FF,17,C0,14,...).

module scrambler (
    input  logic        clk,
    input  logic        rst_n,       // active-low sync reset; LFSR -> 0xFFFF
    input  logic        scramble_en, // 0 = bypass (passthrough, LFSR held)
    input  logic        valid_in,    // input character valid
    input  logic [7:0]  data_in,     // {H G F E D C B A}
    input  logic        k_in,        // 1 = control (K) symbol
    output logic [7:0]  data_out,    // (de)scrambled character
    output logic        k_out,       // registered K flag (passthrough)
    output logic        valid_out    // registered, follows valid_in by 1 clock
);
    localparam logic [15:0] SEED = 16'hFFFF;
    localparam logic [7:0]  COM  = 8'hBC;   // K28.5
    localparam logic [7:0]  SKP  = 8'h1C;   // K28.0

    logic [15:0] lfsr;

    // Scramble byte (LSB-first: mask[i] = lfsr[15-i]).
    wire [7:0] mask = {lfsr[8], lfsr[9], lfsr[10], lfsr[11],
                       lfsr[12], lfsr[13], lfsr[14], lfsr[15]};

    // LFSR state after advancing 8 serial shifts (parallel form).
    wire [15:0] nxt;
    assign nxt[0]  = lfsr[8];
    assign nxt[1]  = lfsr[9];
    assign nxt[2]  = lfsr[10];
    assign nxt[3]  = lfsr[8]  ^ lfsr[11];
    assign nxt[4]  = lfsr[8]  ^ lfsr[9]  ^ lfsr[12];
    assign nxt[5]  = lfsr[8]  ^ lfsr[9]  ^ lfsr[10] ^ lfsr[13];
    assign nxt[6]  = lfsr[9]  ^ lfsr[10] ^ lfsr[11] ^ lfsr[14];
    assign nxt[7]  = lfsr[10] ^ lfsr[11] ^ lfsr[12] ^ lfsr[15];
    assign nxt[8]  = lfsr[0]  ^ lfsr[11] ^ lfsr[12] ^ lfsr[13];
    assign nxt[9]  = lfsr[1]  ^ lfsr[12] ^ lfsr[13] ^ lfsr[14];
    assign nxt[10] = lfsr[2]  ^ lfsr[13] ^ lfsr[14] ^ lfsr[15];
    assign nxt[11] = lfsr[3]  ^ lfsr[14] ^ lfsr[15];
    assign nxt[12] = lfsr[4]  ^ lfsr[15];
    assign nxt[13] = lfsr[5];
    assign nxt[14] = lfsr[6];
    assign nxt[15] = lfsr[7];

    wire is_com = k_in & (data_in == COM);
    wire is_skp = k_in & (data_in == SKP);

    // Output: only data characters are scrambled (and only when enabled).
    wire [7:0] out_data = (scramble_en & ~k_in) ? (data_in ^ mask) : data_in;

    // Next LFSR: COM resets; bypass/SKP hold; everything else advances.
    wire [15:0] lfsr_next = is_com               ? SEED
                          : (~scramble_en)       ? lfsr
                          : is_skp               ? lfsr
                          :                        nxt;

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            lfsr      <= SEED;
            data_out  <= 8'b0;
            k_out     <= 1'b0;
            valid_out <= 1'b0;
        end else begin
            valid_out <= valid_in;
            if (valid_in) begin
                data_out <= out_data;
                k_out    <= k_in;
                lfsr     <= lfsr_next;
            end
        end
    end

endmodule
