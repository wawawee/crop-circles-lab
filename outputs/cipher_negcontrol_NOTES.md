# B11 — Classical cipher negative control

Native Caesar / IC screen (`tools/ccat/cipher_negcontrol.py`). Full matthewdgreen/decipher
needs Rust `bootstrap.sh`; bare pip install leaves a broken `cli` entrypoint.

## Results
- **crabwood_disc_crop**: NO classical English cipher detected (expected for noise / bitmap / bad crop)
- **chilbolton 73×23**: NO classical English cipher detected (expected for noise / bitmap / bad crop)
- **self-test**: pass=True (Caesar-3 known-answer + noise negative + planted ASCII)

## Reading
Expected: no English cipher. Web-res Crabwood bits are near-random ASCII noise (BER≈0.5);
Chilbolton is a designed bitmap, not a classical cipher alphabet.
