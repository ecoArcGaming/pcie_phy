`timescale 1ns / 1ps
//============================================================================
// phy_link -- two phy_tops connected back-to-back through a parallel 10-bit
// symbol channel (shared clock; the serial/ppm channel + elastic buffer are a
// later increment). Node A is downstream (Link=1/Lane=0), node B is upstream.
//
// Exposes each node's decoder error flags so the test can assert the full
// 8b/10b + scrambler datapath is bit-exact (flags stay low on a clean channel).
//============================================================================
module phy_link (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        sc_req_a,
    input  logic        lb_req_b,
    output logic [3:0]  state_a,
    output logic [3:0]  state_b,
    output logic        up_a,
    output logic        up_b,
    output logic        rate_a,
    output logic        rate_b,
    output logic [7:0]  link_a,
    output logic [7:0]  lane_a,
    output logic [7:0]  link_b,
    output logic [7:0]  lane_b,
    output logic        err_a,
    output logic        err_b
);
    logic [9:0] a2b, b2a;
    logic       a2b_v, b2a_v;
    logic       ca, da, cb, db;

    phy_top #(.ROLE(1), .LINK_NUM(1), .LANE_NUM(0)) u_a (
        .clk, .rst_n,
        .speed_change_req (sc_req_a), .loopback_req (1'b0),
        .mac_tx_data (8'h0), .mac_tx_valid (1'b0),
        .mac_rx_data (), .mac_rx_valid (),
        .rx_symbol (b2a), .rx_symbol_valid (b2a_v),
        .tx_symbol (a2b), .tx_symbol_valid (a2b_v),
        .state (state_a), .link_up (up_a), .rate (rate_a),
        .loopback_active (), .link_num (link_a), .lane_num (lane_a),
        .rx_code_err (ca), .rx_disp_err (da)
    );

    phy_top #(.ROLE(0)) u_b (
        .clk, .rst_n,
        .speed_change_req (1'b0), .loopback_req (lb_req_b),
        .mac_tx_data (8'h0), .mac_tx_valid (1'b0),
        .mac_rx_data (), .mac_rx_valid (),
        .rx_symbol (a2b), .rx_symbol_valid (a2b_v),
        .tx_symbol (b2a), .tx_symbol_valid (b2a_v),
        .state (state_b), .link_up (up_b), .rate (rate_b),
        .loopback_active (), .link_num (link_b), .lane_num (lane_b),
        .rx_code_err (cb), .rx_disp_err (db)
    );

    assign err_a = ca | da;
    assign err_b = cb | db;

endmodule
