`timescale 1ns / 1ps
// ordered_set_gen -- PCIe Gen1/Gen2 ordered-set generator.
//
// On a `start` pulse (when idle) emits the selected ordered set as a stream of
// (data_out, k_out) characters, one per clock, with valid_out high throughout
// and a one-cycle `done` on the final symbol. The first symbol appears the
// cycle after `start`.

module ordered_set_gen (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        start,        // pulse to begin (ignored while busy)
    input  logic [2:0]  os_type,      
    input  logic [7:0]  link_num,
    input  logic [7:0]  lane_num,
    input  logic [7:0]  n_fts,
    input  logic [7:0]  rate_id,
    input  logic [7:0]  train_ctl,
    input  logic        link_pad,     // send PAD instead of link_num
    input  logic        lane_pad,     // send PAD instead of lane_num
    output logic [7:0]  data_out,
    output logic        k_out,
    output logic        valid_out,    // high while emitting
    output logic        busy,
    output logic        done          // 1-cycle pulse on the last symbol
);
    // os_type selectors (must match tb/model_ordered_sets.py)
    localparam logic [2:0] OS_TS1 = 3'd0, OS_TS2 = 3'd1, OS_SKP = 3'd2,
                           OS_EIOS = 3'd3, OS_FTS = 3'd4, OS_EIEOS = 3'd5;
    // K-code / identifier bytes
    localparam logic [7:0] COM = 8'hBC, SKP = 8'h1C, FTS = 8'h3C, IDL = 8'h7C,
                           EIE = 8'hFC, PAD = 8'hF7, TS1_ID = 8'h4A, TS2_ID = 8'h45;

    logic        active;
    logic [4:0]  idx;
    // latched request
    logic [2:0]  ost;
    logic [7:0]  link_r, lane_r, nfts_r, rate_r, train_r;
    logic        lpad_r, npad_r;

    wire [4:0] os_len = (ost == OS_TS1 || ost == OS_TS2 || ost == OS_EIEOS)
                        ? 5'd16 : 5'd4;

    // Combinational symbol at the current index of the latched ordered set.
    logic [7:0] sym_data;
    logic       sym_k;
    always_comb begin
        sym_data = 8'h00;
        sym_k    = 1'b0;
        case (ost)
            OS_TS1, OS_TS2: begin
                case (idx)
                    5'd0: begin sym_data = COM; sym_k = 1'b1; end
                    5'd1: begin
                        sym_data = lpad_r ? PAD : link_r;
                        sym_k    = lpad_r;
                    end
                    5'd2: begin
                        sym_data = npad_r ? PAD : lane_r;
                        sym_k    = npad_r;
                    end
                    5'd3: sym_data = nfts_r;
                    5'd4: sym_data = rate_r;
                    5'd5: sym_data = train_r;
                    default: sym_data = (ost == OS_TS1) ? TS1_ID : TS2_ID;
                endcase
            end
            OS_SKP:   begin sym_k = 1'b1; sym_data = (idx == 5'd0) ? COM : SKP; end
            OS_EIOS:  begin sym_k = 1'b1; sym_data = (idx == 5'd0) ? COM : IDL; end
            OS_FTS:   begin sym_k = 1'b1; sym_data = (idx == 5'd0) ? COM : FTS; end
            OS_EIEOS: begin sym_k = 1'b1; sym_data = (idx == 5'd0) ? COM : EIE; end
            default:  begin sym_data = 8'h00; sym_k = 1'b0; end
        endcase
    end

    assign busy = active;

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            active    <= 1'b0;
            idx       <= 5'd0;
            valid_out <= 1'b0;
            done      <= 1'b0;
            data_out  <= 8'h00;
            k_out     <= 1'b0;
            ost       <= 3'd0;
            link_r <= 8'h0; lane_r <= 8'h0; nfts_r <= 8'h0;
            rate_r <= 8'h0; train_r <= 8'h0; lpad_r <= 1'b0; npad_r <= 1'b0;
        end else begin
            done <= 1'b0;
            if (!active) begin
                valid_out <= 1'b0;
                if (start) begin
                    active <= 1'b1;
                    idx    <= 5'd0;
                    ost    <= os_type;
                    link_r <= link_num; lane_r <= lane_num; nfts_r <= n_fts;
                    rate_r <= rate_id;  train_r <= train_ctl;
                    lpad_r <= link_pad; npad_r <= lane_pad;
                end
            end else begin
                valid_out <= 1'b1;
                data_out  <= sym_data;
                k_out     <= sym_k;
                idx       <= idx + 5'd1;
                if (idx == os_len - 5'd1) begin
                    active <= 1'b0;
                    done   <= 1'b1;
                end
            end
        end
    end

endmodule
