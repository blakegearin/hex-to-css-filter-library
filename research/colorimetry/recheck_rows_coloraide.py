#!/usr/bin/env python3
"""Independent re-verification of the published colorimetric stats on real dataset rows.

This script exists because the stats file was computed by de2000_stats.py, and
"trust the tool that made the numbers" is not verification. It re-derives every
checkable number from two sources that are NOT de2000_stats.py:

  * research/verifier/verify_covering.py: the W3C-spec rendering model whose
    fidelity to real browser pixels was measured in the verifier's `golden`
    mode (every Chrome pixel equal to the model's float within one 8-bit code), and
  * `coloraide` (pip install coloraide), an independent third-party color
    library with its own CIEDE2000 and sRGB->CIELAB (D65) implementations.

`de2000_stats.py` is deliberately never imported here. If its colorimetry were
wrong, this script would disagree with the published file and exit nonzero.

Checks:
  1. PER-ROW: every `worst[]` entry of de2000_stats.json is recomputed from its
     stored witness (quantized and float renderings) and compared to the
     published Delta-E values, tolerance --tol (default 1e-3).
  2. AGGREGATE: --n random rows are independently rescored, and their sample
     is compared to the published distribution: no row may exceed the
     published maxima; the sample mean must sit inside a 6-sigma band derived
     from the PUBLISHED histogram itself (worst-case second moment); the share
     of sample rows under each published perceptibility band must match the
     published share within 6 binomial standard deviations. A wrong formula
     shifts the distribution and trips this.

Convention note: coloraide uses the D65 white derived from chromaticity
(0.9504559, 1, 1.0890578) while the published stats use the classical CIE
tabulated white (0.95047, 1, 1.08883), ~1e-2 in absolute L*a*b*, largely
cancelling inside a Delta-E between a target and its rendering (always
nearby): measured <1e-3. The tolerance above is set from that measurement.

Usage:
  pip install coloraide
  python3 research/colorimetry/recheck_rows_coloraide.py
  python3 research/colorimetry/recheck_rows_coloraide.py --n 200000 --seed 11

Exit 0 = every rechecked number agrees; 1 = a published statistic failed
independent re-verification; 2 = artifact/stat-file problem. Stdlib + coloraide
only; Python 3.8+.
"""

import argparse
import json
import math
import os
import random
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "verifier"))

from verify_covering import (  # noqa: E402  (trust path, not the tool under test)
    TOTAL_ROWS,
    ArtifactError,
    fetch_rows,
    open_db,
    parse_chain,
    render_chain,
    resolve_db_path,
    target_of,
    UnparseableWitness,
)

from coloraide import Color  # noqa: E402


def delta_e_pair(rgb_a, rgb_b):
    """Delta-E2000 between two 0-255 RGB triples (int or float), coloraide-only path."""
    ca = Color("srgb", data=[c / 255.0 for c in rgb_a]).convert("lab-d65")
    cb = Color("srgb", data=[c / 255.0 for c in rgb_b]).convert("lab-d65")
    return ca.delta_e(cb, method="2000")


def recheck_row(conn, row_id):
    """Return (dE_quantized, dE_float) recomputed independently for one dataset row."""
    row = conn.execute("SELECT filter FROM color WHERE id = ?", (row_id,)).fetchone()
    if row is None:
        return None
    rgb_f = render_chain(parse_chain(row[0]))
    rgb_i = (round(rgb_f[0]), round(rgb_f[1]), round(rgb_f[2]))
    target = target_of(row_id)
    return (delta_e_pair(target, rgb_i), delta_e_pair(target, rgb_f))


def histogram_sigma(doc):
    """Worst-case std of the published quantized Delta-E distribution: for each
    bucket use its corner FARTEST from the mean, weighted by bucket share."""
    mu = doc["deltaE2000Quantized"]["mean"]
    edges = [0.0] + doc["histogram"]["edges"] + [doc["headline"]["measuredMaxDE2000"]]
    counts = doc["histogram"]["counts"]
    total = sum(counts)
    acc = 0.0
    for i, c in enumerate(counts):
        if not c:
            continue
        lo, hi = edges[i], edges[i + 1]
        far = max(abs(lo - mu), abs(hi - mu))
        acc += c * far * far
    return math.sqrt(acc / total)


def cmd_recheck(args):
    stats_path = args.stats or os.path.join(HERE, "de2000_stats.json")
    if not os.path.exists(stats_path):
        print("ERROR: no stats file at %s (run `de2000_stats.py scan` first)" % stats_path,
              file=sys.stderr)
        return 2
    doc = json.load(open(stats_path))
    db_path = resolve_db_path(args.db)
    conn = open_db(db_path)

    failures = []
    n_checked = 0

    # 1) PER-ROW: the worst table carries published values; recompute each.
    if args.include_worst:
        worst_dev = 0.0
        for w in doc["worst"]:
            got = recheck_row(conn, w["id"])
            if got is None:
                failures.append("row %s missing from dataset" % w["hex"])
                continue
            dq, df = got
            for label, a, b in (("quantized", dq, w["dE2000Quantized"]),
                                ("float", df, w["dE2000Float"])):
                dev = abs(a - b)
                worst_dev = max(worst_dev, dev)
                n_checked += 1
                if dev > args.tol:
                    failures.append("%s %s: published %.6f, independent %.6f (dev %.6f)"
                                    % (w["hex"], label, b, a, dev))
        print("worst[] rechecked per row: %d values, max deviation %.6f (tol %g)"
              % (n_checked, worst_dev, args.tol))

    # 2) AGGREGATE: random rows vs the published distribution.
    if args.n > 0:
        rng = random.Random(args.seed)
        ids = rng.sample(range(TOTAL_ROWS), args.n)
        max_q = doc["headline"]["measuredMaxDE2000"]
        max_f = doc["deltaE2000Float"]["max"]
        dqs, dfs = [], []
        for row_id, filter_text, _loss in fetch_rows(conn, ids):
            try:
                rgb_f = render_chain(parse_chain(filter_text))
            except UnparseableWitness:
                failures.append("row %06x: witness text no longer parses" % row_id)
                continue
            rgb_i = (round(rgb_f[0]), round(rgb_f[1]), round(rgb_f[2]))
            target = target_of(row_id)
            dq, df = delta_e_pair(target, rgb_i), delta_e_pair(target, rgb_f)
            if dq > max_q + args.tol:
                failures.append("row %06x: independent quantized dE %.6f exceeds the "
                                "published maximum %.6f" % (row_id, dq, max_q))
            if df > max_f + args.tol:
                failures.append("row %06x: independent float dE %.6f exceeds the "
                                "published float maximum %.6f" % (row_id, df, max_f))
            dqs.append(dq)
            dfs.append(df)
        m = len(dqs)
        print("random rows independently rescored: %d (seed=%d)" % (m, args.seed))
        if m:
            # 2a) sample mean inside a 6-sigma band derived from the published histogram
            sample_mean = sum(dqs) / m
            pub_mean = doc["deltaE2000Quantized"]["mean"]
            band = 6.0 * histogram_sigma(doc) / math.sqrt(m)
            dev = abs(sample_mean - pub_mean)
            if dev > band:
                failures.append("sample mean %.6f vs published %.6f: deviation %.6f exceeds "
                                "the 6-sigma band +-%.6f from the published histogram"
                                % (sample_mean, pub_mean, dev, band))
            print("  mean check: sample %.6f vs published %.6f (band +-%.6f, deviation %.6f)"
                  % (sample_mean, pub_mean, band, dev))
            # 2b) band shares match the published histogram
            for pb in doc["perceptibilityBands"]:
                below, share = pb["below"], pb["share"] / 100.0
                samp = sum(1 for d in dqs if d < below) / m
                sd = math.sqrt(max(share * (1.0 - share), 1e-12) / m)
                if abs(samp - share) > 6.0 * sd + 1e-9:
                    failures.append("share under %.2f: sample %.5f vs published %.5f "
                                    "(>6 binomial sd %.5f)" % (below, samp, share, sd))
                print("  share under %.2f: sample %.5f vs published %.5f"
                      % (below, samp, share))
        n_checked += 2 * m

    conn.close()
    if failures:
        for f in failures:
            print("INDEPENDENCE FAILURE: %s" % f, file=sys.stderr)
        print("VERDICT: FAIL. A published statistic did not survive independent rechecking")
        return 1
    print("VERDICT: PASS. %d independently recomputed Delta-E values agree with the "
          "published stats (per-row tol %g; distribution checks at 6 sigma)"
          % (n_checked, args.tol))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="recheck_rows_coloraide.py",
        description="Recompute published colorimetric stats using only the spec renderer + coloraide.")
    ap.add_argument("--stats", help="path to de2000_stats.json (default: alongside this script)")
    ap.add_argument("--db", help="path to the dataset artifact (auto-discovered if omitted)")
    ap.add_argument("--n", type=int, default=50000,
                    help="random rows to independently rescore (0 skips)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--tol", type=float, default=1e-3,
                    help="max |published - independent| Delta-E per rechecked worst-row value")
    ap.add_argument("--no-worst", dest="include_worst", action="store_false",
                    help="skip rechecking the worst[] table")
    ap.set_defaults(include_worst=True)
    args = ap.parse_args(argv)
    try:
        return cmd_recheck(args)
    except ArtifactError as exc:
        print("ARTIFACT ERROR: %s" % exc, file=sys.stderr)
        return 2
    except sqlite3.Error as exc:
        print("ARTIFACT ERROR: sqlite: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
