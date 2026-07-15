`timescale 1ns / 1ps
//============================================================================
// ordered_set_parser -- PCIe Gen1/Gen2 ordered-set detector (RX side).
//
// Consumes decoded (data_in, k_in) characters (one per clock when valid_in) and
// recognizes ordered sets. COM starts a set; the symbol after COM selects the
// simple types (SKP/EIOS/FTS/EIEOS); anything else defaults to a 16-symbol
// TS1/TS2, distinguished by its identifier (D10.2/D5.2) in positions 6..15.
//
// On completion it pulses (registered, 1 cycle):
//   os_valid : a well-formed set, with os_type and (for TS) the field outputs.
//   os_error : a malformed set, or a set aborted by an early COM.
// COM always re-synchronizes: a COM seen mid-set aborts it and starts a new one.
//
// Mirrors tb/model_os_parser.py (event-list oracle).
//============================================================================
module ordered_set_parser (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        valid_in,
    input  logic [7:0]  data_in,
    input  logic        k_in,
    output logic        os_valid,     // 1-cycle: well-formed ordered set
    output logic        os_error,     // 1-cycle: malformed / aborted
    output logic [2:0]  os_type,      // valid with os_valid
    output logic [7:0]  ts_link,
    output logic [7:0]  ts_lane,
    output logic [7:0]  ts_nfts,
    output logic [7:0]  ts_rate,
    output logic [7:0]  ts_train,
    output logic        ts_link_pad,
    output logic        ts_lane_pad
);
    // os_type selectors (match model_ordered_sets.py)
    localparam logic [2:0] OS_TS1 = 3'd0, OS_TS2 = 3'd1, OS_SKP = 3'd2,
                           OS_EIOS = 3'd3, OS_FTS = 3'd4, OS_EIEOS = 3'd5;
    // internal type tags for the collector
    localparam logic [2:0] TYP_TS = 3'd6, TYP_NONE = 3'd7;
    // K-code / identifier bytes
    localparam logic [7:0] COM = 8'hBC, SKP = 8'h1C, FTS = 8'h3C, IDL = 8'h7C,
                           EIE = 8'hFC, PAD = 8'hF7, TS1_ID = 8'h4A, TS2_ID = 8'h45;

    logic        collecting;
    logic [4:0]  pos;         // position of the symbol currently arriving
    logic [2:0]  typ;         // OS_* for simple, TYP_TS for TS, TYP_NONE idle
    logic [4:0]  exp_len;
    logic        err;
    logic [7:0]  id_sym;
    logic        is_ts1;
    logic [7:0]  link, lane, nfts, rate, train;
    logic        link_pad, lane_pad;

    // combinational temporaries (blocking use only, inside the always_ff)
    logic [2:0]  t_t;
    logic [4:0]  elen_t;
    logic        e_t;
    logic        done_t;

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            collecting <= 1'b0; pos <= 5'd0; typ <= TYP_NONE; exp_len <= 5'd0;
            err <= 1'b0; id_sym <= 8'h0; is_ts1 <= 1'b0;
            link <= 8'h0; lane <= 8'h0; nfts <= 8'h0; rate <= 8'h0; train <= 8'h0;
            link_pad <= 1'b0; lane_pad <= 1'b0;
            os_valid <= 1'b0; os_error <= 1'b0; os_type <= 3'd0;
            ts_link <= 8'h0; ts_lane <= 8'h0; ts_nfts <= 8'h0;
            ts_rate <= 8'h0; ts_train <= 8'h0; ts_link_pad <= 1'b0; ts_lane_pad <= 1'b0;
        end else begin
            os_valid <= 1'b0;                       // default: pulses
            os_error <= 1'b0;

            if (valid_in) begin
                if (k_in && data_in == COM) begin
                    if (collecting) os_error <= 1'b1;   // abort partial set
                    collecting <= 1'b1; pos <= 5'd1; typ <= TYP_NONE;
                    exp_len <= 5'd0; err <= 1'b0; id_sym <= 8'h0; is_ts1 <= 1'b0;
                    link <= 8'h0; lane <= 8'h0; nfts <= 8'h0; rate <= 8'h0;
                    train <= 8'h0; link_pad <= 1'b0; lane_pad <= 1'b0;
                end else if (collecting) begin
                    e_t    = err;
                    t_t    = typ;
                    elen_t = exp_len;

                    if (pos == 5'd1) begin
                        if      (k_in && data_in == SKP) begin t_t = OS_SKP;   elen_t = 5'd4;  end
                        else if (k_in && data_in == IDL) begin t_t = OS_EIOS;  elen_t = 5'd4;  end
                        else if (k_in && data_in == FTS) begin t_t = OS_FTS;   elen_t = 5'd4;  end
                        else if (k_in && data_in == EIE) begin t_t = OS_EIEOS; elen_t = 5'd16; end
                        else begin
                            t_t = TYP_TS; elen_t = 5'd16;
                            if      (k_in && data_in == PAD) link_pad <= 1'b1;
                            else if (!k_in)                  link     <= data_in;
                            else                             e_t = 1'b1;
                        end
                        typ <= t_t; exp_len <= elen_t;
                    end else begin
                        case (typ)
                            OS_SKP:   if (!(k_in && data_in == SKP)) e_t = 1'b1;
                            OS_EIOS:  if (!(k_in && data_in == IDL)) e_t = 1'b1;
                            OS_FTS:   if (!(k_in && data_in == FTS)) e_t = 1'b1;
                            OS_EIEOS: if (!(k_in && data_in == EIE)) e_t = 1'b1;
                            TYP_TS: begin
                                case (pos)
                                    5'd2: if      (k_in && data_in == PAD) lane_pad <= 1'b1;
                                          else if (!k_in)                  lane     <= data_in;
                                          else                             e_t = 1'b1;
                                    5'd3: if (!k_in) nfts  <= data_in; else e_t = 1'b1;
                                    5'd4: if (!k_in) rate  <= data_in; else e_t = 1'b1;
                                    5'd5: if (!k_in) train <= data_in; else e_t = 1'b1;
                                    5'd6: if      (!k_in && data_in == TS1_ID) begin is_ts1 <= 1'b1; id_sym <= TS1_ID; end
                                          else if (!k_in && data_in == TS2_ID) begin is_ts1 <= 1'b0; id_sym <= TS2_ID; end
                                          else                                 e_t = 1'b1;
                                    default: if (k_in || data_in != id_sym) e_t = 1'b1;  // pos 7..15
                                endcase
                            end
                            default: e_t = 1'b1;
                        endcase
                    end

                    err <= e_t;
                    done_t = (elen_t != 5'd0) && ((pos + 5'd1) == elen_t);
                    pos <= pos + 5'd1;

                    if (done_t) begin
                        collecting <= 1'b0;
                        if (e_t) begin
                            os_error <= 1'b1;
                        end else begin
                            os_valid <= 1'b1;
                            os_type  <= (t_t == TYP_TS) ? (is_ts1 ? OS_TS1 : OS_TS2)
                                                        : t_t;
                            ts_link <= link; ts_lane <= lane; ts_nfts <= nfts;
                            ts_rate <= rate; ts_train <= train;
                            ts_link_pad <= link_pad; ts_lane_pad <= lane_pad;
                        end
                    end
                end
            end
        end
    end

endmodule
