"""
8b/10b encoding reference model (Widmer & Franaszek / PCIe Base Spec).

This is the *golden* model the RTL encoder is checked against. Its correctness
is anchored by:

  1. The canonical RD=-1 (negative) 5b/6b column (the well-established standard).
  2. The 3b/4b data table, where the balanced codes y1,y2,y5,y6 are SINGLE
     (identical for both RD) and y0,y3,y4,y7 are RD-dependent pairs. Making the
     balanced codes single is what keeps decode unambiguous: e.g. D.x.2 always
     ends '...0101' and D.x.5 always '...1010', so they never collide even when
     they share a balanced 6b sub-block.
  3. Control (K) symbols use the complement-paired 3b/4b forms (the comma etc.),
     which differ from the data table. Because there are only 12 valid K codes
     and their full 10-bit encodings are universally published, K is encoded by
     direct golden lookup -- no rule modelling, no room for transcription error.
  4. A self-test (run at import) that: reproduces all 12 K golden vectors (trivi-
     ally, since they ARE the lookup), and for every data byte x both RD checks
     structural invariants (4/5/6 ones, RD stays +/-1) AND that the full set of
     256 data + 12 control symbols has a collision-free, round-trippable decode.

Disparity convention: RD is -1 (negative) or +1 (positive); the link starts -1.

Bit/transmit order: a symbol is 'abcdei fghj', transmitted a-first. Encodings
here are 10-char strings with index 0 = a (first on the wire). As an integer
(int(s, 2)) that makes a the MSB (bit 9), matching data_out[9] in the RTL.
"""

NEG = -1
POS = +1

# --- 5b/6b: RD=-1 (negative) column, indexed by the low 5 input bits (x, EDCBA).
#     String order 'abcdei' (a first). Trusted standard column.
_5B6B_MINUS = {
    0:  "100111", 1:  "011101", 2:  "101101", 3:  "110001",
    4:  "110101", 5:  "101001", 6:  "011001", 7:  "111000",
    8:  "111001", 9:  "100101", 10: "010101", 11: "110100",
    12: "001101", 13: "101100", 14: "011100", 15: "010111",
    16: "011011", 17: "100011", 18: "010011", 19: "110010",
    20: "001011", 21: "101010", 22: "011010", 23: "111010",
    24: "110011", 25: "100110", 26: "010110", 27: "110110",
    28: "001110", 29: "101110", 30: "011110", 31: "101011",
}

# --- 3b/4b DATA table, indexed by the high 3 input bits (y, HGF), order 'fghj'.
#     Balanced codes y1,y2,y5,y6 are single (same for both RD).
_3B4B_SINGLE = {1: "1001", 2: "0101", 5: "1010", 6: "0110"}
#     RD-dependent codes (RD=-1 form; RD=+1 is the bitwise complement).
_3B4B_MINUS = {0: "1011", 3: "1100", 4: "1101", 7: "1110"}   # y=7 primary
_3B4B_MINUS_ALT7 = "0111"   # D.x.A7 alternate (RD=-1 form)


def _complement(bits: str) -> str:
    return "".join("1" if c == "0" else "0" for c in bits)


def _disparity(bits: str) -> int:
    return bits.count("1") - bits.count("0")


def _new_rd(code: str, rd: int) -> int:
    d = _disparity(code)
    return rd if d == 0 else (POS if d > 0 else NEG)


def _plus_6b(minus: str, x: int) -> str:
    """RD=+1 6-bit code: complement of the RD=-1 code, except balanced codes
    are identical in both columns -- with D.07 the single documented exception
    (it is paired 111000/000111)."""
    if _disparity(minus) != 0:          # 4 ones -> disparity +2 -> complement
        return _complement(minus)
    return _complement(minus) if x == 7 else minus


def is_valid_k(x: int, y: int) -> bool:
    """Valid control symbols: K.28.0-7 and K.{23,27,29,30}.7."""
    if x == 28:
        return True
    return x in (23, 27, 29, 30) and y == 7


# Universally-published control (K) symbol encodings: (RD=-1, RD=+1) 10-bit.
_K_GOLDEN = {
    (28, 0): ("0011110100", "1100001011"),
    (28, 1): ("0011111001", "1100000110"),
    (28, 2): ("0011110101", "1100001010"),
    (28, 3): ("0011110011", "1100001100"),
    (28, 4): ("0011110010", "1100001101"),
    (28, 5): ("0011111010", "1100000101"),
    (28, 6): ("0011110110", "1100001001"),
    (28, 7): ("0011111000", "1100000111"),
    (23, 7): ("1110101000", "0001010111"),
    (27, 7): ("1101101000", "0010010111"),
    (29, 7): ("1011101000", "0100010111"),
    (30, 7): ("0111101000", "1000010111"),
}


def encode(byte: int, k: bool, rd: int):
    """Encode one 8-bit character.

    Args:
        byte: 0..255 in {H G F E D C B A} order (bit0 = A = LSB).
        k:    True for a control (K) symbol.
        rd:   starting running disparity, NEG (-1) or POS (+1).

    Returns (out, new_rd, err): `out` is a 10-char 'abcdei fghj' string
    (index 0 = a = first on the wire); `err` True for an invalid K code.
    Invalid K codes fall back to the data encoding (with err set) so the model
    and RTL stay bit-identical.
    """
    assert rd in (NEG, POS)
    assert 0 <= byte <= 255
    x = byte & 0x1F
    y = (byte >> 5) & 0x7

    if k and is_valid_k(x, y):
        neg, pos = _K_GOLDEN[(x, y)]
        out = neg if rd == NEG else pos
        return out, _new_rd(out, rd), False

    err = bool(k)   # k set but not a valid control code

    # --- Data path ---------------------------------------------------------
    # 5b/6b sub-block.
    m6 = _5B6B_MINUS[x]
    code6 = m6 if rd == NEG else _plus_6b(m6, x)
    rd6 = _new_rd(code6, rd)

    # 3b/4b sub-block.
    if y in _3B4B_SINGLE:
        code4 = _3B4B_SINGLE[y]           # single: RD-independent
    else:
        # y in {0,3,4,7}. y=7 may take the alternate to avoid a run of 5:
        #   RD (entering 4b) negative for x in {17,18,20}, positive for {11,13,14}.
        use_alt = (y == 7) and (
            (rd6 == NEG and x in (17, 18, 20)) or
            (rd6 == POS and x in (11, 13, 14))
        )
        m4 = _3B4B_MINUS_ALT7 if use_alt else _3B4B_MINUS[y]
        code4 = m4 if rd6 == NEG else _complement(m4)
    rd4 = _new_rd(code4, rd6)

    return code6 + code4, rd4, err


# --- Decoder (for encoder round-trip checks) -------------------------------
def _build_decode_map():
    table = {}
    for k in (False, True):
        for byte in range(256):
            x, y = byte & 0x1F, (byte >> 5) & 0x7
            if k and not is_valid_k(x, y):
                continue
            for rd in (NEG, POS):
                out, _, err = encode(byte, k, rd)
                if err:
                    continue
                prev = table.get(out)
                assert prev in (None, (byte, k)), \
                    f"decode collision on {out}: {prev} vs {(byte, k)}"
                table[out] = (byte, k)
    return table


_DECODE = _build_decode_map()


def decode(out: str):
    """Return (byte, k) for a 10-char symbol, or None if not a valid code."""
    return _DECODE.get(out)


def _disp_step(d: int, rd: int):
    """Advance RD through a sub-block of disparity d. Returns (new_rd, err).
    A positive sub-block is only legal entering RD-, a negative one only
    entering RD+; otherwise it is a running-disparity error."""
    if d == 0:
        return rd, False
    if d > 0:
        return POS, (rd == POS)      # +disparity block illegal when already +
    return NEG, (rd == NEG)          # -disparity block illegal when already -


def decode_symbol(cw: str, rd: int):
    """Decode one 10-char codeword given the current running disparity.

    The data value / K flag are a pure function of the codeword (looked up in
    the verified, collision-free decode map). Running disparity is tracked
    independently for error detection: `disp_err` flags a codeword whose
    sub-block disparity is inconsistent with the incoming RD. The data value is
    still returned even under a disparity error (it does not depend on RD).

    Returns (byte, k, code_err, disp_err, new_rd).
    """
    assert rd in (NEG, POS) and len(cw) == 10
    hit = _DECODE.get(cw)
    code_err = hit is None
    byte, k = (0, False) if code_err else hit

    d6 = cw[:6].count("1") * 2 - 6
    d4 = cw[6:].count("1") * 2 - 4
    rd1, e6 = _disp_step(d6, rd)
    rd2, e4 = _disp_step(d4, rd1)
    return byte, k, code_err, (e6 or e4), rd2


# --- Self-test -------------------------------------------------------------
def _self_test():
    # Every valid K symbol round-trips both RD, with correct RD flip.
    for (x, y), (neg, pos) in _K_GOLDEN.items():
        byte = (y << 5) | x
        assert encode(byte, True, NEG)[0] == neg
        assert encode(byte, True, POS)[0] == pos
        assert decode(neg) == (byte, True) and decode(pos) == (byte, True)

    # Every data byte, both RD: structural invariants + round-trip.
    for byte in range(256):
        for rd in (NEG, POS):
            out, new_rd, err = encode(byte, False, rd)
            assert not err
            assert len(out) == 10 and set(out) <= {"0", "1"}
            assert out.count("1") in (4, 5, 6), f"D byte {byte}: {out}"
            assert new_rd in (NEG, POS)
            assert _disparity(out) in (-2, 0, 2), f"D byte {byte}: {out}"
            assert decode(out) == (byte, False), f"round-trip D byte {byte}"

    # decode_symbol value/code_err agree with the decode map over ALL 1024
    # 10-bit words (valid and invalid), independent of RD.
    for i in range(1024):
        cw = format(i, "010b")
        hit = _DECODE.get(cw)
        b, k, cerr, _, _ = decode_symbol(cw, NEG)
        assert cerr == (hit is None), f"code_err mismatch on {cw}"
        if hit is not None:
            assert (b, k) == hit, f"decode value mismatch on {cw}"

    # Full encode->decode round-trip with RD threaded through both: every
    # symbol decodes back byte-exact, with no code/disparity errors, and the
    # decoder's RD stays locked to the encoder's.
    for k in (False, True):
        rd_e = rd_d = NEG
        for byte in range(256):
            x, y = byte & 0x1F, (byte >> 5) & 0x7
            if k and not is_valid_k(x, y):
                continue
            out, rd_e, _ = encode(byte, k, rd_e)
            b, kk, cerr, derr, rd_d = decode_symbol(out, rd_d)
            assert (b, kk, cerr, derr) == (byte, k, False, False), \
                f"round-trip fail byte={byte} k={k}: {(b, kk, cerr, derr)}"
            assert rd_d == rd_e, f"RD desync byte={byte} k={k}"


_self_test()


if __name__ == "__main__":
    print("8b/10b reference model self-test PASSED")
    print(f"  {len(_K_GOLDEN)} K-symbol golden vectors (both RD)")
    print(f"  256 data codes x 2 RD: invariants + round-trip")
    print(f"  decode map: {len(_DECODE)} distinct, collision-free 10-bit symbols")
