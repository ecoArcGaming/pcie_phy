`timescale 1ns / 1ps
//============================================================================
// phy_top -- integrated digital PHY (one direction of a link).
//
// TX:  LTSSM -> ordered_set_gen -> scrambler -> 8b/10b encoder -> tx_symbol[9:0]
// RX:  rx_symbol[9:0] -> 8b/10b decoder -> descrambler -> ordered_set_parser -> LTSSM
//
// The 10-bit symbol interface stands in for the (de)serializer/channel; two
// phy_tops connect back-to-back through it (see phy_link.sv). In Loopback the
// received symbol stream is echoed back (registered).
//
// Scrambling is held enabled in both directions here (both ends stay in sync
// via the COM-triggered LFSR reset), which exercises the scrambler on real
// ordered-set data. Spec-accurate enable-point gating comes with data payloads.
//
// rx_code_err / rx_disp_err expose the decoder's error flags -- on a clean
// channel they must stay low, which verifies the 8b/10b + scrambler chain is
// bit-exact end to end.
//============================================================================
module phy_top #(
    parameter int ROLE     = 1,
    parameter int LINK_NUM = 1,
    parameter int LANE_NUM = 0
) (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        speed_change_req,
    input  logic        loopback_req,

    // MAC payload interface (carried in L0)
    input  logic [7:0]  mac_tx_data,
    input  logic        mac_tx_valid,
    output logic [7:0]  mac_rx_data,
    output logic        mac_rx_valid,

    // 10-bit symbol interface (to/from the channel)
    input  logic [9:0]  rx_symbol,
    input  logic        rx_symbol_valid,
    output logic [9:0]  tx_symbol,
    output logic        tx_symbol_valid,

    // status
    output logic [3:0]  state,
    output logic        link_up,
    output logic        rate,
    output logic        loopback_active,
    output logic [7:0]  link_num,
    output logic [7:0]  lane_num,
    output logic        rx_code_err,
    output logic        rx_disp_err
);
    localparam logic [3:0] ST_L0 = 4'd4;   // LTSSM L0 state code

    // ---- RX chain: decode -> descramble -> parse -----------------------
    logic [7:0] d_data;   logic d_k, d_valid;
    dec8b10b u_dec (
        .clk, .rst_n,
        .valid_in (rx_symbol_valid), .data_in (rx_symbol),
        .data_out (d_data), .k_out (d_k), .valid_out (d_valid),
        .code_err (rx_code_err), .disp_err (rx_disp_err)
    );

    logic [7:0] ds_data;  logic ds_k, ds_valid;
    descrambler u_descr (
        .clk, .rst_n, .scramble_en (1'b1),
        .valid_in (d_valid), .data_in (d_data), .k_in (d_k),
        .data_out (ds_data), .k_out (ds_k), .valid_out (ds_valid)
    );

    logic       p_os_valid, p_os_error;
    logic [2:0] p_os_type;
    logic [7:0] p_rate, p_link, p_lane;
    logic       p_link_pad, p_lane_pad;
    ordered_set_parser u_parser (
        .clk, .rst_n,
        .valid_in (ds_valid), .data_in (ds_data), .k_in (ds_k),
        .os_valid (p_os_valid), .os_error (p_os_error), .os_type (p_os_type),
        .ts_link (p_link), .ts_lane (p_lane), .ts_nfts (),
        .ts_rate (p_rate), .ts_train (),
        .ts_link_pad (p_link_pad), .ts_lane_pad (p_lane_pad)
    );

    // In L0, descrambled data characters (not part of an ordered set) are the
    // MAC payload; ordered sets always start with COM (a K character).
    assign mac_rx_data  = ds_data;
    assign mac_rx_valid = ds_valid & ~ds_k & (state == ST_L0);

    // ---- LTSSM ---------------------------------------------------------
    logic       l_tx_en, l_link_pad, l_lane_pad;
    logic [2:0] l_os_type;
    logic [7:0] l_link, l_lane, l_nfts, l_rate, l_train;
    logic       g_busy, g_done;

    ltssm #(.ROLE(ROLE), .LINK_NUM(LINK_NUM), .LANE_NUM(LANE_NUM)) u_ltssm (
        .clk, .rst_n,
        .rx_os_valid (p_os_valid), .rx_os_type (p_os_type),
        .rx_ts_rate (p_rate), .rx_ts_link (p_link), .rx_ts_lane (p_lane),
        .rx_ts_link_pad (p_link_pad), .rx_ts_lane_pad (p_lane_pad),
        .tx_os_done (g_done),
        .speed_change_req (speed_change_req), .loopback_req (loopback_req),
        .rx_error (rx_code_err | rx_disp_err),
        .tx_enable (l_tx_en), .tx_os_type (l_os_type),
        .tx_link (l_link), .tx_lane (l_lane), .tx_nfts (l_nfts),
        .tx_rate (l_rate), .tx_train (l_train),
        .tx_link_pad (l_link_pad), .tx_lane_pad (l_lane_pad),
        .state (state), .link_up (link_up), .rate (rate),
        .loopback_active (loopback_active),
        .link_num (link_num), .lane_num (lane_num)
    );

    // ---- TX chain: generate -> scramble -> encode ----------------------
    wire        g_start = l_tx_en & ~g_busy;
    logic [7:0] g_data;  logic g_k, g_valid;
    ordered_set_gen u_gen (
        .clk, .rst_n,
        .start (g_start), .os_type (l_os_type),
        .link_num (l_link), .lane_num (l_lane), .n_fts (l_nfts),
        .rate_id (l_rate), .train_ctl (l_train),
        .link_pad (l_link_pad), .lane_pad (l_lane_pad),
        .data_out (g_data), .k_out (g_k), .valid_out (g_valid),
        .busy (g_busy), .done (g_done)
    );

    // Switch to MAC payload only after the in-flight ordered set finishes once
    // in L0 (first g_done). Truncating that last TS2 would starve a peer still
    // completing Configuration and stall its training.
    logic l0_data;
    always_ff @(posedge clk) begin
        if (!rst_n)                   l0_data <= 1'b0;
        else if (state != ST_L0)      l0_data <= 1'b0;
        else if (g_done)              l0_data <= 1'b1;
    end

    // In L0 the TX carries MAC payload (data character, or scrambled logical
    // idle 0x00 when the MAC has nothing); otherwise the ordered-set generator.
    wire        l0_tx    = l0_data & ~loopback_active;
    wire [7:0]  tx_char  = l0_tx ? (mac_tx_valid ? mac_tx_data : 8'h00) : g_data;
    wire        tx_char_k = l0_tx ? 1'b0 : g_k;
    wire        tx_char_v = l0_tx ? 1'b1 : g_valid;

    logic [7:0] s_data;  logic s_k, s_valid;
    scrambler u_scr (
        .clk, .rst_n, .scramble_en (1'b1),
        .valid_in (tx_char_v), .data_in (tx_char), .k_in (tx_char_k),
        .data_out (s_data), .k_out (s_k), .valid_out (s_valid)
    );

    logic [9:0] e_symbol;  logic e_valid;
    logic       e_code_err;
    encoder_8b10b u_enc (
        .clk, .rst_n,
        .valid_in (s_valid), .data_in (s_data), .k_in (s_k),
        .data_out (e_symbol), .valid_out (e_valid), .code_err (e_code_err)
    );

    // ---- TX mux: encoder output vs registered loopback echo ------------
    logic [9:0] rx_sym_r;  logic rx_val_r;
    always_ff @(posedge clk) begin
        if (!rst_n) begin rx_sym_r <= 10'b0; rx_val_r <= 1'b0; end
        else        begin rx_sym_r <= rx_symbol; rx_val_r <= rx_symbol_valid; end
    end

    assign tx_symbol       = loopback_active ? rx_sym_r : e_symbol;
    assign tx_symbol_valid = loopback_active ? rx_val_r : e_valid;

endmodule
