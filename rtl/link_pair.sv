`timescale 1ns / 1ps
//============================================================================
// link_pair -- two link_trainers connected back-to-back at the symbol level
// (A's TX -> B's RX and vice versa), sharing one clock. Node A is the
// downstream port (assigns Link=1/Lane=0); node B is upstream (adopts them).
//
// sc_req_a  : pulse node A's speed-change request (B follows via the TS bit).
// lb_req_b  : hold node B in Loopback (B echoes A's stream back to A).
//============================================================================
module link_pair (
    input  logic       clk,
    input  logic       rst_n,
    input  logic       sc_req_a,
    input  logic       lb_req_b,
    output logic [3:0] state_a,
    output logic [3:0] state_b,
    output logic       up_a,
    output logic       up_b,
    output logic       rate_a,
    output logic       rate_b,
    output logic       lb_active_b,
    output logic [7:0] link_a,
    output logic [7:0] lane_a,
    output logic [7:0] link_b,
    output logic [7:0] lane_b
);
    logic [7:0] a2b_data, b2a_data;
    logic       a2b_k, a2b_valid, b2a_k, b2a_valid;

    link_trainer #(.ROLE(1), .LINK_NUM(1), .LANE_NUM(0)) u_a (
        .clk, .rst_n,
        .speed_change_req (sc_req_a), .loopback_req (1'b0),
        .rx_data (b2a_data), .rx_k (b2a_k), .rx_valid (b2a_valid),
        .tx_data (a2b_data), .tx_k (a2b_k), .tx_valid (a2b_valid),
        .state (state_a), .link_up (up_a), .rate (rate_a),
        .loopback_active (), .link_num (link_a), .lane_num (lane_a)
    );

    link_trainer #(.ROLE(0)) u_b (
        .clk, .rst_n,
        .speed_change_req (1'b0), .loopback_req (lb_req_b),
        .rx_data (a2b_data), .rx_k (a2b_k), .rx_valid (a2b_valid),
        .tx_data (b2a_data), .tx_k (b2a_k), .tx_valid (b2a_valid),
        .state (state_b), .link_up (up_b), .rate (rate_b),
        .loopback_active (lb_active_b), .link_num (link_b), .lane_num (lane_b)
    );

endmodule
