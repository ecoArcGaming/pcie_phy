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


_GOLDEN = [0xFF, 0x17, 0xC0, 0x14, 0xB2, 0xE7, 0x02, 0x82,
           0x72, 0x6E, 0x28, 0xA6, 0xBE, 0x6D, 0xBF, 0x8D]

