# Independent Python verifier (release gate)

A standalone checker for the covering claim of the [CSS Filter Covering Dataset](../../docs/dataset.md):

> For every one of the 16,777,216 sRGB colors the dataset stores a six-function CSS filter chain which, applied to black, renders the target color with a rendered loss under 1.

This tool re-derives every row's rendered loss from its witness using only the Python standard library (`sqlite3`, `math`, `re`, `unittest`). It is written from the W3C [Filter Effects Level 1](https://www.w3.org/TR/filter-effects-1/) definitions (§5 sRGB-space rule, §9.1 per-primitive clamping, §9.6 feColorMatrix matrices, §13.1.2–13.1.8 function equivalents) — **not** ported from the JavaScript pipeline that produced the data. It is the single trust path every published statistic is checked through.

## Check the claim in one command

With the artifact present, the whole verification is a single command:

```sh
python3 research/verifier/verify_covering.py --db ./hex-to-css-filter-covering-dataset-2026.10.07.sqlite3 scan --jobs 0
```

From an empty directory, one-time setup first (download the published artifact and verify its pinned SHA-256):

```sh
curl -sSfL -O https://github.com/blakegearin/hex-to-css-filter-library/releases/download/dataset-2026.10.07/CHECKSUMS.txt \
  -O https://github.com/blakegearin/hex-to-css-filter-library/releases/download/dataset-2026.10.07/hex-to-css-filter-covering-dataset-2026.10.07.sqlite3.gz
grep 'hex-to-css-filter-covering-dataset-2026.10.07.sqlite3.gz$' CHECKSUMS.txt | sha256sum -c -   # macOS: ... | shasum -a 256 -c -
gunzip hex-to-css-filter-covering-dataset-2026.10.07.sqlite3.gz
```

Exit code `0` = the claim holds. Any other code = it does not (see [Gate semantics](#gate-semantics)). On this machine the full scan takes about 19 seconds with 12 jobs; the artifact download gunzips to 1.7 GiB.

If the library (`hex-to-css-filter-library`) has already cached the dataset, `--db` can be omitted and the verifier finds it in the usual cache location (or `./hex-to-css-filter-covering-dataset-2026.10.07.sqlite3`).

## Modes

| Command | What it does |
| ------- | ------------ |
| `scan [--jobs N] [--json] [--progress]` | Recompute every row's loss from its witness; the release gate. `--jobs 0` = all cores. |
| `sample --n 100000 [--seed S]` | Recompute N random rows (quick spot check). |
| `row '#42dead'` | Show the full math for one color: parsed params, rendered float RGB/HSL, recomputed vs stored loss. |
| `golden [--n 256] [--tol 1.0]` | Render a seeded golden set of witnesses in headless Chrome (`--headless=new --screenshot`), decode the (CRC-checked) PNG, and compare the pixels with the verifier's float RGB. |
| `selftest [-v]` | Known-answer tests: hand-computed spec-matrix chains, the documented example rows, the fractional-parameter rows, parser-rejection cases, and a synthetic DB proving failures/unparseables flip the counters. |

## Gate semantics

Exit codes:

- `0` — claim verified: exactly 16,777,216 rows (the `--expect-rows` gate; only disabled by `--expect-rows 0`, which turns the gate into a spot-check — never use it for a release), zero failures, zero unparseable witnesses.

- `1` — claim violated: some recomputed loss `>= 1`, or some witness text could not be parsed, or (with `--strict-stored`) some stored-loss column value disagrees with the recomputation beyond `--stored-tol` (default `1e-9`).

- `2` — artifact error: file missing or unreadable, not a covering-dataset artifact (bad or unexpected `color` schema, missing `loss` column), row count gate not met, or Chrome failed to cooperate (golden mode). Every mode shares this classification; the verifier never opens the artifact for writing.

The scan reports **passed / failed / unparseable / stored-mismatch as four disjoint counters** that sum exactly to rows processed. A parse error can never count as a pass: the chain regex is fully anchored and accepts both integer and fractional parameters (`invert(26.2%)` must parse as `26.2`, never as `2`). This exists because an early JavaScript scan in this project used `/(\d+)(?:%|deg)/g`, which silently mis-parsed exactly the five fractional-parameter rows while still reporting a clean verification.

`--json` emits the same verdict as one machine-readable object for CI.

## Fidelity to real browsers

The `golden` mode is the load-bearing test: browser rendering is the model's definition. On Chrome 154 (macOS, `--force-color-profile=srgb --force-device-scale-factor=1`) a 2,126-witness sample (6,378 channel comparisons) showed **every** browser pixel within `0.501/255` of the verifier's float value — indistinguishable from the verifier's float rounded to 8 bits, modulo one channel where Chrome's float32 arithmetic flipped a rounding tie by half a code value. The gate therefore defaults to tolerance `1.0/255`: exactly one 8-bit code value, wide enough for float32-vs-float64 luck, tight enough that any real arithmetic disagreement (a wrong coefficient or matrix) would blow through it.

## Two documented findings

1. **Numeric achromatic boundary.** A chain whose final matrix rows sum to 1 within float luck renders a perfect gray; whether the three channels come out *bitwise* equal is decided by the platform libm's last bit. Dividing hue by that noise can invent `|ΔH|` up to 100 for colors every browser quantizes to one gray. The verifier treats channel spreads below `1e-9/255` as achromatic (`h = 0, s = 0`), matching browser output. This flipped the first two full-scan "failures" (`#a1a1a1`, `#e3e3e3`) into passes whose recomputed losses equal the stored values to 1e-10.

2. **Two stored-loss artifacts.** `#010101` (stored 0.41955, re-renders 0.22700) and `#e2e2e2` (stored 0.81157, re-renders 0.26513) still carry ulp-noise hue from the original JS pipeline in their `loss` column. The claim holds under both readings; the default gate ignores these (they are counted and displayed), while `--strict-stored` would fail on them. Both rows are in the golden set, where the browser confirms the verifier's achromatic reading.

## Importable API

```python
from verify_covering import parse_chain, render_chain, rgb_to_hsl, rendered_loss, verify_row, scan_ranges
```

All ΔE, hardness-map and benchmark tools in `research/` must compute rendered colors through this module so every published number shares one trust path.

Built that way: [research/colorimetry](../colorimetry/), with full-cube ΔE2000/per-channel stats (`de2000_stats.py`) whose `selftest` proves its row statuses are bit-equal to `verify_row` and whose scan re-checks the recomputed mean loss against the dataset's published average rendered loss 0.78803 (`docs/dataset.md`) as an artifact identity invariant.

## Runtime reference

Measured on 2026-10-07, Apple silicon (12-core) laptop, warm file cache:

| Mode | Runtime |
| ---- | ------- |
| `scan --jobs 0` (12 jobs, full 16,777,216 rows) | ~19 s |
| `scan --jobs 1` (single core) | ~174 s |
| `golden --n 2048` | ~2 s (+ Chrome) |
| `selftest` | <1 s |

The scan is I/O- and parse-bound per core: it streams `SELECT id, filter, loss FROM color WHERE id BETWEEN ? AND ?` over the primary-key index in contiguous ranges, so cost scales linearly with jobs.

## License

MIT (tooling), matching the library. The dataset itself is CC-BY-4.0.
