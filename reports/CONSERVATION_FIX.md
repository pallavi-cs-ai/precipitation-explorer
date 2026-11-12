# Corrected cumulative reconstruction (v2)

The original audit found that clipping each negative interval independently increased the 72-hour sum at some points. Processing v2 corrects this before interval conversion.

For source cumulative amounts C[1]…C[24], use B[i] = min(C[i], …, C[24]), anchored to B[24] = C[24], and B[0] = 0. Then interval P[i] = B[i] − B[i−1]. B is nondecreasing, so intervals are nonnegative and telescope to the final source accumulation. Already-monotonic series are unchanged. Calculations and storage use float64 to retain source precision.

Each downward correction is checked against the sum of the packing-error bounds for the adjusted field and the later field supplying the lower value. Larger inconsistencies, nonfinite input and negative source accumulations are rejected. This is a conservative reconstruction of quantized cumulative values, not a claim that the original sub-precision rainfall timing is recoverable. Some earlier three-hour amounts are reduced; a sum over a shorter selected period is derived from this corrected series rather than arbitrary independent endpoint clamping.

## Real-source verification

Source: IFS 11 November 2026, 18Z; original GRIB hash `99fbdb2a2fa4b1071922813af1eca782aec97cb54a0748fbd12bb7cc21479723`.

`verify_conservation.py` compares production decoding with an independently indexed, vectorized reconstruction from the original native GRIB fields. Results:

- 64,800 global grid points; 1,555,200 interval values checked.
- Maximum 72-hour total difference from source: **0.0 mm**.
- Negative output intervals: **0**.
- All 7,904 source-dry points have zero intervals.
- All 57,353 monotonic source series are unchanged.
- 26,348 cumulative values adjusted; maximum adjustment 0.1220703125 mm, within packing bounds.
- Unit tests cover intermediate decreases, final zero, monotonic preservation, malformed inputs, accumulated resets beyond tolerance and v2 run-ID support.

Machine-readable evidence: `conservation-fix.json`. The historical v1 audit remains preserved. The same reconstruction is used for regional and global profiles.

## Publication

New run IDs contain `-v2` before the optional coverage suffix, so previous immutable caches cannot be mistaken for corrected data. Every published run additionally checks total conservation, and per-step validation records count corrected cells and their maximum adjustment. Existing API fields and frontend interactions remain unchanged.

This report verifies corrected local processing of real data. The live Render service requires deployment and successful v2 ingestion before these results apply to its output.
