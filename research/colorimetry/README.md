# Colorimetric stats: Delta-E2000 over the whole cube

`de2000_stats.py` scores every color's witness through the independent verifier's rendering model (`../verifier/verify_covering.py`, the same trust path as the <1% covering claim), converts rendered RGB to CIELAB (D65), and computes CIEDE2000 plus per-channel errors for all 16,777,216 colors. The headline number for the dataset doc, the arXiv note and the outreach email:

> **integer CSS filters cover sRGB within Delta-E2000 of 1.096** (measured maximum 1.095415 at `#231a0b` over all 16,777,216 colors, mean 0.0281; browser-quantized rendering, snapshot 2026.10.07)

Under the published perceptibility scale (Sharma et al. 2005 / Mahy et al. 1994), *every* color is under Delta-E 2 (the largest perceptibility threshold in the standard bands). 99.9997% are under Delta-E 1, not perceptible except through very close observation. Two renderings are always reported side by side: the 8-bit-quantized one (what a browser paints, per the verifier's Chrome golden set) and the float model (max 0.6537, the unrounded chain output).

## Run it

```sh
python3 research/colorimetry/de2000_stats.py selftest        # published-data tests, <1 s
python3 research/colorimetry/de2000_stats.py row '#231a0b'   # full colorimetry for one color
python3 research/colorimetry/de2000_stats.py sample --n 100000
python3 research/colorimetry/de2000_stats.py scan --jobs 0   # writes the two stats files
```

The `row` output is designed for hand-verification without trusting any code in this repo: it prints both CIELAB triples (target and rendered), so you can check the math with the authors' own published calculator (`CIEDE2000.xls` / `deltaE2000.m` on https://www.hajim.rochester.edu/ece/~gsharma/ciede2000/) and see the printed Delta-E match. The Table I data that `selftest` checks against comes from that same page. Or run `recheck_rows_coloraide.py` (below) to have a third-party library re-derive the published table.

`scan` finds the artifact in the library cache (or pass `--db`), verifies its sha256, recomputes every row, and checks four self-evidencies: disjoint counters, histogram sums to scored rows, worst-K heap ordered, and mean recomputed loss equal to the dataset's published average rendered loss (0.78803 in `docs/dataset.md`; the recomputed full-precision value is 0.78803648). A wrong artifact or broken arithmetic cannot pass. It then writes two files. `de2000_stats.json` is machine-readable: histogram (131 buckets over the 130 edges 0.001–100, the two open end-buckets included), percentiles, perceptibility bands, per-channel errors, loss-band table, hardness cross-check, worst 200 colors with witnesses, and a full method block. `de2000_summary.md` is the human summary with the quotable statement. Both are regenerable from the artifact alone. Runtime/timestamp are the only run-dependent fields. Exit codes mirror the verifier: 0 = stats consistent, 1 = invariant/covering violation, 2 = artifact error.

**Runtime** (Apple silicon 12-core, Python 3.9.4, warm cache): full scan 33 s at 12 jobs, 287 s single core. Counts, maxima and the histogram are identical across job counts. Mean-valued fields are rounded to 10-12 decimals in the JSON so that float summation order cannot wobble the last ulp, and the stats file is therefore byte-stable apart from timestamp/runtime. Stdlib only (uses `math.cbrt` on 3.11+, `pow` fallback otherwise).

## Why the numbers are trustworthy

- **Conversion validated against published data**: all 34 CIEDE2000 test pairs of Sharma, Wu & Dalley (2005, Table I) reproduced within 4-decimal rounding, plus the published CIELAB values of the sRGB primaries (`selftest`). The embedded table was checked digit-for-digit against the authors' own machine-readable file (`ciede2000testdata.txt`, sha256 `44aebb39…`), so these are externally sourced ground truth: a wrong formula cannot reproduce them.

- **Independent-oracle cross-check**: `crosscheck_coloraide.py` (dev-only, needs `pip install coloraide`) agrees to 3e-13 on the pure formula over 200k random Lab pairs and to <4e-4 on end-to-end Delta-E over 50k nearby 8-bit color pairs (its exit banner always reports the actual measured deviations); the documented residual is the D65-white convention (this tool uses the classical CIE-tabulated 0.95047/1/1.08883 white the published anchors use).

- **Re-checking the published file without trusting this tool**: `recheck_rows_coloraide.py` (dev-only) recomputes every number in the stats file's `worst[]` table, and N random rows against the published distribution (mean and band shares at 6 sigma), using ONLY the spec renderer (`verify_covering.py`, itself browser-verified) and third-party `coloraide`; it never imports `de2000_stats.py`. Measured: 400/400 per-row values agree (max deviation 0.000092), distribution checks pass at n=100,000. Anyone can rerun: `pip install coloraide && python3 research/colorimetry/recheck_rows_coloraide.py`.

- **One trust path**: witnesses are parsed/rendered by the verifier's `parse_chain`/`render_chain`; statuses are `verify_row`-identical (proved bit-equal by `selftest`); the loss is the verifier's `rendered_loss`.

- **Caveats in the summary**:
  - the 5 fractional-parameter witnesses (the "integer" statement holds strictly for the other 16,777,211)
  - exact-half quantization ties can flip one code value across platforms inside the golden tolerance
  - the hardness cross-check is a loss-band proxy until the survivor-based hardness map replaces it

## Findings worth citing

- Worst colors cluster at the **dark extreme** (mean target L* 14.9 for the worst 200 vs 57.5 for the cube): one code of float residual is worth the most Delta-E near black.

- Per-channel error: **no channel of any color is ever off by more than one 8-bit code value**, and the float rendering never deviates more than 0.938 codes; ~4% of colors round one code value per channel (R 655,989 / G 598,511 / B 704,357 rows).

- Delta-E rises monotonically with the mixed-metric loss band (mean 0.000 / 0.019 / 0.048 / 0.053 across `[0,0.5) / [0.5,0.9) / [0.9,0.99) / [0.99,1)`), and the worst-200 colors are 2.7x enriched in the near-threshold band. That band is not itself dark-biased, so "search-hard" and "colorimetry-worst" are related yet distinct notions. State this precisely in the writeup and re-check against the hardness map.

License: MIT (tooling), matching the library; dataset CC-BY-4.0.
