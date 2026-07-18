`timescale 1ns / 1ps
//============================================================================
// phy_link_serial -- two phy_tops connected through behavioral serial_channels
// (one per direction), each PHY driven by a mac_stub. err_mask_* inject bit
// errors into each direction of the link.
//============================================================================
module phy_link_serial (
    input  logic        clk,
    input  logic        rst_n,
    input  logic [9:0]  err_mask_a2b,   // bit errors on A -> B
    input  logic [9:0]  err_mask_b2a,   // bit errors on B -> A
    output logic [3:0]  state_a,
    output logic [3:0]  state_b,
    output logic        up_a,
    output logic        up_b,
    output logic [31:0] rx_count_a,
    output logic [31:0] rx_count_b,
    output logic        seq_error_a,
    output logic        seq_error_b,
    output logic        code_err_a,
    output logic        disp_err_a,
    output logic        code_err_b,
    output logic        disp_err_b
);
    logic [9:0] a_tx, b_tx;      // PHY TX symbols
    logic       a_txv, b_txv;
    logic [9:0] to_b, to_a;      // channel outputs
    logic       to_b_v, to_a_v;
    logic [7:0] a_txd, a_rxd, b_txd, b_rxd;
    logic       a_txvd, a_rxvd, b_txvd, b_rxvd;

    // A -> B and B -> A serial channels
    serial_channel u_a2b (
        .clk, .rst_n, .tx_symbol (a_tx), .tx_valid (a_txv),
        .err_mask (err_mask_a2b), .rx_symbol (to_b), .rx_valid (to_b_v)
    );
    serial_channel u_b2a (
        .clk, .rst_n, .tx_symbol (b_tx), .tx_valid (b_txv),
        .err_mask (err_mask_b2a), .rx_symbol (to_a), .rx_valid (to_a_v)
    );

    phy_top #(.ROLE(1), .LINK_NUM(1), .LANE_NUM(0)) u_a (
        .clk, .rst_n, .speed_change_req (1'b0), .loopback_req (1'b0),
        .mac_tx_data (a_txd), .mac_tx_valid (a_txvd),
        .mac_rx_data (a_rxd), .mac_rx_valid (a_rxvd),
        .rx_symbol (to_a), .rx_symbol_valid (to_a_v),
        .tx_symbol (a_tx), .tx_symbol_valid (a_txv),
        .state (state_a), .link_up (up_a), .rate (), .loopback_active (),
        .link_num (), .lane_num (),
        .rx_code_err (code_err_a), .rx_disp_err (disp_err_a)
    );
    mac_stub u_mac_a (
        .clk, .rst_n, .link_up (up_a),
        .tx_data (a_txd), .tx_valid (a_txvd),
        .rx_data (a_rxd), .rx_valid (a_rxvd),
        .tx_count (), .rx_count (rx_count_a), .seq_error (seq_error_a)
    );

    phy_top #(.ROLE(0)) u_b (
        .clk, .rst_n, .speed_change_req (1'b0), .loopback_req (1'b0),
        .mac_tx_data (b_txd), .mac_tx_valid (b_txvd),
        .mac_rx_data (b_rxd), .mac_rx_valid (b_rxvd),
        .rx_symbol (to_b), .rx_symbol_valid (to_b_v),
        .tx_symbol (b_tx), .tx_symbol_valid (b_txv),
        .state (state_b), .link_up (up_b), .rate (), .loopback_active (),
        .link_num (), .lane_num (),
        .rx_code_err (code_err_b), .rx_disp_err (disp_err_b)
    );
    mac_stub u_mac_b (
        .clk, .rst_n, .link_up (up_b),
        .tx_data (b_txd), .tx_valid (b_txvd),
        .rx_data (b_rxd), .rx_valid (b_rxvd),
        .tx_count (), .rx_count (rx_count_b), .seq_error (seq_error_b)
    );

endmodule
