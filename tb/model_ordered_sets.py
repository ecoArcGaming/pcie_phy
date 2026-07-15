"""
PCIe Gen1/Gen2 ordered-set reference model.

Each ordered set is a list of (byte, k) characters (8-bit value + control flag),
in transmit order. These feed the scrambler/8b10b encoder downstream. The LTSSM
supplies the TS1/TS2 field bytes (Link#, Lane#, N_FTS, Rate ID, Training Control)
-- this model only frames them into the correct symbol positions, so no
possibly-fragile bit-field encodings are baked in here.

Special-symbol bytes (K-codes), standard PCIe assignments:
    COM = K28.5 (0xBC)   SKP = K28.0 (0x1C)   FTS = K28.1 (0x3C)
    IDL = K28.3 (0x7C)   EIE = K28.7 (0xFC)   PAD = K23.7 (0xF7)
Training-sequence identifiers (data symbols):
    TS1 ID = D10.2 (0x4A)   TS2 ID = D5.2 (0x45)

Ordered sets:
    TS1/TS2 : 16 symbols  COM, Link#, Lane#, N_FTS, RateID, TrainCtl, 10x ID
    SKP     :  4 symbols  COM + 3x SKP
    EIOS    :  4 symbols  COM + 3x IDL          (Electrical Idle OS)
    FTS     :  4 symbols  COM + 3x FTS          (Fast Training Sequence)
    EIEOS   : 16 symbols  COM + 15x EIE  <-- length pending PCIe Base 4.2.4.3
              confirmation (K28.7 gives the required low-frequency pattern).
"""

# K-code (control) bytes
COM = 0xBC   # K28.5
SKP = 0x1C   # K28.0
FTS = 0x3C   # K28.1
IDL = 0x7C   # K28.3
EIE = 0xFC   # K28.7
PAD = 0xF7   # K23.7

# Training-sequence identifier data symbols
TS1_ID = 0x4A   # D10.2
TS2_ID = 0x45   # D5.2

# os_type selector values (must match rtl/ordered_set_gen.sv)
OS_TS1   = 0
OS_TS2   = 1
OS_SKP   = 2
OS_EIOS  = 3
OS_FTS   = 4
OS_EIEOS = 5


def _ts(identifier, link=0, lane=0, n_fts=0, rate_id=0, train_ctl=0,
        link_pad=False, lane_pad=False):
    syms = [
        (COM, True),
        (PAD, True) if link_pad else (link & 0xFF, False),
        (PAD, True) if lane_pad else (lane & 0xFF, False),
        (n_fts & 0xFF, False),
        (rate_id & 0xFF, False),
        (train_ctl & 0xFF, False),
    ]
    syms += [(identifier, False)] * 10
    return syms


def ts1(**kw):
    return _ts(TS1_ID, **kw)


def ts2(**kw):
    return _ts(TS2_ID, **kw)


def skp_os():
    return [(COM, True)] + [(SKP, True)] * 3


def eios():
    return [(COM, True)] + [(IDL, True)] * 3


def fts_os():
    return [(COM, True)] + [(FTS, True)] * 3


def eieos():
    return [(COM, True)] + [(EIE, True)] * 15


def build(os_type, **kw):
    """Return the (byte, k) symbol list for the given os_type selector."""
    if os_type == OS_TS1:
        return ts1(**kw)
    if os_type == OS_TS2:
        return ts2(**kw)
    if os_type == OS_SKP:
        return skp_os()
    if os_type == OS_EIOS:
        return eios()
    if os_type == OS_FTS:
        return fts_os()
    if os_type == OS_EIEOS:
        return eieos()
    raise ValueError(f"bad os_type {os_type}")


# --- self-test -------------------------------------------------------------
def _self_test():
    # Lengths.
    assert len(ts1()) == 16 and len(ts2()) == 16
    assert len(skp_os()) == 4 and len(eios()) == 4 and len(fts_os()) == 4
    assert len(eieos()) == 16

    # Every ordered set begins with COM (control).
    for os in (ts1(), ts2(), skp_os(), eios(), fts_os(), eieos()):
        assert os[0] == (COM, True), "ordered set must start with COM"

    # TS1/TS2 identifier symbols (positions 6..15) are the right data symbol.
    t1 = ts1(link=1, lane=2, n_fts=255, rate_id=0x02, train_ctl=0x00)
    assert t1[1] == (1, False) and t1[2] == (2, False)
    assert t1[3] == (255, False) and t1[4] == (0x02, False)
    assert all(t1[i] == (TS1_ID, False) for i in range(6, 16))
    t2 = ts2()
    assert all(t2[i] == (TS2_ID, False) for i in range(6, 16))

    # PAD substitution for unconfigured Link/Lane numbers.
    tp = ts1(link_pad=True, lane_pad=True)
    assert tp[1] == (PAD, True) and tp[2] == (PAD, True)

    # Simple OS bodies use the right K-code repeated 3x.
    assert skp_os()[1:] == [(SKP, True)] * 3
    assert eios()[1:] == [(IDL, True)] * 3
    assert fts_os()[1:] == [(FTS, True)] * 3
    assert eieos()[1:] == [(EIE, True)] * 15


_self_test()


if __name__ == "__main__":
    print("ordered-set reference model self-test PASSED")
    for name, os in [("TS1", ts1(link=1, lane=0, n_fts=8, rate_id=2)),
                     ("TS2", ts2()), ("SKP", skp_os()), ("EIOS", eios()),
                     ("FTS", fts_os()), ("EIEOS", eieos())]:
        body = " ".join(f"{b:02X}{'k' if k else ''}" for b, k in os)
        print(f"  {name:5} ({len(os):2}): {body}")
