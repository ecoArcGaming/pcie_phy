"""
PCIe Gen1/Gen2 data scrambler reference model (PCIe Base Spec 4.2.3).

LFSR: G(X) = X^16 + X^5 + X^4 + X^3 + 1, seed 0xFFFF, advanced 8 serial shifts
per character. Output bit each shift is d15; feedback (d15) re-enters bits
0,3,4,5. The scramble byte is applied LSB-first: data bit i is XORed with the
i-th shift output, i.e. mask[i] = lfsr[15-i] taken before advancing.

Rules (per character = 8-bit value + K flag):
  * COM (K28.5, 0xBC): not scrambled; the LFSR is (re)initialized to 0xFFFF.
  * SKP (K28.0, 0x1C): not scrambled; the LFSR is NOT advanced.
  * other control (K): not scrambled; the LFSR IS advanced 8 shifts.
  * data (D):          XORed with the scramble byte; LFSR advanced 8 shifts.
  * scrambling disabled: characters pass through; LFSR is not advanced (COM
    still re-initializes it).

Scrambling is an XOR against a deterministic sequence, so it is its own
inverse: an identical unit on the receive side descrambles. This model is
self-tested on import against the published output sequence and for
scramble->descramble identity.
"""

COM = 0xBC   # K28.5
SKP = 0x1C   # K28.0
SEED = 0xFFFF


class Scrambler:
    """One direction of scrambling. Use one instance for TX (scramble) and an
    independent instance for RX (descramble); both track RD-free LFSR state
    identically, so RX recovers TX's input."""

    def __init__(self):
        self.lfsr = SEED

    def reset(self):
        self.lfsr = SEED

    def _advance(self):
        """Advance the LFSR 8 serial shifts (output d15, feedback into 0,3,4,5)."""
        s = self.lfsr
        for _ in range(8):
            fb = (s >> 15) & 1
            ns = ((s << 1) & 0xFFFF) | fb            # shift up, d0 <- fb
            ns ^= (fb << 3) | (fb << 4) | (fb << 5)  # taps X^3, X^4, X^5
            s = ns & 0xFFFF
        self.lfsr = s

    def _mask(self):
        """8-bit scramble byte from the current LFSR (mask[i] = lfsr[15-i])."""
        m = 0
        for i in range(8):
            m |= ((self.lfsr >> (15 - i)) & 1) << i
        return m

    def process(self, byte, k=False, en=True):
        """Scramble (or descramble) one character; returns the 8-bit result."""
        assert 0 <= byte <= 255
        if k and byte == COM:
            self.lfsr = SEED
            return byte
        if not en:
            return byte
        if k and byte == SKP:
            return byte
        m = self._mask()
        self._advance()
        return byte if k else (byte ^ m)


# Convenience: the exact scramble byte a fresh scrambler emits for the i-th
# consecutive data character (all-zero data). This is the published sequence.
def scramble_sequence(n):
    s = Scrambler()
    return [s.process(0x00, k=False) for _ in range(n)]


# --- self-test -------------------------------------------------------------
_GOLDEN = [0xFF, 0x17, 0xC0, 0x14, 0xB2, 0xE7, 0x02, 0x82,
           0x72, 0x6E, 0x28, 0xA6, 0xBE, 0x6D, 0xBF, 0x8D]


def _self_test():
    # Published output sequence (scramble 0x00 from seed 0xFFFF).
    assert scramble_sequence(len(_GOLDEN)) == _GOLDEN, "golden sequence mismatch"

    # scramble -> descramble identity over a mixed stream, incl. COM/SKP/K.
    import random
    rng = random.Random(0x5CA1AB1E)
    tx, rx = Scrambler(), Scrambler()
    for _ in range(5000):
        r = rng.random()
        if r < 0.02:
            byte, k = COM, True
        elif r < 0.06:
            byte, k = SKP, True
        elif r < 0.16:
            byte, k = rng.randrange(256), True     # other control
        else:
            byte, k = rng.randrange(256), False    # data
        scrambled = tx.process(byte, k)
        recovered = rx.process(scrambled, k)
        assert recovered == byte, f"identity fail on ({byte:#04x}, k={k})"
        assert tx.lfsr == rx.lfsr, "TX/RX LFSR desync"

    # COM re-initializes the LFSR regardless of prior state.
    s = Scrambler()
    s.process(0x5A, False)
    s.process(0x3C, False)
    assert s.lfsr != SEED
    s.process(COM, True)
    assert s.lfsr == SEED, "COM did not reset LFSR"

    # SKP does not advance the LFSR; a non-COM K does.
    s = Scrambler()
    before = s.lfsr
    s.process(SKP, True)
    assert s.lfsr == before, "SKP advanced the LFSR"
    s.process(0xFE, True)     # arbitrary non-COM/SKP control byte
    assert s.lfsr != before, "control char did not advance the LFSR"


_self_test()


if __name__ == "__main__":
    print("scrambler reference model self-test PASSED")
    print("  golden sequence:", [f"{b:02X}" for b in _GOLDEN[:8]], "...")
    print("  scramble->descramble identity over 5000 mixed chars")
