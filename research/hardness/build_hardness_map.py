#!/usr/bin/env python3
"""Hardness map for the CSS filter covering dataset: which color regions resisted search.

The dataset was produced by an escalation ladder: a fixed-budget full pass, then
rounds of increasing per-color search budget (6,000,000 -> 24,000,000 ->
60,000,000 evaluations per color), then two no-budget-cap "until-solved"
passes, then a fractional-parameter closure for the last 5 colors. Between
rounds the *survivor list* (colors still unsolved) was retained; those six
lists are the retained round data this tool consumes. NO SEARCHES ARE
RE-RUN: per-color hardness ("which round first solved it") comes straight
from the survivor lists, final per-color loss comes from the dataset artifact.

Outputs (all regenerable from [dataset artifact + round_history.json]):

  * hardness_regions.csv   per-region residual statistics on an HSL grid of
                           the *target* colors: hue sectors of 6 deg x
                           saturation bands of 2 % x lightness bands of 10 %,
                           plus one achromatic pseudo-sector for the 256 pure
                           grays. Columns: population, solved-at-round
                           counts (stage 0..6), and recomputed-loss
                           mean/max over all rows and over the region's
                           survivor rows only.
   * hardness_summary.json  headline numbers for the writeup: per-stage
                            population/loss aggregates, per-2%-saturation-band
                            survivor rates (the spatial-clustering
                            quantification), the integer-lattice case study
                            of the five fractional-parameter colors, the
                            round metadata table, and artifact checks.
  * hardness_map.png       rendered two-panel figure: survivor density and
                           hardest tier per (hue, saturation) cell, with a
                           hue swatch strip and a saturation gradient bar
                           for orientation (pure stdlib PNG encoder).

Everything is computed THROUGH the independent verifier
(research/verifier/verify_covering.py): each row's witness re-renders from
the W3C spec matrices, so the hardness numbers share the covering claim's
single trust path. Faithful to the spec's decision: "all statistics are
derived from the dataset through it".

The round history itself is archived in round_history.json: the six
survivor lists (delta-packed + zlib, base64-embedded), transcribed round
metadata from the rebuild logs, and the counts that tie them together.
`derive` rebuilds that file from the raw rebuild archive; `map` consumes
only round_history.json + the dataset artifact.

Usage:
  python3 build_hardness_map.py selftest [-v]
  python3 build_hardness_map.py derive --archive DIR [--out PATH]
  python3 build_hardness_map.py map [--db PATH] [--rounds PATH] [--out-dir DIR]
                                    [--jobs N] [--progress] [--hash]
  python3 build_hardness_map.py case-study [--db PATH]

License: MIT (tooling), matching the library. Dataset: CC-BY-4.0.
"""

import argparse
import base64
import csv
import json
import math
import multiprocessing
import os
import struct
import sys
import time
import unittest
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "verifier"))

HERE = os.path.dirname(os.path.abspath(__file__))


def local(*parts):
    return os.path.join(HERE, *parts)

from verify_covering import (  # noqa: E402  (path set above, by design)
    LOSS_THRESHOLD,
    SNAPSHOT,
    TOTAL_ROWS,
    ArtifactError,
    check_artifact,
    open_db,
    parse_chain,
    render_chain,
    rendered_loss,
    resolve_db_path,
    split_ranges,
    target_of,
    verify_row,
    fmt_hex,
)

# ---
# The six retained survivor lists, in escalation order. List k holds the ids
# carried INTO round k+1, i.e. the colors still unsolved after round k. The
# lists are strictly nested; a color's "stage" (the round that first solved
# it) is one more than the index of the last list containing it:
#   absent everywhere          -> stage 0  (first-pass coverage)
#   last seen in list 0        -> stage 1  (6M-eval round)
#   last seen in list 4        -> stage 5  (second until-solved pass)
#   present in list 5          -> stage 6  (fractional-parameter closure)
LIST_NAMES = ["survivors.txt", "survivors3.txt", "survivors4.txt",
              "survivors5.txt", "survivors6.txt", "survivors7.txt"]
STAGES = 7
LAST_STAGE = 6

# Stage labels used in every output, one per solved-at round.
STAGE_LABELS = [
    "first-pass coverage (initial fixed-budget full pass)",
    "round 2: 6,000,000 evals/color (1 warm + 5 cold restarts), target <0.999",
    "round 3: 24,000,000 evals/color (1 warm + 5 cold restarts), target <0.99",
    "round 4: 60,000,000 evals/color (1 warm + 5 cold restarts), target <0.998",
    "phase 5: until-solved, no budget cap, target <0.998",
    "phase 6: until-solved, no budget cap, target <0.998",
    "phase 7: fractional (0.1-granularity, seconds-scale) closure of the last 5 colors",
]

# The parameter box the searches optimize over, in integer cells (from the
# rebuild's optimizer bounds: invert/sepia/saturate/brightness/contrast are
# integer percents 0..100 or up to 30000/300, hue-rotate integer degrees
# 0..360). The "integer lattice" of the writeup is exactly this grid.
LATTICE_BOUNDS = [100, 100, 30000, 360, 300, 300]


def lattice_size():
    n = 1
    for hi in LATTICE_BOUNDS:
        n *= hi + 1
    return n


# ---
# Region grid over the TARGET colors. Hue sector 0..59 (6 deg, from HSL of
# the target RGB), saturation band 0..49 (2 % each, [98, 100] merged), and
# lightness band 0..9 (10 % each) plus one achromatic pseudo-sector (-1) for
# the 256 pure grays, whose hue is undefined.
HUE_SECTORS = 60
SAT_BANDS = 50
LIGHT_BANDS = 10
HUE_ACHROMATIC = -1

SAT_BAND_LABELS = ["%d-%d" % (b * 2, min(100, b * 2 + 2)) for b in range(SAT_BANDS)]


def rgb_to_hsl_degrees(r8, g8, b8):
    """Classic RGB->HSL for an 8-bit target; hue in [0,360), sat/light in [0,100].

    Kept here rather than delegating to the verifier's rgb_to_hsl (hue on
    0..100) so region codes match the committed hardness_regions.csv
    exactly, without a rescaling step that could flip a hue sector on a
    boundary color."""
    r, g, b = r8 / 255.0, g8 / 255.0, b8 / 255.0
    mx, mn = max(r, g, b), min(r, g, b)
    lightness = (mx + mn) / 2.0 * 100.0
    if mx == mn:
        return 0.0, 0.0, lightness
    delta = mx - mn
    saturation = delta / (2.0 - mx - mn) if mx + mn > 1.0 else delta / (mx + mn)
    if mx == r:
        h = (g - b) / delta + (6.0 if g < b else 0.0)
    elif mx == g:
        h = (b - r) / delta + 2.0
    else:
        h = (r - g) / delta + 4.0
    h *= 60.0
    if h >= 360.0:
        h -= 360.0
    return h, saturation * 100.0, lightness


def region_code(rid):
    """stable int region key: (hue_sector+1)*500 + sat_band*10 + light_band."""
    r8, g8, b8 = target_of(rid)
    h, s, l = rgb_to_hsl_degrees(r8, g8, b8)
    if s == 0.0:
        hue = HUE_ACHROMATIC
    else:
        hue = min(HUE_SECTORS - 1, int(h // 6.0))
    sat = min(SAT_BANDS - 1, int(s // 2.0))
    light = min(LIGHT_BANDS - 1, int(l // 10.0))
    return (hue + 1) * (SAT_BANDS * LIGHT_BANDS) + sat * LIGHT_BANDS + light


def region_key_parts(code):
    """inverse of region_code: -> (hue_sector, sat_band, light_band)"""
    rest = code % (SAT_BANDS * LIGHT_BANDS)
    return (code // (SAT_BANDS * LIGHT_BANDS) - 1,
            rest // LIGHT_BANDS, rest % LIGHT_BANDS)


# ---
# round_history.json format
# ---
# lists:  name -> base64 of zlib(delta-packed uint32 of the sorted ids)
# rounds: transcribed metadata (counts from the files, budgets/targets from
#         the logged banners, durations where the logs retained them)

ROUND_METADATA = [
    {
        "round": 0,
        "label": "first-pass coverage",
        "stage": 0,
        "budget": "fixed-budget full pass over all 16,777,216 colors "
                  "(per-color budget not retained in the logs)",
        "inputColors": TOTAL_ROWS,
        "outputColors": None,  # filled by derive from survivors.txt
        "sourceLogs": ["work/logs/run.log", "work/logs/polish.log"],
        "note": "the rebuild's first campaign; produced the initial covering "
                "and the first survivor list (136,787 colors)",
    },
    {
        "round": 2,
        "label": "budget round 2",
        "stage": 1,
        "budget": {"evalsPerColor": 6000000, "restarts": "1 warm + 5 cold"},
        "target": 0.999,
        "sourceLog": "work/logs/round2.log",
        "banner": "Round 2: 136787 survivors | 12 workers | 6000000 evals "
                  "(1 warm + 5 cold restarts) | target <0.999",
        "durationMinutes": 151.8,
    },
    {
        "round": 3,
        "label": "budget round 3",
        "stage": 2,
        "budget": {"evalsPerColor": 24000000, "restarts": "1 warm + 5 cold"},
        "target": 0.99,
        "sourceLog": "work/logs/round3.log",
        "banner": "Round 2: 30010 survivors | 12 workers | 24000000 evals "
                  "(1 warm + 5 cold restarts) | target <0.99",
        "durationMinutes": 112.0,
        "note": "banner says 'Round 2' because the same campaign script "
                "(round2_campaign.mjs) drove every round; the escape "
                "target <0.99 is transcribed verbatim from the log",
    },
    {
        "round": 4,
        "label": "budget round 4",
        "stage": 3,
        "budget": {"evalsPerColor": 60000000, "restarts": "1 warm + 5 cold"},
        "target": 0.998,
        "sourceLog": "work/logs/round4.log",
        "banner": "Round 2: 4900 survivors | 12 workers | 60000000 evals "
                  "(1 warm + 5 cold restarts) | target <0.998",
        "durationMinutes": 58.5,
    },
    {
        "round": 5,
        "label": "until-solved pass 1",
        "stage": 4,
        "budget": "no budget cap",
        "target": 0.998,
        "sourceLog": "work/logs/phase5.log",
        "banner": "UNTIL-SOLVED: 934 colors | 12 workers | no budget cap, "
                  "target <0.998 (solved ones only in output)",
        "durationMinutes": None,
    },
    {
        "round": 6,
        "label": "until-solved pass 2",
        "stage": 5,
        "budget": "no budget cap",
        "target": 0.998,
        "sourceLog": "work/logs/phase6.log",
        "banner": "UNTIL-SOLVED: 29 colors | 12 workers | no budget cap, "
                  "target <0.998 (solved ones only in output)",
        "durationMinutes": None,
    },
    {
        "round": 7,
        "label": "fractional closure",
        "stage": 6,
        "budget": "wall-clock seconds per color, split over 6 seeds "
                  "(simulated annealing, 0.1-granularity parameters)",
        "target": 0.998,
        "sourceFiles": ["old-src/fraction_worker.mjs", "work/data/phase7.tsv"],
        "note": "the only stage that abandons integer parameters; closed the "
                "five extreme-yellow colors that stages 0-5 could not",
    },
]

EXPECTED_LIST_COUNTS = [136787, 30010, 4900, 934, 29, 5]


def encode_id_list(ids_sorted):
    """sorted ints -> delta-packed uint32, zlib-compressed, base64 text."""
    prev = 0
    packed = bytearray()
    for v in ids_sorted:
        packed += struct.pack("<I", v - prev)
        prev = v
    return base64.b64encode(zlib.compress(bytes(packed), 9)).decode("ascii")


def decode_id_list(b64):
    packed = zlib.decompress(base64.b64decode(b64))
    out = []
    prev = 0
    for i in range(0, len(packed), 4):
        prev += struct.unpack("<I", packed[i:i + 4])[0]
        out.append(prev)
    return out


def build_stage_map(lists):
    """lists[k] = sorted ids carried into round k+1. Returns {id: stage} where
    stage = (last list index containing it) + 1, and covers every list member."""
    stage = {}
    for k, ids in enumerate(lists):
        for rid in ids:
            stage[rid] = k + 1
    return stage


def derive_rounds_counts(rounds, lists):
    """Fill the derived accumulations: input/output counts per round."""
    counts = [len(xs) for xs in lists]
    out = json.loads(json.dumps(rounds))
    for entry in out:
        st = entry.get("stage")
        if st is None:
            continue
        if st == 0:
            entry["outputColors"] = TOTAL_ROWS - counts[0]
        else:
            # round k solved colors present in its input list but absent
            # from the next list (absent lists mean fully solved)
            nxt = counts[st] if st < len(counts) else 0
            entry["inputColors"] = counts[st - 1]
            entry["outputColors"] = counts[st - 1] - nxt
    out[0]["inputColors"] = TOTAL_ROWS
    return out


def check_survivor_nesting(lists, source):
    for smaller, bigger in zip(lists, lists[1:]):
        if not set(bigger) <= set(smaller):
            raise ArtifactError("survivor lists not nested in %s: bigger list has "
                                "ids the previous list lacks" % source)


def make_round_history(archive_dir):
    """Read the six survivor files from the rebuild archive; build the
    committed round_history payload."""
    lists = []
    for name in LIST_NAMES:
        path = os.path.join(archive_dir, name)
        if not os.path.exists(path):
            raise ArtifactError("missing survivor list %r in archive %r" % (name, archive_dir))
        raw = open(path).read()
        ids = sorted(set(int(x) for x in raw.split()))
        if not ids:
            raise ArtifactError("empty survivor list %r" % name)
        lists.append(ids)
    for name, ids, want in zip(LIST_NAMES, lists, EXPECTED_LIST_COUNTS):
        if len(ids) != want:
            raise ArtifactError("survivor list %r has %d ids, expected %d"
                                % (name, len(ids), want))
    check_survivor_nesting(lists, "archive %r" % archive_dir)
    payload = {
        "format": "survivor lists, delta-packed uint32 + zlib, base64",
        "listOrderNote": "list k = ids carried into round k+1; strictly nested; "
                         "stage = (last list containing an id) + 1",
        "expectedCounts": EXPECTED_LIST_COUNTS,
        "lists": {name: encode_id_list(ids) for name, ids in zip(LIST_NAMES, lists)},
        "rounds": derive_rounds_counts(ROUND_METADATA, lists),
        "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sourceArchive": os.path.abspath(archive_dir),
    }
    return payload


def load_round_history(path):
    """Load + validate the committed round history; return (lists, rounds)."""
    data = json.load(open(path))
    if "lists" not in data or "rounds" not in data:
        raise ArtifactError("round history missing lists/rounds: %r" % path)
    lists = []
    for name in LIST_NAMES:
        if name not in data["lists"]:
            raise ArtifactError("round history missing list %r" % name)
        ids = decode_id_list(data["lists"][name])
        want = data["expectedCounts"][LIST_NAMES.index(name)]
        if len(ids) != want:
            raise ArtifactError("list %r decodes to %d ids, expected %d" % (name, len(ids), want))
        for a, b in zip(ids, ids[1:]):
            if a >= b:
                raise ArtifactError("list %r not strictly sorted" % name)
        lists.append(ids)
    check_survivor_nesting(lists, "round history %r" % path)
    return lists, data["rounds"]


# ---
# map mode: the region aggregation
# ---
# Every worker returns {region_code: Region}; merge left-to-right. Survivor
# rows are those with stage >= 1. Loss values are the verifier's recomputed
# rendered loss. Empty regions are dropped.

_WORKER_STAGE = None


def _init_worker(rounds_path):
    global _WORKER_STAGE
    lists, _rounds = load_round_history(rounds_path)
    _WORKER_STAGE = build_stage_map(lists)


@dataclass
class StageAgg:
    n: int = 0
    loss_sum: float = 0.0
    loss_max: float = float("-inf")
    loss_min: float = float("inf")

    def merge_from(self, other):
        self.n += other.n
        self.loss_sum += other.loss_sum
        self.loss_max = max(self.loss_max, other.loss_max)
        self.loss_min = min(self.loss_min, other.loss_min)


@dataclass
class Region:
    n: int = 0
    counts: list = field(default_factory=lambda: [0] * STAGES)
    loss_sum: float = 0.0
    loss_max: float = float("-inf")
    surv_n: int = 0
    surv_sum: float = 0.0
    surv_max: float = float("-inf")

    def merge_from(self, other):
        self.n += other.n
        for i in range(STAGES):
            self.counts[i] += other.counts[i]
        self.loss_sum += other.loss_sum
        self.loss_max = max(self.loss_max, other.loss_max)
        self.surv_n += other.surv_n
        self.surv_sum += other.surv_sum
        self.surv_max = max(self.surv_max, other.surv_max)


def _map_worker(args):
    db_path, lo, hi, stored_tol = args
    if _WORKER_STAGE is None:
        _init_worker(os.environ["HARDNESS_ROUNDS"])
    stage = _WORKER_STAGE
    conn = open_db(db_path)
    cur = conn.execute("SELECT id, filter, loss FROM color WHERE id BETWEEN ? AND ? ORDER BY id",
                       (lo, hi))
    regions = {}
    fail = unparse = mismatch = 0
    mismatch_examples = []
    stage_agg = [StageAgg() for _ in range(STAGES)]
    while True:
        rows = cur.fetchmany(10000)
        if not rows:
            break
        for rid, text, stored in rows:
            status, loss = verify_row(rid, text, stored, stored_tol)
            st = stage.get(rid, 0)
            reg = regions.get(region_code(rid))
            if reg is None:
                reg = regions[region_code(rid)] = Region()
            reg.n += 1
            reg.counts[st] += 1
            if loss is not None:
                reg.loss_sum += loss
                reg.loss_max = max(reg.loss_max, loss)
                if st >= 1:
                    reg.surv_n += 1
                    reg.surv_sum += loss
                    reg.surv_max = max(reg.surv_max, loss)
            if status == "fail":
                fail += 1
            elif status == "unparseable":
                unparse += 1
            else:
                a = stage_agg[st]
                a.n += 1
                a.loss_sum += loss
                a.loss_max = max(a.loss_max, loss)
                a.loss_min = min(a.loss_min, loss)
                if status == "stored-mismatch":
                    mismatch += 1
                    if len(mismatch_examples) < 20:
                        mismatch_examples.append([rid, loss, stored])
    conn.close()
    return {"regions": regions, "fail": fail, "unparse": unparse,
            "mismatch": mismatch, "mismatchExamples": mismatch_examples,
            "stageAgg": stage_agg}


def merge_region_maps(parts):
    merged = {}
    checks = {"fail": 0, "unparse": 0, "mismatch": 0, "mismatchExamples": [],
              "stageAgg": [StageAgg() for _ in range(STAGES)]}
    for p in parts:
        for code, reg in p["regions"].items():
            dst = merged.get(code)
            if dst is None:
                merged[code] = reg
                continue
            dst.merge_from(reg)
        checks["fail"] += p["fail"]
        checks["unparse"] += p["unparse"]
        checks["mismatch"] += p["mismatch"]
        checks["mismatchExamples"] = (checks["mismatchExamples"] + p["mismatchExamples"])[:20]
        for st in range(STAGES):
            checks["stageAgg"][st].merge_from(p["stageAgg"][st])
    return merged, checks


def stage_table(checks):
    """Final per-stage (count, mean, max, min) from the merged single pass."""
    return [{
        "count": checks["stageAgg"][st].n,
        "mean": checks["stageAgg"][st].loss_sum / checks["stageAgg"][st].n if checks["stageAgg"][st].n else 0.0,
        "max": checks["stageAgg"][st].loss_max if checks["stageAgg"][st].n else 0.0,
        "min": checks["stageAgg"][st].loss_min if checks["stageAgg"][st].n else 0.0,
    } for st in range(STAGES)]


# ---
# Output: hardness_regions.csv
# ---

REGION_CSV_HEADER = [
    "hue_sector", "hue_deg_from", "hue_deg_to", "sat_band_pct", "light_band_pct",
    "n", "survivors",
    "n_stage0", "n_stage1", "n_stage2", "n_stage3", "n_stage4", "n_stage5", "n_stage6",
    "mean_loss_all", "max_loss_all", "mean_loss_survivors", "max_loss_survivors",
]


def region_rows(merged):
    out = []
    for code in sorted(merged):
        reg = merged[code]
        hue, sat, light = region_key_parts(code)
        out.append({
            "hue_sector": hue,
            "hue_deg_from": None if hue < 0 else hue * 6,
            "hue_deg_to": None if hue < 0 else hue * 6 + 6,
            "sat_band_pct": SAT_BAND_LABELS[sat],
            "light_band_pct": "%d-%d" % (light * 10, light * 10 + 10),
            "n": reg.n,
            "survivors": reg.surv_n,
            **{("n_stage%d" % i): reg.counts[i] for i in range(STAGES)},
            "mean_loss_all": reg.loss_sum / reg.n,
            "max_loss_all": reg.loss_max,
            "mean_loss_survivors": (reg.surv_sum / reg.surv_n) if reg.surv_n else 0.0,
            "max_loss_survivors": reg.surv_max if reg.surv_n else 0.0,
        })
    return out


def _load_region_csv_rows(path):
    """Read hardness_regions.csv back (figure mode + selftest roundtrip)."""
    out = []
    with open(path, newline="") as fh:
        for rec in csv.DictReader(fh):
            r = {"hue_sector": int(rec["hue_sector"]),
                 "sat_band_pct": rec["sat_band_pct"],
                 "light_band_pct": rec["light_band_pct"],
                 "n": int(rec["n"]), "survivors": int(rec["survivors"])}
            for st in range(STAGES):
                r["n_stage%d" % st] = int(rec["n_stage%d" % st])
            out.append(r)
    return out


def write_region_csv(path, rows):
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(REGION_CSV_HEADER)
        for r in rows:
            hue = r["hue_sector"]
            w.writerow([
                hue, "" if r["hue_deg_from"] is None else r["hue_deg_from"],
                "" if r["hue_deg_to"] is None else r["hue_deg_to"],
                r["sat_band_pct"], r["light_band_pct"],
                r["n"], r["survivors"],
                *[r["n_stage%d" % i] for i in range(STAGES)],
                "%.6f" % r["mean_loss_all"], "%.6f" % r["max_loss_all"],
                "%.6f" % r["mean_loss_survivors"], "%.6f" % r["max_loss_survivors"],
            ])


# ---
# per-2%-saturation-band rollup (the spatial-clustering headline)
# ---

def sat_band_index(label):
    """'90-92' -> band 45; inverts SAT_BAND_LABELS for rows read back from CSV."""
    return int(label.split("-")[0]) // 2


def sat_band_rollup(rows):
    """Exact per-2%-saturation-band population and survivor counts, hue-
    and lightness-marginalized. Band 49 = [98, 100]."""
    dec = {}
    for r in rows:
        band = sat_band_index(r["sat_band_pct"])
        d = dec.setdefault(band, {"n": 0, "survivors": 0})
        d["n"] += r["n"]
        d["survivors"] += r["survivors"]
    out = []
    for band in sorted(dec):
        d = dec[band]
        out.append({
            "satBandPct": SAT_BAND_LABELS[band],
            "colors": d["n"],
            "survivors": d["survivors"],
            "survivorRatePct": 100.0 * d["survivors"] / d["n"] if d["n"] else 0.0,
        })
    return out


# ---
# the integer-lattice case study (deterministic, post-hoc, tiny budgets)
# ---

FRACTIONAL_IDS = [0xFBFC02, 0xFBFC03, 0xFBFC1F, 0xFCFD02, 0xFCFD03]
PROBE_BUDGET = 200000          # per-color cap on distinct lattice evals
PROBE_DESCENT_STEPS = (-1, 1, -2, 2, -5, 5, -10, 10, -30, 30)
PROBE_OFFSETS = (0, 1, -1, 2, -2, 5, -5, 10, -10, 20, -20, 50, -50,
                 100, -100, 200, -200)


def integer_probe(rid, filter_text, budget=PROBE_BUDGET):
    """Deterministic multi-start greedy descent on the integer lattice, seeded
    from the stored fractional witness (rounded) and saturate-offset variants.

    This is NOT the historical search and never substitutes for it: it is a
    bounded, reproducible post-hoc probe that quantifies how far above the
    certification threshold the adjacent integer neighborhood stayed for the
    five fractional-parameter colors.
    """
    params = parse_chain(filter_text)
    target = target_of(rid)
    lo = [0] * 6
    cache = {}

    def loss(q):
        qt = tuple(q)
        v = cache.get(qt)
        if v is None:
            ok = all(lo[i] <= qt[i] <= LATTICE_BOUNDS[i] for i in range(6))
            v = rendered_loss(render_chain(list(qt)), target) if ok else float("inf")
            cache[qt] = v
        return v

    base = [int(round(x)) for x in params]

    def descend(start):
        cur = list(start)
        cl = loss(cur)
        for _ in range(60):
            improved = False
            for i in range(6):
                for d in PROBE_DESCENT_STEPS:
                    cand = cur[:]
                    cand[i] += d
                    if cand[i] < 0 or cand[i] > LATTICE_BOUNDS[i]:
                        continue
                    v = loss(cand)
                    if v < cl - 1e-12:
                        cur = cand
                        cl = v
                        improved = True
            if not improved:
                break
        return cl, list(cur)

    rounding = {
        "round": base,
        "floor": [int(math.floor(x)) for x in params],
        "ceil": [int(math.floor(x)) + 1 for x in params],
    }
    rounding_losses = {k: loss(v) for k, v in rounding.items()}
    best_loss, best_vec = float("inf"), None
    for off in PROBE_OFFSETS:
        if len(cache) > budget:
            break
        start = base[:]
        start[2] += off
        cl, vec = descend(start)
        if cl < best_loss:
            best_loss, best_vec = cl, vec
    return {
        "id": rid,
        "hex": fmt_hex(rid),
        "storedFilter": filter_text,
        "storedFractionalLoss": rendered_loss(render_chain(params), target),
        "integerRoundingLosses": rounding_losses,
        "integerRoundingVectors": {k: v for k, v in rounding.items()},
        "bestIntegerLossFound": best_loss,
        "bestIntegerVectorFound": best_vec,
        "distinctLatticePointsEvaluated": len(cache),
        "probe": "deterministic multi-start greedy descent from the stored "
                 "fractional witness and saturate offsets %r, budget %d lattice evals; "
                 "steps %r" % (PROBE_OFFSETS, PROBE_BUDGET, PROBE_DESCENT_STEPS),
    }


# ---
# the rendered figure (pure-stdlib PNG)
# ---
# Panel A: survivor density, log10(1 + survivors), black -> crimson -> white.
# Panel B: hardest tier 0..6, discrete warm palette. Bottom row of the grid is
# saturation 0-2 %, top row is 98-100 %. A hue swatch strip sits above the
# grids and a saturation gradient bar to their right for orientation.

TIER_COLORS = [
    (225, 227, 232),  # 0: solved by the first pass (no survivors)
    (49, 104, 142),   # 1: 6M round
    (69, 117, 180),   # 2: 24M round
    (171, 217, 233),  # 3: 60M round
    (255, 237, 160),  # 4: until-solved #1
    (254, 224, 144),  # 5: until-solved #2
    (229, 57, 53),    # 6: fractional closure (the five extreme yellows)
]
DENSITY_STOPS = [
    (0.0, (18, 18, 24)),
    (0.35, (84, 39, 143)),
    (0.65, (219, 92, 104)),
    (0.85, (249, 208, 125)),
    (1.0, (255, 253, 231)),
]


def _lerp_color(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def density_color(t):
    for i in range(len(DENSITY_STOPS) - 1):
        p0, c0 = DENSITY_STOPS[i]
        p1, c1 = DENSITY_STOPS[i + 1]
        if t <= p1:
            return _lerp_color(c0, c1, (t - p0) / (p1 - p0) if p1 > p0 else 0.0)
    return DENSITY_STOPS[-1][1]


def pure_hue_color(hue_deg, sat=100.0, light=50.0):
    """HSL -> sRGB 8-bit for figure orientation strips (targets only)."""
    hp = hue_deg / 60.0
    # standard HSL to RGB
    l = light / 100.0
    c_ = (1.0 - abs(2.0 * l - 1.0)) * (sat / 100.0)
    x = c_ * (1.0 - abs(hp % 2 - 1.0))
    rgb1 = {
        0: (c_, x, 0.0), 1: (x, c_, 0.0), 2: (0.0, c_, x),
        3: (0.0, x, c_), 4: (x, 0.0, c_), 5: (c_, 0.0, x),
    }[int(hp) % 6]
    m = l - c_ / 2.0
    return tuple(int(round((v + m) * 255)) for v in rgb1)


def write_png(path, width, height, rgb_rows):
    """rgb_rows: `height` rows of `width`*3 bytes. 8-bit RGB, filter 0."""
    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + row for row in rgb_rows)
    body = zlib.compress(raw, 9)
    out = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", body)
           + chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(out)
    return len(out)


def build_figure_from_rows(rows, out_path, cell=10, bar=8):
    """Figure straight from the region rows (as written to the CSV) — also
    exposed as the standalone `figure` mode so the rendered map can be
    regenerated from hardness_regions.csv without re-scanning the dataset."""
    hue_to_cells = [None] * HUE_SECTORS  # per hue: [sat_band -> (survivors, tier)]
    for r in rows:
        hue = r["hue_sector"]
        if hue < 0:
            continue
        if hue_to_cells[hue] is None:
            hue_to_cells[hue] = [(0, 0)] * SAT_BANDS
        sat = sat_band_index(r["sat_band_pct"])
        counts = [r["n_stage%d" % st] for st in range(STAGES)]
        tier = 0
        for st in range(STAGES):
            if counts[st]:
                tier = st
        s0, t0 = hue_to_cells[hue][sat]
        hue_to_cells[hue][sat] = (s0 + r["survivors"], max(t0, tier))
    return _render_figure(hue_to_cells, out_path, cell, bar)


def _render_figure(hue_to_cells, out_path, cell=10, bar=8):
    """Two-panel hue x saturation figure.

    Left panel: survivor density, log-scaled. Right panel: hardest tier
    reached in the cell. Bottom row of each grid is saturation 0-2 %, top row
    is 98-100 %. A hue swatch strip spans the top; a saturation gradient bar
    sits right of each grid for orientation. No survivors -> near-black
    (density) / light gray (tier 0).
    """
    grid_w, grid_h = HUE_SECTORS * cell, SAT_BANDS * cell

    max_surv = 1
    for hue in range(HUE_SECTORS):
        if hue_to_cells[hue]:
            for surv, _t in hue_to_cells[hue]:
                max_surv = max(max_surv, surv)
    log_max = math.log10(1 + max_surv)

    def density_value(hue, sat):
        v = 0 if hue_to_cells[hue] is None else hue_to_cells[hue][sat][0]
        return math.log10(1 + v) / log_max if v else 0.0

    def tier_value(hue, sat):
        return 0 if hue_to_cells[hue] is None else hue_to_cells[hue][sat][1]

    swatch_h, gutter, margin = 18, 6, 14
    # layout: left margin | swatch strip | grid A | bar | grid B | bar | margin
    sw_w = HUE_SECTORS * cell
    width = margin + sw_w + gutter + grid_w + bar + gutter + grid_w + bar + margin
    height = margin * 2 + swatch_h + grid_h

    rows = [bytearray(b"\xff\xff\xff" * width) for _ in range(height)]
    grid_y0 = margin + swatch_h

    def fill_rect(x0, y0, w, h, color):
        for y in range(y0, y0 + h):
            rows[y][x0 * 3:(x0 + w) * 3] = bytes(color) * w

    # hue swatch strip
    for hue in range(HUE_SECTORS):
        fill_rect(margin + hue * cell, margin, cell, swatch_h,
                  pure_hue_color(hue * 6.0 + 3.0))
    # saturation gradient bars (gray -> fully saturated red, hue-neutral anchor)
    for sy in range(SAT_BANDS):
        sat_pct = sy * 2.0
        bar_col = pure_hue_color(0.0, sat=sat_pct, light=50.0)
        y = grid_y0 + (SAT_BANDS - 1 - sy) * cell
        for panel in (0, 1):
            bx = margin + sw_w + gutter + panel * (grid_w + bar + gutter) + grid_w
            fill_rect(bx, y, bar, cell, bar_col)
    # the two grids
    def put(panel, hue, sat, color):
        x0 = margin + sw_w + gutter + panel * (grid_w + bar + gutter) + hue * cell
        y0 = grid_y0 + (SAT_BANDS - 1 - sat) * cell
        fill_rect(x0, y0, cell, cell, color)
    for hue in range(HUE_SECTORS):
        for sat in range(SAT_BANDS):
            put(0, hue, sat, density_color(density_value(hue, sat)))
            put(1, hue, sat, TIER_COLORS[min(tier_value(hue, sat), 6)])
    return write_png(out_path, width, height, rows)


# ---
# CLI
# ---

def cmd_derive(args):
    payload = make_round_history(args.archive)
    out = args.out
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    tmp = out + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(payload, fh, indent=1, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, out)
    lists, _ = load_round_history(out)
    print("round history written: %s" % out)
    print("  lists: %s" % ", ".join("%s=%d" % (n, len(x)) for n, x in zip(LIST_NAMES, lists)))
    for r in payload["rounds"]:
        print("  %s: in %s -> out %s" % (r["label"], r.get("inputColors"),
                                         r.get("outputColors")))
    return 0


def _sha256_file(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blob in iter(lambda: fh.read(1 << 24), b""):
            h.update(blob)
    return h.hexdigest()


def _band_rollup(sat_bands, lo, hi, label):
    """Survivor rollup over sat_bands[lo:hi] (hi None = to the end)."""
    sl = sat_bands[lo:hi] if hi is not None else sat_bands[lo:]
    colors = sum(b["colors"] for b in sl)
    survivors = sum(b["survivors"] for b in sl)
    return {"satBandPct": label, "colors": colors, "survivors": survivors,
            "survivorRatePct": 100.0 * survivors / colors if colors else 0.0}


def cmd_map(args):
    rounds_path = args.rounds
    if not os.path.exists(rounds_path):
        print("ERROR: no round history at %s (run `derive`)" % rounds_path, file=sys.stderr)
        return 2
    lists, rounds = load_round_history(rounds_path)
    db_path = resolve_db_path(args.db)
    if _WORKER_STAGE is None:
        _init_worker(os.path.abspath(rounds_path))
    os.environ["HARDNESS_ROUNDS"] = os.path.abspath(rounds_path)
    conn = open_db(db_path)
    try:
        rows_in_table = check_artifact(conn)
    finally:
        conn.close()
    if rows_in_table != TOTAL_ROWS:
        print("ARTIFACT ERROR: row count %d != %d" % (rows_in_table, TOTAL_ROWS), file=sys.stderr)
        return 2
    if args.jobs == 0:
        args.jobs = max(1, os.cpu_count() or 1)
    ranges = split_ranges(args.jobs * 4 if args.jobs > 1 else 1)
    work = [(db_path, lo, hi, 1e-9) for lo, hi in ranges]
    t0 = time.monotonic()

    if args.jobs > 1:
        ctx = multiprocessing.get_context("spawn")
        with ctx.Pool(args.jobs, initializer=_init_worker,
                      initargs=(os.environ["HARDNESS_ROUNDS"],)) as pool:
            results = []
            # imap (not imap_unordered): deterministic merge order keeps the
            # CSV byte-identical across reruns
            for r in pool.imap(_map_worker, work):
                results.append(r)
                if args.progress:
                    print("  ... %d workers done, %d region codes so far"
                          % (len(results), sum(len(x["regions"]) for x in results)),
                          file=sys.stderr)
        parts = results
    else:
        parts = [_map_worker(work[0])]
    merged, checks = merge_region_maps(parts)
    if checks["fail"] or checks["unparse"]:
        print("ARTIFACT ERROR: %d failing / %d unparseable rows during scan; refuse to map"
              % (checks["fail"], checks["unparse"]), file=sys.stderr)
        return 1
    elapsed = time.monotonic() - t0

    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)
    root = os.path.dirname(os.path.abspath(out_dir))
    csv_path = os.path.join(out_dir, "hardness_regions.csv")
    rows = region_rows(merged)
    total_rows = sum(r["n"] for r in rows)
    if total_rows != TOTAL_ROWS:
        print("ARTIFACT ERROR: region population %d != %d" % (total_rows, TOTAL_ROWS),
              file=sys.stderr)
        return 2
    write_region_csv(csv_path, rows)

    # per-stage aggregates come from the same single pass (see merge_region_maps)
    sat_bands = sat_band_rollup(rows)
    stage_tables = stage_table(checks)
    # summary: the writeup payload
    figure_path = os.path.join(root, "hardness_map.png")
    fig_bytes = build_figure_from_rows(rows, figure_path)

    # artifact hash (optional; ~8 s on this machine)
    sha = _sha256_file(db_path) if args.hash else None

    case_rows = []
    conn = open_db(db_path)
    for rid in FRACTIONAL_IDS:
        f_text = conn.execute(
            "SELECT filter FROM color WHERE id = ?", (rid,)).fetchone()[0]
        case_rows.append(integer_probe(rid, f_text))
    conn.close()

    summary = {
        "snapshot": SNAPSHOT,
        "dataset": {"path": db_path, "size": os.path.getsize(db_path), "sha256": sha},
        "rows": TOTAL_ROWS, "lossThreshold": LOSS_THRESHOLD,
        "stages": {
            str(st): {
                "label": STAGE_LABELS[st],
                "colors": stage_tables[st]["count"],
                "meanLoss": stage_tables[st]["mean"],
                "maxLoss": stage_tables[st]["max"],
                "minLoss": stage_tables[st]["min"],
            } for st in range(STAGES)
        },
        "saturationBands": sat_bands,
        "hotZone": {
            **_band_rollup(sat_bands, -5, None, "90-100"),
            "midSatComparison": _band_rollup(sat_bands, 25, 45, "50-90"),
        },
        "integerLattice": {
            "parameterSpaceCells": lattice_size(),
            "largestBudgetEvalsPerColor": 60_000_000,
            "largestBudgetFractionOfLattice": 60_000_000 / lattice_size(),
            "caseStudy": case_rows,
        },
        "rounds": rounds,
        "checks": {
            "failedRows": checks["fail"],
            "unparseableRows": checks["unparse"],
            "storedMismatchRows": checks["mismatch"],
            "storedMismatchExamples": checks["mismatchExamples"],
            "totalRegionPopulation": total_rows,
            "regionRowsWritten": len(rows),
        },
        "outputs": {
            "regionCsv": os.path.abspath(csv_path),
            "summaryJson": None,
            "figure": os.path.abspath(figure_path),
            "figureBytes": fig_bytes,
        },
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runtimeSeconds": round(elapsed, 1),
    }
    summary_path = os.path.join(out_dir, "hardness_summary.json")
    tmp = summary_path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(summary, fh, indent=1, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, summary_path)

    print("hardness map written")
    print("  regions: %d (%d empty dropped), rows %d" % (len(rows), num_empty_regions(rows), total_rows))
    for st in range(STAGES):
        t = stage_tables[st]
        print("  stage %d: %8d colors | mean %.4f | max %.6f" %
              (st, t["count"], t["mean"], t["max"]))
    hz = summary["hotZone"]
    print("  survivor rate, S 90-100%%: %.3f%% vs S 50-90%%: %.3f%% (mid)"
          % (hz["survivorRatePct"], hz["midSatComparison"]["survivorRatePct"]))
    print("  figure: %s (%d bytes)" % (figure_path, fig_bytes))
    print("  summary: %s" % summary_path)
    print("  regions: %s" % csv_path)
    return 0


def num_empty_regions(rows):
    # rows contains only populated regions; empties were dropped by scan
    full = (HUE_SECTORS + 1) * SAT_BANDS * LIGHT_BANDS
    return full - len(rows)


def cmd_figure(args):
    rows = _load_region_csv_rows(args.csv)
    if not rows:
        print("ERROR: no region rows in %s" % args.csv, file=sys.stderr)
        return 2
    nbytes = build_figure_from_rows(rows, args.out)
    print("figure written: %s (%d bytes) from %d regions" % (args.out, nbytes, len(rows)))
    return 0


def cmd_case_study(args):
    db_path = resolve_db_path(args.db)
    conn = open_db(db_path)
    for rid in FRACTIONAL_IDS:
        row = conn.execute("SELECT filter FROM color WHERE id = ?", (rid,)).fetchone()
        if row is None:
            print("missing fractional row %s" % fmt_hex(rid), file=sys.stderr)
            return 2
        info = integer_probe(rid, row[0])
        print("%s stored %.6f | integer round %.6f floor %.6f ceil %.6f | "
              "best-integer-nearby %.6f at %s (%d evals)"
              % (info["hex"], info["storedFractionalLoss"],
                 info["integerRoundingLosses"]["round"],
                 info["integerRoundingLosses"]["floor"],
                 info["integerRoundingLosses"]["ceil"],
                 info["bestIntegerLossFound"],
                 info["bestIntegerVectorFound"],
                 info["distinctLatticePointsEvaluated"]))
    conn.close()
    return 0


# ---
# selftest
# ---

class TestListsAndStages(unittest.TestCase):
    def setUp(self):
        self.rounds_path = local("data", "round_history.json")
        if not os.path.exists(self.rounds_path):
            self.skipTest("round_history.json not committed yet; run `derive`")

    def test_round_history_loads_and_nests(self):
        lists, rounds = load_round_history(self.rounds_path)
        self.assertEqual([len(x) for x in lists], EXPECTED_LIST_COUNTS)
        check_survivor_nesting(lists, "round history")
        self.assertEqual(len(rounds), len(ROUND_METADATA))

    def test_stage_assignment_spot_values(self):
        lists, _ = load_round_history(self.rounds_path)
        stage = build_stage_map(lists)
        # real spot checks from the rebuild:
        self.assertEqual(stage.get(65852), 1)         # solved by the 6M round
        self.assertEqual(stage.get(66037), 2)         # 24M round
        self.assertEqual(stage.get(68862), 3)         # 60M round
        self.assertEqual(stage.get(130561), 4)        # until-solved #1
        self.assertEqual(stage.get(16514092), 5)      # until-solved #2
        for rid in FRACTIONAL_IDS:
            self.assertEqual(stage.get(rid), 6)       # fractional closure
        self.assertNotIn(0, stage)                     # black never a survivor
        self.assertEqual(len(stage), len(lists[0]))    # distinct survivor ids


class TestRegionBuckets(unittest.TestCase):
    def test_known_colors(self):
        # both achromatic: hue is undefined and collapses to the pseudo-sector
        hue0, sat0, _l0 = region_key_parts(region_code(0x000000))
        hue1, _s1, _l1 = region_key_parts(region_code(0xFFFFFF))
        self.assertEqual(hue0, HUE_ACHROMATIC)
        self.assertEqual(hue1, HUE_ACHROMATIC)
        h, s, l = region_key_parts(region_code(0xFF0000))
        self.assertEqual((h, s, l), (0, SAT_BANDS - 1, 5))   # pure red: sat 100, light 50
        h, s, l = region_key_parts(region_code(0xFBFC02))
        self.assertEqual(h, 10)                              # 60-66 deg: the yellow sector
        h2, s2, l2 = region_key_parts(region_code(0xFCFD02))
        self.assertEqual((h2, s2, l2), (10, SAT_BANDS - 1, 5))  # lightness (253+2)/2 = 50%
        h, s, l = region_key_parts(region_code(0x00FF00))    # green: hue exactly 120 deg
        self.assertEqual(h, 20)                              # floor(120/6)
        h, s, l = region_key_parts(region_code(0x0000FF))    # blue: hue exactly 240 deg
        self.assertEqual(h, 40)

    def test_regions_cover_all_ids_codes(self):
        for rid in (0x000000, 0xFFFFFF, 0x010203, 0xFBFC02, 0xFCFD03, 0xDEAD42):
            hue, sat, light = region_key_parts(region_code(rid))
            self.assertTrue(-1 <= hue <= 59)
            self.assertTrue(0 <= sat <= 49)
            self.assertTrue(0 <= light <= 9)


class TestListCodec(unittest.TestCase):
    def test_roundtrip(self):
        for xs in ([0], [5], [1, 2, 3, 10 ** 6], sorted(set(
                (i * 8388607 + 12345) % TOTAL_ROWS for i in range(100)))):
            b64 = encode_id_list(sorted(xs))
            self.assertEqual(decode_id_list(b64), sorted(xs))


class TestStageAggregates(unittest.TestCase):
    def test_stage_counts_match_list_diffs(self):
        self.rounds_path = local("data", "round_history.json")
        if not os.path.exists(self.rounds_path):
            self.skipTest("round_history.json not committed yet")
        lists, _ = load_round_history(self.rounds_path)
        stage = build_stage_map(lists)
        counts = [0] * STAGES
        for st in stage.values():
            counts[st] += 1
        counts[0] = TOTAL_ROWS - len(stage)
        resolved = derive_rounds_counts(ROUND_METADATA, lists)
        outs = [len(lists[k]) - len(lists[k + 1]) for k in range(len(lists) - 1)]
        outs.append(len(lists[-1]))  # the fractional closure solved all five
        self.assertEqual(counts[1:], outs)
        self.assertEqual(resolved[0]["outputColors"], TOTAL_ROWS - len(lists[0]),
                         "stage-0 population = rows minus the first survivor list")


class TestFigure(unittest.TestCase):
    def test_png_decodable_by_verifier(self):
        from verify_covering import decode_png
        with tempfile_target() as path:
            w, h = 40, 20
            rows = [bytes(w * 3) for _ in range(h)]
            write_png(path, w, h, rows)
            dw, dh, bpp, prs = decode_png(path)
            self.assertEqual((dw, dh, bpp), (w, h, 3))
            self.assertEqual(len(prs), h)

    def test_figure_roundtrips_through_csv(self):
        region = region_code(0xFBFC02)
        counts = [0] * STAGES
        counts[6] = 4
        merged = {region: Region(n=4, counts=counts, loss_sum=1.9, loss_max=0.97,
                                 surv_n=4, surv_sum=3.8, surv_max=0.97)}
        with tempfile_target() as _csv:
            rows = region_rows(merged)
            write_region_csv(_csv, rows)
            back = _load_region_csv_rows(_csv)
            self.assertEqual(back[0]["n_stage6"], 4)
            self.assertEqual(back[0]["hue_sector"], 10)
            with tempfile_target() as fig:
                nbytes = build_figure_from_rows(_load_region_csv_rows(_csv), fig)
                self.assertGreater(nbytes, 1000)


class TestProbe(unittest.TestCase):
    def test_rounding_of_case_study_colors_stays_above_threshold(self):
        # Regression anchors measured during the case study; the converter must
        # reproduce them exactly (deterministic).
        anchors = {
            0xFBFC02: 2.671624,   # round
            0xFBFC03: 1.036412,
            0xFBFC1F: 3.849453,
            0xFCFD02: 3.810029,
            0xFCFD03: 4.819731,
        }
        cases = {
            0xFBFC02: ("invert(26.2%) sepia(78.3%) saturate(4245.5%) hue-rotate(56.9deg) "
                       "brightness(241.7%) contrast(98.3%)"),
            0xFBFC03: ("invert(95.9%) sepia(3%) saturate(14349.1%) hue-rotate(18deg) "
                       "brightness(137%) contrast(98%)"),
            0xFBFC1F: ("invert(91.6%) sepia(15.8%) saturate(7661.2%) hue-rotate(39.7deg) "
                       "brightness(223.8%) contrast(97.5%)"),
            0xFCFD02: ("invert(78.3%) sepia(30.6%) saturate(10529.8%) hue-rotate(35.3deg) "
                       "brightness(170.2%) contrast(98.6%)"),
            0xFCFD03: ("invert(74.5%) sepia(11.6%) saturate(10489.7%) hue-rotate(51deg) "
                       "brightness(281.3%) contrast(98.6%)"),
        }
        for rid, txt in cases.items():
            v = integer_probe(rid, txt, budget=PROBE_BUDGET)
            self.assertAlmostEqual(v["integerRoundingLosses"]["round"], anchors[rid],
                                   delta=5e-4, msg=fmt_hex(rid))
            # every one of the case-study probes was billed to stay "just above"
            # the threshold at rounding granularity; assert round >= 1 for all
            self.assertGreaterEqual(v["integerRoundingLosses"]["round"],
                                    1.0, "rounding must stay >= 1 (case study premise)")

    def test_lattice_size(self):
        # 101*101*30001*361*301*301
        self.assertEqual(lattice_size(), 101 * 101 * 30001 * 361 * 301 * 301)


def tempfile_target():
    import tempfile

    class _Ctx:
        def __enter__(self):
            self.dir = tempfile.TemporaryDirectory()
            self.path = os.path.join(self.dir.name, "out.bin")
            return self.path

        def __exit__(self, *a):
            self.dir.cleanup()
            return False
    return _Ctx()


def cmd_selftest(args):
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for cls in (TestListsAndStages, TestRegionBuckets, TestListCodec,
                TestStageAggregates, TestFigure, TestProbe):
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2 if args.verbose else 1)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="build_hardness_map.py",
        description="Hardness map for the CSS filter covering dataset "
                    "(survivor-list escalation history; no searches are re-run).")
    p.add_argument("--db", help="path to the covering dataset artifact")
    sub = p.add_subparsers(dest="mode", required=True)

    d = sub.add_parser("derive", help="rebuild round_history.json from the rebuild archive")
    d.add_argument("--archive", required=True,
                   help="directory containing the six survivor*.txt lists")
    d.add_argument("--out", default=local("data", "round_history.json"))
    d.set_defaults(func=cmd_derive)

    m = sub.add_parser("map", help="aggregate region statistics + render the figure")
    m.add_argument("--rounds", default=local("data", "round_history.json"))
    m.add_argument("--out-dir", default=local("data"))
    m.add_argument("--jobs", type=int, default=8)
    m.add_argument("--progress", action="store_true")
    m.add_argument("--hash", action="store_true", help="include dataset sha256 in summary")
    m.set_defaults(func=cmd_map)

    c = sub.add_parser("case-study", help="integer-lattice probe of the five fractional colors")
    c.set_defaults(func=cmd_case_study)

    f = sub.add_parser("figure", help="re-render hardness_map.png from hardness_regions.csv")
    f.add_argument("--csv", default=local("data", "hardness_regions.csv"))
    f.add_argument("--out", default=local("hardness_map.png"))
    f.set_defaults(func=cmd_figure)

    s = sub.add_parser("selftest", help="tests")
    s.add_argument("-v", "--verbose", action="store_true")
    s.set_defaults(func=cmd_selftest)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except ArtifactError as exc:
        print("ARTIFACT ERROR: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
