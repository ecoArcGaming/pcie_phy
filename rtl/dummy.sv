`timescale 1ns / 1ps

// A trivial module just to prove the toolchain compiles and simulates
module dummy (
    input  logic a,
    output logic b
);
    // Simple inverter
    assign b = ~a;
endmodule
