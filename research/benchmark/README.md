# Optimization benchmark export: a fully-solved 6-parameter problem at 16.7M-instance scale

The [covering dataset](../../docs/dataset.md) is a flat, SQLite-free benchmark corpus for metaheuristic researchers: **one record per sRGB color (16,777,216 instances), each with its target RGB, its witness parameter vector, and the achieved loss**. The framing is best-known-solution:

- Each instance is a 6-parameter nonlinear optimization problem: choose the six chain parameters so the *rendered loss* (sum of absolute RGB and HSL deltas against the target — see [the metric](../../docs/dataset.md#the-metric-rendered-loss)) is minimized; the covering claim says a value under 1 exists and is recorded.
- **The dataset witnesses ARE the best-known solutions.** Every witness was produced by the rebuild's escalating search budgets (a full fixed-budget pass, then 6M / 24M / 60M evaluations per color, then two no-cap until-solved passes; see the [hardness map](../hardness/README.md) for the full escalation record). No better parameter vector is known for any of the 16,777,216 instances.
- Fixed validation: the maximizing instance under the metric is [#38cac2](../verifier/README.md) at stored loss 0.9999991215 — reproducible in one pass over this file by any scorer, no search required.

## The artifact

| File | What |
| ---- | ---- |
| `hex-to-css-filter-benchmark-2026.10.07.csv.gz` | the corpus; CSV, gzip level 9, header first, ~16.7M rows |
| `benchmark_manifest.json` | column spec, dataset identity, recomputation tallies, checksums |
| `BENCHMARK_CHECKSUMS.txt` | `sha256sum`-format checksums for both files |

Download (release `dataset-2026.10.07`, where the source artifact lives):

- https://github.com/blakegearin/hex-to-css-filter-library/releases/download/dataset-2026.10.07/hex-to-css-filter-benchmark-2026.10.07.csv.gz
- Mirror: https://data.blakegearin.com/2026.10.07/hex-to-css-filter-benchmark-2026.10.07.csv.gz

## Column spec

`id,r,g,b,invert,sepia,saturate,hue_rotate,brightness,contrast,loss`

Header line first, LF newlines, no quoting (no field ever contains a comma or quote — parse with a plain `split(",")` / `read_csv` on defaults). Numeric text is the shortest exact-roundtrip form: integral parameters drop the trailing `.0` (`95`, not `95.0`); fractional parameters keep full precision (`26.2`); losses are emitted by Python `repr` and read back bit-identically.

| Column | Unit / range | Description |
| ------ | ------------ | ----------- |
| `id` | `0..16777215` | Target color packed `0xRRGGBB` (red in the high byte); the hex color is `'%06X' % id` |
| `r`, `g`, `b` | `0..255` | Target channels (derivable from `id`; kept for convenience) |
| `invert` | percent | `invert()` amount — the CSS-facing number; renderers of this benchmark apply matrix math with amounts divided by 100 |
| `sepia` | percent | `sepia()` amount |
| `saturate` | percent | `saturate()` amount — commonly tens of thousands; this axis is what makes the problem wide-range |
| `hue_rotate` | degrees | `hue-rotate()` angle |
| `brightness` | percent | `brightness()` amount |
| `contrast` | percent | `contrast()` amount — may exceed 100 |
| `loss` | `0..<1` | Achieved rendered loss of the witness (the dataset's `loss` column); the bound `1` defines "solved". Metric: sum of absolute RGB (0–255 scale) and HSL (hue/sat/light on 0–100 scale, achromatic read as `h = 0, s = 0`) deltas between rendered and target — the dataset's historical definition, kept for comparability; it is non-standard (see [docs](../../docs/dataset.md#the-metric-rendered-loss)) |

The parameter vector is parsed out of the dataset's canonical `filter` TEXT (the CSS chain `invert() sepia() saturate() hue-rotate() brightness() contrast()`, in that exact order to black). Five exceptions were stored with 0.1-granularity fractional parameters; see [fractional-parameter exceptions](../../docs/dataset.md#fractional-parameter-exceptions).

To re-render a row's color from its parameters (the objective), apply the W3C [Filter Effects Level 1](https://www.w3.org/TR/filter-effects-1/) color-matrix chain to black. The reference implementation, written independently of the search code that produced the witnesses, is [`research/verifier/verify_covering.py`](../verifier/README.md): `parse_chain` / `render_chain` / `rendered_loss` — and `verify_covering.py golden` validates that arithmetic against real headless-Chrome pixels.

## Warm-start prior art

How the phase experiments seeded their searches — recorded here because there is no published prior art for this problem:

1. **Stored witness (warm start).** Resume from the color's own stored witness. This was seed 1 of every escalation round (the banners read "1 warm + 5 cold restarts" per color, e.g. the 6M/24M/60M-eval rounds).
2. **Solved-neighbor.** Seed from a nearby color's solved witness. Recorded finding: this helps only marginally — the parameter→color map is smooth forward but its inverse is not continuous, so two colors one unit apart can have witnesses far apart in parameter space. The extreme case study: all five fractional-row witnesses sit at loss 0.74–0.97, yet *every* rounding of their parameters to integers lands at loss 1.04–15.08 — [the integer-floor pocket analysis](../hardness/README.md#3-the-integer-floor-case-study-five-extreme-yellows).
3. **Random restarts.** The workhorse: 5 cold restarts per color per round, covering where warm/neighbor seeding stalls.

For budget-exhaustion studies, "which budget level first certified each color" (the stage attribution) is derivable from [`research/hardness/data/round_history.json`](../hardness/data/round_history.json): a color's stage is one more than the index of the last of the six nested survivor lists that contains its id (absent everywhere = stage 0, the first pass). Expected shape: 99.2% of colors need no escalation at all, and hardness concentrates near extreme saturations — [quantified here](../hardness/README.md#findings).

## Reproducing

From the repo root (the verifier's `resolve_db_path` finds the cached artifact automatically; or pass `--db`):

```sh
# all checks (~1 s)
python3 research/benchmark/export_benchmark.py selftest -v

# full export: every row re-rendered through the verifier as it is exported
# (the run recorded in benchmark_manifest.json took 148 s at 12 jobs on
# Apple-silicon 12 cores; writes the .csv.gz, manifest, and checksums)
python3 research/benchmark/export_benchmark.py export --jobs 0 --progress

# verify the FILE: readback re-renders every row, and a seeded sample of
# 100,000 records is cross-checked parameter-by-parameter against the
# dataset artifact (~2 min)
python3 research/benchmark/export_benchmark.py verify
```

Both passes fail nonzero if any row fails the covering claim, is blank, or disagrees with the artifact. The two rows whose stored `loss` differs from its recomputation beyond 1e-9 (`#010101`, `#e2e2e2`) are the dataset's two [documented stored-loss artifacts](../verifier/README.md#two-documented-findings), counted and reported, not fatal — the claim holds under both readings.

The export is deterministic (ordered worker merge, zeroed gzip timestamp, repr-exact floats): reruns are byte-identical except the manifest's `generatedAt`/`runtimeSeconds`. Consequence for the checksum file: a fresh rerun rewrites `BENCHMARK_CHECKSUMS.txt` with the unchanged `.csv.gz` hash but a fresh manifest hash — so the manifest row there matches only the published run. When checking a rerun, compare the `.csv.gz` row against the published checksum file, not the manifest row.

## License

MIT (tooling), matching the library. The dataset — and this export of it — is [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).
