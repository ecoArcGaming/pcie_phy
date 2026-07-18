# PCIe Physical Layer (digital PHY) in RTL

A parameterized digital **PCIe Gen2 (5.0 GT/s) PHY** built in
SystemVerilog and verified in  simulation with
[cocotb](https://www.cocotb.org/) on [Icarus Verilog](https://steveicarus.github.io/iverilog/).
This is the *digital* PHY between the PIPE boundary and the transceiver's
parallel interface: 8b/10b, scrambling, ordered sets, elastic buffering, and the
**LTSSM** link-training state machine (Detect → Polling → Config → L0, plus
Recovery, the Gen2 speed change, and Loopback). The analog SerDes is replaced by
a behavioral serial channel.

## Architecture

```
   ┌──────────────────────────── PHY (per direction) ───────────────────────────┐
   │                                                                             │
   │   LTSSM   ── link training · link/lane negotiation · speed change ·         │
   │    │  ▲       recovery · loopback                                           │
   │    ▼  │                                                                     │
   │  ordered-set gen                    ordered-set parser                      │
   │    │  (TS1/TS2/SKP/EIOS/FTS/EIEOS)        ▲  (detect / classify / fields)   │
   │    ▼                                      │                                 │
   │  scrambler  (LFSR X^16+X^5+X^4+X^3+1)   elastic buffer  (±ppm, SKP add/del) │
   │    │                                      ▲                                 │
   │    ▼                                      │                                 │
   │  8b/10b encoder                        8b/10b decoder                       │
   │    │  TX 10-bit symbols                    ▲  RX 10-bit symbols             │
   └────┼──────────────────────────────────────┼─────────────────────────────────┘
        ▼                                       │
   ╞════════════ behavioral serial channel (ppm / jitter / bit-error) ═══════════╡
                        two PHYs connected back-to-back
```

Each block is developed against a Python model, then the RTL is checked against that model in 
cocotb. 

## Layout

```
rtl/     encoder_8b10b, dec8b10b (+ generated ROM), scrambler, descrambler,
         ordered_set_gen, ordered_set_parser, elastic_buffer,
         ltssm, link_trainer, link_pair
tb/      cocotb tests + Python golden models (model_*.py)
sim/     per-block cocotb runners (run_*.py)
scripts/ regress.py (run all suites), gen_dec_rom.py (decode ROM generator)
docs/    architecture / results (WIP)
```

## Running the tests

Requires Icarus Verilog 12, Python 3.12, and cocotb 2.x.

```bash
# everything (regenerates the decode ROM, runs all suites, one green/red result)
python scripts/regress.py

# filter by name
python scripts/regress.py ltssm encoder

# a single block directly
python sim/run_ltssm.py
```

