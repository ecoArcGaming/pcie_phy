`timescale 1ns / 1ps
//============================================================================
// ltssm -- PCIe Link Training and Status State Machine.
//
// States (state[3:0]):
//   0 DETECT      quiet, then advance
//   1 POLLING     TS1 (PAD link/lane); bit lock
//   2 CONFIG_LW   TS1 with Link/Lane numbers -- the downstream port assigns,
//                 the upstream port adopts and echoes them back
//   3 CONFIG_CMP  TS2 confirming the agreed numbers -> L0
//   4 L0          link up (SKP idle). Enter Recovery on a speed-change request
//                 or a received speed-change bit; enter Loopback on loopback_req
//   5 RCVR_LOCK   TS1 re-lock
//   6 RCVR_CFG    TS2; on completion -> RCVR_SPEED (if speed change) else L0
//   7 RCVR_SPEED  electrical idle while the rate switches 2.5 -> 5.0
//   8 LOOPBACK    loopback active (link_trainer echoes RX to TX)
//
// Training handshake (lock/cfg states): advance after receiving N_TRAIN good
// sets AND sending TX_AFTER sets past the first received one (send-after-receive
// avoids stalls when one partner enters a phase first).
//
// Role: ROLE=1 downstream (assigns Link=LINK_NUM, Lane=LANE_NUM); ROLE=0
// upstream (adopts the received numbers). Speed-change bit = tx_rate[7].
//============================================================================
module ltssm #(
    parameter int ROLE        = 1,    // 1 = downstream (assigns), 0 = upstream
    parameter int LINK_NUM    = 1,
    parameter int LANE_NUM    = 0,
    parameter int N_TRAIN     = 8,
    parameter int TX_AFTER    = 4,
    parameter int DETECT_TIME = 16,
    parameter int SPEED_TIME  = 16
) (
    input  logic        clk,
    input  logic        rst_n,

    // from ordered_set_parser
    input  logic        rx_os_valid,
    input  logic [2:0]  rx_os_type,
    input  logic [7:0]  rx_ts_rate,
    input  logic [7:0]  rx_ts_link,
    input  logic [7:0]  rx_ts_lane,
    input  logic        rx_ts_link_pad,
    input  logic        rx_ts_lane_pad,

    // from ordered_set_gen
    input  logic        tx_os_done,

    // control
    input  logic        speed_change_req,
    input  logic        loopback_req,

    // to ordered_set_gen
    output logic        tx_enable,
    output logic [2:0]  tx_os_type,
    output logic [7:0]  tx_link,
    output logic [7:0]  tx_lane,
    output logic [7:0]  tx_nfts,
    output logic [7:0]  tx_rate,
    output logic [7:0]  tx_train,
    output logic        tx_link_pad,
    output logic        tx_lane_pad,

    // status
    output logic [3:0]  state,
    output logic        link_up,
    output logic        rate,             // 0 = 2.5 GT/s, 1 = 5.0 GT/s
    output logic        loopback_active,
    output logic [7:0]  link_num,         // agreed Link number
    output logic [7:0]  lane_num          // agreed Lane number
);
    localparam logic [3:0] DETECT = 4'd0, POLLING = 4'd1, CONFIG_LW = 4'd2,
                           CONFIG_CMP = 4'd3, L0 = 4'd4, RCVR_LOCK = 4'd5,
                           RCVR_CFG = 4'd6, RCVR_SPEED = 4'd7, LOOPBACK = 4'd8;
    localparam logic [2:0] OS_TS1 = 3'd0, OS_TS2 = 3'd1, OS_SKP = 3'd2;

    logic [15:0] detect_ctr, speed_ctr;
    logic [15:0] rx_cnt, tx_after;
    logic        rx_seen;
    logic        sc_pending, changed;
    logic        assigned;                 // upstream has adopted numbers
    logic [7:0]  my_link, my_lane;

    assign link_num = my_link;
    assign lane_num = my_lane;

    wire rx_ts1  = rx_os_valid && (rx_os_type == OS_TS1);
    wire rx_ts2  = rx_os_valid && (rx_os_type == OS_TS2);
    wire rx_train = rx_ts1 || rx_ts2;
    wire rx_sc   = rx_train && rx_ts_rate[7];
    wire have_numbers = (ROLE != 0) ? 1'b1 : assigned;
    wire rx_num_match = have_numbers && !rx_ts_link_pad && !rx_ts_lane_pad
                        && (rx_ts_link == my_link) && (rx_ts_lane == my_lane);

    wire in_train = (state == POLLING) || (state == CONFIG_LW) ||
                    (state == CONFIG_CMP) || (state == RCVR_LOCK) ||
                    (state == RCVR_CFG);
    wire phase_done = (rx_cnt >= N_TRAIN[15:0]) && (tx_after >= TX_AFTER[15:0]);

    // state-specific "good receive" event that advances rx_cnt
    logic rx_count_ev;
    always_comb begin
        rx_count_ev = 1'b0;
        case (state)
            POLLING:    rx_count_ev = rx_train;
            CONFIG_LW:  rx_count_ev = rx_ts1 && rx_num_match;
            CONFIG_CMP: rx_count_ev = rx_ts2 && rx_num_match;
            RCVR_LOCK:  rx_count_ev = rx_train;
            RCVR_CFG:   rx_count_ev = rx_ts2;
            default: ;
        endcase
    end

    // ---- transmit select ----------------------------------------------
    always_comb begin
        tx_enable   = 1'b0;
        tx_os_type  = OS_TS1;
        tx_nfts     = 8'h00;
        tx_train    = 8'h00;
        tx_rate     = {sc_pending, 7'h03};   // 2.5+5.0 advertised; bit7 = speed change
        tx_link     = my_link;
        tx_lane     = my_lane;
        tx_link_pad = 1'b1;                   // default: PAD
        tx_lane_pad = 1'b1;
        case (state)
            POLLING:    begin tx_enable = 1'b1; tx_os_type = OS_TS1; end
            CONFIG_LW:  begin tx_enable = 1'b1; tx_os_type = OS_TS1;
                              tx_link_pad = ~have_numbers; tx_lane_pad = ~have_numbers; end
            CONFIG_CMP: begin tx_enable = 1'b1; tx_os_type = OS_TS2;
                              tx_link_pad = ~have_numbers; tx_lane_pad = ~have_numbers; end
            L0:         begin tx_enable = 1'b1; tx_os_type = OS_SKP; end
            RCVR_LOCK:  begin tx_enable = 1'b1; tx_os_type = OS_TS1;
                              tx_link_pad = ~have_numbers; tx_lane_pad = ~have_numbers; end
            RCVR_CFG:   begin tx_enable = 1'b1; tx_os_type = OS_TS2;
                              tx_link_pad = ~have_numbers; tx_lane_pad = ~have_numbers; end
            RCVR_SPEED: tx_enable = 1'b0;
            LOOPBACK:   tx_enable = 1'b0;     // echo handled in link_trainer
            default:    tx_enable = 1'b0;
        endcase
    end

    assign link_up         = (state == L0);
    assign loopback_active = (state == LOOPBACK);

    // ---- phase-reset (clears handshake counters on any phase change) ----
    logic phase_reset;
    always_comb begin
        phase_reset = 1'b0;
        if (loopback_req && state != LOOPBACK) phase_reset = 1'b1;
        else case (state)
            DETECT:     if (detect_ctr >= DETECT_TIME[15:0]) phase_reset = 1'b1;
            POLLING, CONFIG_LW, CONFIG_CMP, RCVR_LOCK, RCVR_CFG:
                        if (phase_done) phase_reset = 1'b1;
            L0:         if (speed_change_req || rx_sc) phase_reset = 1'b1;
            RCVR_SPEED: if (speed_ctr >= SPEED_TIME[15:0]) phase_reset = 1'b1;
            LOOPBACK:   if (!loopback_req) phase_reset = 1'b1;
            default: ;
        endcase
    end

    // ---- state machine -------------------------------------------------
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            state <= DETECT; detect_ctr <= 16'd0; speed_ctr <= 16'd0;
            rx_cnt <= 16'd0; tx_after <= 16'd0; rx_seen <= 1'b0;
            sc_pending <= 1'b0; changed <= 1'b0; rate <= 1'b0;
            assigned <= 1'b0;
            my_link <= (ROLE != 0) ? LINK_NUM[7:0] : 8'h00;
            my_lane <= (ROLE != 0) ? LANE_NUM[7:0] : 8'h00;
        end else begin
            // handshake counters
            if (in_train && rx_train)      rx_seen  <= 1'b1;
            if (rx_count_ev)               rx_cnt   <= rx_cnt + 16'd1;
            if (tx_os_done && rx_seen)     tx_after <= tx_after + 16'd1;

            // upstream adopts the downstream-assigned numbers
            if (state == CONFIG_LW && ROLE == 0 && !assigned
                && rx_ts1 && !rx_ts_link_pad && !rx_ts_lane_pad) begin
                my_link <= rx_ts_link; my_lane <= rx_ts_lane; assigned <= 1'b1;
            end

            // pick up a peer speed-change request while retraining
            if ((state == RCVR_LOCK || state == RCVR_CFG) && rx_sc) sc_pending <= 1'b1;

            if (loopback_req) begin
                state <= LOOPBACK;
            end else begin
                case (state)
                    DETECT: begin
                        detect_ctr <= detect_ctr + 16'd1;
                        if (detect_ctr >= DETECT_TIME[15:0]) state <= POLLING;
                    end
                    POLLING:    if (phase_done) state <= CONFIG_LW;
                    CONFIG_LW:  if (phase_done) state <= CONFIG_CMP;
                    CONFIG_CMP: if (phase_done) state <= L0;
                    L0: if (speed_change_req || rx_sc) begin
                            sc_pending <= 1'b1; state <= RCVR_LOCK;
                        end
                    RCVR_LOCK:  if (phase_done) state <= RCVR_CFG;
                    RCVR_CFG:   if (phase_done) begin
                                    if (sc_pending && !changed) begin
                                        state <= RCVR_SPEED; speed_ctr <= 16'd0;
                                    end else state <= L0;
                                end
                    RCVR_SPEED: begin
                        rate <= 1'b1; changed <= 1'b1; sc_pending <= 1'b0;
                        speed_ctr <= speed_ctr + 16'd1;
                        if (speed_ctr >= SPEED_TIME[15:0]) state <= RCVR_LOCK;
                    end
                    LOOPBACK: begin state <= DETECT; detect_ctr <= 16'd0; end
                    default: state <= L0;
                endcase
            end

            if (phase_reset) begin
                rx_cnt <= 16'd0; tx_after <= 16'd0; rx_seen <= 1'b0;
            end
        end
    end

endmodule
