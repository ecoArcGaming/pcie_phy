"""
PCIe Gen1/Gen2 ordered-set parser reference model (RX side).

Consumes a stream of decoded (byte, k) characters and recognizes ordered sets.
It is the inverse of model_ordered_sets: COM starts a set, the symbol after COM
selects the simple types, and TS1/TS2 are the 16-symbol default distinguished by
their identifier (D10.2 / D5.2) in positions 6..15.

`feed(byte, k)` returns one event per completed set, else None:
    ('good', os_type, fields)   fields = (link, lane, nfts, rate, train,
                                          link_pad, lane_pad) for TS1/TS2, else None
    ('error',)                  a malformed set, or a set aborted by an early COM

COM always (re)synchronizes: a COM seen mid-set aborts it (-> 'error') and starts
a new one, mirroring how the comma symbol re-establishes alignment on the wire.
"""
from model_ordered_sets import (
    COM, SKP, FTS, IDL, EIE, PAD, TS1_ID, TS2_ID,
    OS_TS1, OS_TS2, OS_SKP, OS_EIOS, OS_FTS, OS_EIEOS,
)

_SIMPLE = {SKP: (OS_SKP, 4), IDL: (OS_EIOS, 4),
           FTS: (OS_FTS, 4), EIE: (OS_EIEOS, 16)}
_SIMPLE_SYM = {OS_SKP: SKP, OS_EIOS: IDL, OS_FTS: FTS, OS_EIEOS: EIE}


class OSParser:
    def __init__(self):
        self.reset()

    def reset(self):
        self.collecting = False
        self.pos = 0
        self.typ = None       # OS_* or 'TS'
        self.exp_len = 0
        self.err = False
        self.id_sym = None
        self.is_ts1 = False
        self.f = dict(link=0, lane=0, nfts=0, rate=0, train=0,
                      link_pad=False, lane_pad=False)

    def _begin(self):
        self.collecting = True
        self.pos = 1
        self.typ = None
        self.exp_len = 0
        self.err = False
        self.id_sym = None
        self.is_ts1 = False
        self.f = dict(link=0, lane=0, nfts=0, rate=0, train=0,
                      link_pad=False, lane_pad=False)

    def _complete(self):
        self.collecting = False
        if self.err:
            return ('error',)
        if self.typ == 'TS':
            ot = OS_TS1 if self.is_ts1 else OS_TS2
            return ('good', ot, (self.f['link'], self.f['lane'], self.f['nfts'],
                                 self.f['rate'], self.f['train'],
                                 self.f['link_pad'], self.f['lane_pad']))
        return ('good', self.typ, None)

    def feed(self, byte, k):
        # COM always (re)starts a set.
        if k and byte == COM:
            aborted = ('error',) if self.collecting else None
            self._begin()
            return aborted
        if not self.collecting:
            return None                      # idle: ignore non-COM

        p = self.pos
        if p == 1:
            if k and byte in _SIMPLE:
                self.typ, self.exp_len = _SIMPLE[byte]
            else:                            # default: TS1/TS2
                self.typ, self.exp_len = 'TS', 16
                if k and byte == PAD:
                    self.f['link_pad'] = True
                elif not k:
                    self.f['link'] = byte
                else:
                    self.err = True          # unexpected K in Link# position
        else:
            if self.typ in _SIMPLE_SYM:
                if not (k and byte == _SIMPLE_SYM[self.typ]):
                    self.err = True
            elif self.typ == 'TS':
                if p == 2:
                    if k and byte == PAD:
                        self.f['lane_pad'] = True
                    elif not k:
                        self.f['lane'] = byte
                    else:
                        self.err = True
                elif p == 3:
                    self.f['nfts'] = byte if not k else self.f['nfts']
                    if k:
                        self.err = True
                elif p == 4:
                    self.f['rate'] = byte if not k else self.f['rate']
                    if k:
                        self.err = True
                elif p == 5:
                    self.f['train'] = byte if not k else self.f['train']
                    if k:
                        self.err = True
                elif p == 6:
                    if not k and byte == TS1_ID:
                        self.is_ts1, self.id_sym = True, TS1_ID
                    elif not k and byte == TS2_ID:
                        self.is_ts1, self.id_sym = False, TS2_ID
                    else:
                        self.err = True
                else:                        # p 7..15: identifier must repeat
                    if k or self.id_sym is None or byte != self.id_sym:
                        self.err = True

        self.pos += 1
        if self.exp_len and self.pos == self.exp_len:
            return self._complete()
        return None


def parse_stream(pairs):
    """Return the list of events produced by feeding (byte, k) pairs in order."""
    p, events = OSParser(), []
    for byte, k in pairs:
        ev = p.feed(byte, k)
        if ev is not None:
            events.append(ev)
    return events


# --- self-test -------------------------------------------------------------
def _self_test():
    import model_ordered_sets as m

    # Round-trip: each generated ordered set parses back to itself.
    assert parse_stream(m.ts1(link=1, lane=2, n_fts=8, rate_id=2, train_ctl=0x20)) \
        == [('good', OS_TS1, (1, 2, 8, 2, 0x20, False, False))]
    # When Link/Lane are PAD, the pad flags are set and the number fields stay 0.
    assert parse_stream(m.ts1(link_pad=True, lane_pad=True, n_fts=255)) \
        == [('good', OS_TS1, (0, 0, 255, 0, 0, True, True))]
    assert parse_stream(m.ts2(link=5)) \
        == [('good', OS_TS2, (5, 0, 0, 0, 0, False, False))]
    assert parse_stream(m.skp_os()) == [('good', OS_SKP, None)]
    assert parse_stream(m.eios()) == [('good', OS_EIOS, None)]
    assert parse_stream(m.fts_os()) == [('good', OS_FTS, None)]
    assert parse_stream(m.eieos()) == [('good', OS_EIEOS, None)]

    # Back-to-back sets each produce one event, in order.
    stream = m.ts1(link=3) + m.skp_os() + m.ts2() + m.eieos()
    evs = parse_stream(stream)
    assert [e[1] for e in evs] == [OS_TS1, OS_SKP, OS_TS2, OS_EIEOS]

    # Malformed: truncated SKP body (COM + SKP + wrong symbol) -> error.
    bad = [(COM, True), (SKP, True), (0x00, False), (SKP, True)]
    assert parse_stream(bad) == [('error',)]

    # A TS with an inconsistent identifier tail -> error.
    ts = list(m.ts1(link=1))
    ts[10] = (TS2_ID, False)             # one identifier symbol wrong
    assert parse_stream(ts) == [('error',)]

    # COM mid-set aborts (error) then a valid SKP parses.
    interrupted = [(COM, True), (0x11, False), (0x22, False),
                   (COM, True), (SKP, True), (SKP, True), (SKP, True)]
    assert parse_stream(interrupted) == [('error',), ('good', OS_SKP, None)]

    # Idle data (no COM) is ignored.
    assert parse_stream([(0xAA, False), (0x55, False)]) == []


_self_test()


if __name__ == "__main__":
    print("ordered-set parser reference model self-test PASSED")
