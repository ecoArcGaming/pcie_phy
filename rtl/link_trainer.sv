`timescale 1ns / 1ps
//============================================================================
// link_trainer -- one PHY's training datapath: ordered_set_parser (RX) feeding
// the LTSSM, which drives ordered_set_gen (TX). Exposes symbol-level TX/RX so
// two link_trainers can be connected back-to-back (see link_pair.sv).
//
// In Loopback, the received symbol stream is echoed back out (registered), so a
// loopback slave returns whatever it receives.
//============================================================================
module link_trainer #(
    parameter int ROLE     = 1,     // 1 = downstream (assigns), 0 = upstream
    parameter int LINK_NUM = 1,
    parameter int LANE_NUM = 0
) (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        speed_change_req,
    input  logic        loopback_req,

    input  logic [7:0]  rx_data,
    input  logic        rx_k,
    input  logic        rx_valid,

    output logic [7:0]  tx_data,
    output logic        tx_k,
    output logic        tx_valid,

    output logic [3:0]  state,
    output logic        link_up,
    output logic        rate,
    output logic        loopback_active,
    output logic [7:0]  link_num,
    output logic [7:0]  lane_num
);
    // ---- RX parser -----------------------------------------------------
    logic       p_os_valid, p_os_error;
    logic [2:0] p_os_type;
    logic [7:0] p_rate, p_link, p_lane;
    logic       p_link_pad, p_lane_pad;

    ordered_set_parser u_parser (
        .clk, .rst_n,
        .valid_in (rx_valid), .data_in (rx_data), .k_in (rx_k),
        .os_valid (p_os_valid), .os_error (p_os_error), .os_type (p_os_type),
        .ts_link (p_link), .ts_lane (p_lane), .ts_nfts (),
        .ts_rate (p_rate), .ts_train (),
        .ts_link_pad (p_link_pad), .ts_lane_pad (p_lane_pad)
    );

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
        .rx_error (1'b0),
        .tx_enable (l_tx_en), .tx_os_type (l_os_type),
        .tx_link (l_link), .tx_lane (l_lane), .tx_nfts (l_nfts),
        .tx_rate (l_rate), .tx_train (l_train),
        .tx_link_pad (l_link_pad), .tx_lane_pad (l_lane_pad),
        .state (state), .link_up (link_up), .rate (rate),
        .loopback_active (loopback_active),
        .link_num (link_num), .lane_num (lane_num)
    );

    // ---- TX generator (back-to-back) -----------------------------------
    wire        g_start = l_tx_en & ~g_busy;
    logic [7:0] g_data;
    logic       g_k, g_valid;

    ordered_set_gen u_gen (
        .clk, .rst_n,
        .start (g_start), .os_type (l_os_type),
        .link_num (l_link), .lane_num (l_lane), .n_fts (l_nfts),
        .rate_id (l_rate), .train_ctl (l_train),
        .link_pad (l_link_pad), .lane_pad (l_lane_pad),
        .data_out (g_data), .k_out (g_k), .valid_out (g_valid),
        .busy (g_busy), .done (g_done)
    );

    // ---- TX mux: normal generator vs registered loopback echo -----------
    logic [7:0] echo_data;
    logic       echo_k, echo_valid;
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            echo_data <= 8'h0; echo_k <= 1'b0; echo_valid <= 1'b0;
        end else begin
            echo_data <= rx_data; echo_k <= rx_k; echo_valid <= rx_valid;
        end
    end

    assign tx_data  = loopback_active ? echo_data  : g_data;
    assign tx_k     = loopback_active ? echo_k     : g_k;
    assign tx_valid = loopback_active ? echo_valid : g_valid;

endmodule
