`timescale 1ns / 1ps
//============================================================================
// link_top -- full system: two phy_tops (parallel 10-bit channel) each driven
// by a mac_stub, for the end-to-end data-integrity test. The link trains to L0,
// then both MACs stream payload through the trained datapath and scoreboard it
// byte-exact.
//============================================================================
module link_top (
    input  logic        clk,
    input  logic        rst_n,
    output logic [3:0]  state_a,
    output logic [3:0]  state_b,
    output logic        up_a,
    output logic        up_b,
    output logic [31:0] rx_count_a,
    output logic [31:0] rx_count_b,
    output logic        seq_error_a,
    output logic        seq_error_b,
    output logic        err_a,
    output logic        err_b
);
    logic [9:0] a2b, b2a;
    logic       a2b_v, b2a_v;
    logic [7:0] a_txd, a_rxd, b_txd, b_rxd;
    logic       a_txv, a_rxv, b_txv, b_rxv;
    logic       ca, da, cb, db;

    phy_top #(.ROLE(1), .LINK_NUM(1), .LANE_NUM(0)) u_a (
        .clk, .rst_n, .speed_change_req (1'b0), .loopback_req (1'b0),
        .mac_tx_data (a_txd), .mac_tx_valid (a_txv),
        .mac_rx_data (a_rxd), .mac_rx_valid (a_rxv),
        .rx_symbol (b2a), .rx_symbol_valid (b2a_v),
        .tx_symbol (a2b), .tx_symbol_valid (a2b_v),
        .state (state_a), .link_up (up_a), .rate (), .loopback_active (),
        .link_num (), .lane_num (), .rx_code_err (ca), .rx_disp_err (da)
    );
    mac_stub u_mac_a (
        .clk, .rst_n, .link_up (up_a),
        .tx_data (a_txd), .tx_valid (a_txv),
        .rx_data (a_rxd), .rx_valid (a_rxv),
        .tx_count (), .rx_count (rx_count_a), .seq_error (seq_error_a)
    );

    phy_top #(.ROLE(0)) u_b (
        .clk, .rst_n, .speed_change_req (1'b0), .loopback_req (1'b0),
        .mac_tx_data (b_txd), .mac_tx_valid (b_txv),
        .mac_rx_data (b_rxd), .mac_rx_valid (b_rxv),
        .rx_symbol (a2b), .rx_symbol_valid (a2b_v),
        .tx_symbol (b2a), .tx_symbol_valid (b2a_v),
        .state (state_b), .link_up (up_b), .rate (), .loopback_active (),
        .link_num (), .lane_num (), .rx_code_err (cb), .rx_disp_err (db)
    );
    mac_stub u_mac_b (
        .clk, .rst_n, .link_up (up_b),
        .tx_data (b_txd), .tx_valid (b_txv),
        .rx_data (b_rxd), .rx_valid (b_rxv),
        .tx_count (), .rx_count (rx_count_b), .seq_error (seq_error_b)
    );

    assign err_a = ca | da;
    assign err_b = cb | db;

endmodule
