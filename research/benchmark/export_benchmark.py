#!/usr/bin/env python3
"""Benchmark export of the CSS filter covering dataset: one flat record per color.

The dataset artifact is SQLite, and the witness is a CSS filter chain *string*.
Metaheuristic researchers need neither: a fully-solved 6-parameter nonlinear
problem at the 16.7M-instance scale, loadable with pandas/polars/R/awk. This
tool exports the covering dataset as ONE compressed flat file:

  * every one of the 16,777,216 sRGB colors is one record;
  * the record carries the target RGB, the witness parameter vector (the six
    numeric parameters parsed out of the canonical `filter` TEXT — the parsing
    this export exists to publish), and the achieved loss;
  * the stored witness *is* the best-known solution: the best-known objective
    value for instance `id` is the record's `loss` (always < 1, the covering
    threshold), and no better solution is known for any instance.

Every row is re-rendered through the independent verifier
(research/verifier/verify_covering.py) at export time, so the numbers leaving
this script share the covering claim's single trust path. A `verify` mode then
reads the exported FILE back — completeness plus a seeded sample re-verified
against the verifier and the artifact — closing the loop on the bytes
themselves, not just the scan that produced them.

Outputs (all regenerable from the [dataset artifact] alone):

  * hex-to-css-filter-benchmark-<snapshot>.csv.gz  the flat corpus (see the
                           column spec in README.md; header line first)
  * benchmark_manifest.json  column spec, artifact identity (sha256), row
                             count, recomputation tallies, file checksums
  * BENCHMARK_CHECKSUMS.txt  sha256sum-format checksums of the two files above

The export is deterministic: ordered worker merge, gzip with a zeroed
timestamp, float text via repr (shortest exact roundtrip) — byte-identical on
rerun except for the manifest's rerun-local fields (generatedAt,
runtimeSeconds).

Usage:
  python3 export_benchmark.py selftest [-v]
  python3 export_benchmark.py export [--db PATH] [--out-dir DIR] [--jobs N]
                                     [--progress]
  python3 export_benchmark.py verify [--csv PATH] [--db PATH] [--n N]
                                     [--seed S]

License: MIT (tooling), matching the library. Dataset: CC-BY-4.0.
"""

import argparse
import gzip
import hashlib
import json
import multiprocessing
import os
import random
import shutil
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "verifier"))

HERE = os.path.dirname(os.path.abspath(__file__))

from verify_covering import (  # noqa: E402  (path set above, by design)
    LOSS_THRESHOLD,
    SNAPSHOT,
    TOTAL_ROWS,
    ArtifactError,
    UnparseableWitness,
    _blank_stats,
    _merge,
    _tally,
    check_artifact,
    fetch_rows,
    fmt_hex,
    open_db,
    parse_chain,
    render_chain,
    rendered_loss,
    resolve_db_path,
    split_ranges,
    target_of,
)

BENCHMARK_FILENAME = "hex-to-css-filter-benchmark-%s.csv.gz" % SNAPSHOT
MANIFEST_FILENAME = "benchmark_manifest.json"
CHECKSUMS_FILENAME = "BENCHMARK_CHECKSUMS.txt"

# The published dataset snapshot this export is defined against (from the
# release notes / docs/dataset.md). Recorded in the manifest; export does not
# refuse on mismatch (a future data revision gets a new snapshot name), but
# the manifest always carries the identity so consumers can pin it.
DATASET_SHA256 = "bb2d6b5e1696adfa5f6d689fc41d5696868ed4bc37078e35227132f94dd5717a"

# Tolerance for recomputed vs stored `loss`, shared with the verifier's own
# scan default so every published number uses one reading.
STORED_TOL = 1e-9

# The two rows whose stored `loss` column still carries ulp-noise hue from the
# original JS pipeline (documented in the verifier README). Under the default
# tolerance their recomputed loss disagrees with the stored column; the claim
# holds under both readings, and the verifier's scan counts them the same way.
DOCUMENTED_STORED_MISMATCHES = [0x010101, 0xE2E2E2]

# The flat column spec. Order is the contract; see README.md for units.
COLUMNS = [
    "id",
    "r", "g", "b",
    "invert", "sepia", "saturate", "hue_rotate", "brightness", "contrast",
    "loss",
]
HEADER = ",".join(COLUMNS)

COLUMN_DOC = {
    "id": "INTEGER 0..16777215: target color packed 0xRRGGBB (red high byte); hex string is '%06X' % id",
    "r": "INTEGER 0..255: target red channel",
    "g": "INTEGER 0..255: target green channel",
    "b": "INTEGER 0..255: target blue channel",
    "invert": "NUMERIC: invert() amount in percent (the CSS-facing value; verifier divides by 100)",
    "sepia": "NUMERIC: sepia() amount in percent",
    "saturate": "NUMERIC: saturate() amount in percent (commonly tens of thousands)",
    "hue_rotate": "NUMERIC: hue-rotate() angle in degrees",
    "brightness": "NUMERIC: brightness() amount in percent",
    "contrast": "NUMERIC: contrast() amount in percent (may exceed 100)",
    "loss": "NUMERIC: achieved rendered loss of the witness chain (the stored `loss` column; always < %g; metric = sum of absolute RGB and HSL deltas, see docs/dataset.md)" % LOSS_THRESHOLD,
}


# ---------------------------------------------------------------------------
# Formatting (deterministic, exact-roundtrip float text)
# ---------------------------------------------------------------------------

def fmt_param(v):
    """Shortest text that float() reads back bit-identically; '95.0' -> '95'."""
    s = repr(float(v))
    return s[:-2] if s.endswith(".0") else s


def csv_row(row_id, params, loss):
    """One CSV line (no trailing newline) for id/params/loss."""
    tr, tg, tb = target_of(row_id)
    return "%d,%d,%d,%d,%s,%s" % (
        row_id, tr, tg, tb,
        ",".join(fmt_param(p) for p in params),
        repr(float(loss)),
    )


def parse_csv_row(line):
    """Inverse of csv_row: -> (row_id, params, loss). A degraded line (written
    for an unparseable witness) parses to params=None, loss=None.
    Raises ValueError on malformed lines."""
    parts = line.split(",")
    if len(parts) != len(COLUMNS):
        raise ValueError("expected %d fields, got %d" % (len(COLUMNS), len(parts)))
    row_id = int(parts[0])
    if any(p == "" for p in parts[4:]):
        return row_id, None, None
    return row_id, [float(x) for x in parts[4:10]], float(parts[10])


# ---------------------------------------------------------------------------
# Export: full scan -> part files -> deterministic gzip merge
# ---------------------------------------------------------------------------

def _tally_export(stats, row_id, filter_text, stored_loss, stored_tol, emit):
    """Re-derive one row through the verifier and write its CSV line.

    Row status goes through the verifier's own `_tally` — the exact cascade
    the release scan uses — so the export's tallies are the gate's tallies by
    construction, not by re-implementation. Returns the `verify_row` status
    ('pass' | 'fail' | 'unparseable' | 'stored-mismatch').
    `emit(line)` receives the CSV text (or the degraded line for an
    unparseable witness — the id space must stay complete for the readback
    check to even notice).
    """
    status, _recomputed = _tally(stats, row_id, filter_text, stored_loss, stored_tol)
    if status == "unparseable":
        tr, tg, tb = target_of(row_id)
        emit("%d,%d,%d,%d,%s" % (row_id, tr, tg, tb, ",".join([""] * 7)))
    else:
        params = parse_chain(filter_text)
        emit(csv_row(row_id, params, stored_loss))
    return status


def export_range_worker(args):
    """One [lo, hi] id range: stream rows, verify each, write part CSV."""
    db_path, lo, hi, part_path, stored_tol = args
    conn = open_db(db_path)
    try:
        cur = conn.execute(
            "SELECT id, filter, loss FROM color WHERE id BETWEEN ? AND ? ORDER BY id",
            (lo, hi))
        stats = _blank_stats()
        with open(part_path, "w", newline="") as f:
            def emit(line):
                f.write(line + "\n")
            while True:
                rows = cur.fetchmany(20000)
                if not rows:
                    break
                for row_id, filter_text, stored_loss in rows:
                    _tally_export(stats, row_id, filter_text, stored_loss, stored_tol, emit)
        return stats
    finally:
        conn.close()


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def write_checksums_file(path, pairs):
    """sha256sum-format: '<hex>  <name>' (two spaces), one pair per line."""
    with open(path, "w", newline="") as f:
        for digest, name in pairs:
            f.write("%s  %s\n" % (digest, name))


def merge_parts(out_dir, part_paths, gz_path):
    """Ordered gzip merge. mtime=0 and no stored filename -> byte-identical."""
    with open(gz_path, "wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw,
                           compresslevel=9, mtime=0) as gz:
            gz.write((HEADER + "\n").encode("ascii"))
            for part in part_paths:
                with open(part, "rb") as pf:
                    shutil.copyfileobj(pf, gz, 1 << 20)


def build_manifest(out_dir, gz_path, stats, dataset_path, dataset_sha256,
                   generated_at, runtime):
    gz_sha = sha256_file(gz_path)
    manifest_path = os.path.join(out_dir, MANIFEST_FILENAME)
    manifest = {
        "snapshot": SNAPSHOT,
        "title": "CSS filter covering dataset — optimization benchmark export",
        "description": (
            "Fully-solved 6-parameter nonlinear benchmark: one record per sRGB "
            "color (16,777,216 instances). The witness parameter vector is the "
            "best-known solution; `loss` is the achieved objective value under "
            "the dataset's rendered-loss metric; the covering threshold 1 "
            "defines 'solved'."
        ),
        "bestKnown": (
            "The dataset witnesses ARE the best-known solutions: each was "
            "produced by escalating search budgets (6M -> 24M -> 60M "
            "evaluations/color, then two no-cap passes); no better witness is "
            "known for any instance."
        ),
        "format": "CSV (gzip, level 9); header line first; LF newlines; no quoting (no field ever contains a comma or quote)",
        "columns": [{"name": c, "description": COLUMN_DOC[c]} for c in COLUMNS],
        "rowCount": stats["total"],
        "expectedRows": TOTAL_ROWS,
        "lossThreshold": LOSS_THRESHOLD,
        "recomputation": {
            "tool": "research/verifier/verify_covering.py (independent Python verifier)",
            "pass": stats["pass"],
            "fail": stats["fail"],
            "unparseable": stats["unparseable"],
            "storedMismatch": stats["stored_mismatch"],
            "documentedStoredMismatches": ["#%06x" % i for i in DOCUMENTED_STORED_MISMATCHES],
            "maxRecomputedLoss": stats["max_loss"][0],
            "maxRecomputedLossId": "#%06x" % stats["max_loss"][1],
            "meanRecomputedLoss": stats["loss_sum"] / stats["total"],
        },
        "files": {
            BENCHMARK_FILENAME: {
                "bytes": os.path.getsize(gz_path),
                "sha256": gz_sha,
            },
            MANIFEST_FILENAME: {
                "bytes": None,
                "sha256": None,
                "note": "this file; checksum listed after writing in BENCHMARK_CHECKSUMS.txt",
            },
        },
        "dataset": {
            "file": os.path.basename(dataset_path),
            "sha256": dataset_sha256,
            "publishedSha256": DATASET_SHA256,
            "source": "https://github.com/blakegearin/hex-to-css-filter-library/releases/tag/dataset-%s" % SNAPSHOT,
        },
        "generatedAt": generated_at,
        "runtimeSeconds": runtime,
        "license": "CC-BY-4.0 (dataset); MIT (tooling)",
    }
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")
    manifest_sha = sha256_file(manifest_path)
    write_checksums_file(os.path.join(out_dir, CHECKSUMS_FILENAME), [
        (gz_sha, BENCHMARK_FILENAME),
        (manifest_sha, MANIFEST_FILENAME),
    ])
    return manifest, manifest_sha


def export_full(db_path, out_dir, jobs, progress=None, stored_tol=STORED_TOL):
    """The full export. Returns (gz_path, stats, manifest). Exit semantics:
    raises ArtifactError for artifact trouble; the caller turns tallies into
    exit codes (fail/unparseable -> claim violated)."""
    if not os.path.isdir(out_dir):
        raise ArtifactError("no such output directory: %s" % out_dir)
    conn = open_db(db_path)
    try:
        rows = check_artifact(conn)
    finally:
        conn.close()
    if rows != TOTAL_ROWS:
        raise ArtifactError("row count %d != expected %d" % (rows, TOTAL_ROWS))

    started = time.time()
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dataset_sha = sha256_file(db_path)

    if jobs <= 1:
        ranges = [(0, TOTAL_ROWS - 1)]
    else:
        ranges = split_ranges(jobs * 8)
    tmp = tempfile.mkdtemp(prefix="benchmark-export-", dir=out_dir)
    try:
        work = [(db_path, lo, hi, os.path.join(tmp, "part_%05d.csv" % i), stored_tol)
                for i, (lo, hi) in enumerate(ranges)]
        tallies = []
        done = 0
        if jobs <= 1:
            for w in work:
                tallies.append(export_range_worker(w))
                done += tallies[-1]["total"]
                if progress:
                    progress(done)
        else:
            ctx = multiprocessing.get_context("spawn")
            with ctx.Pool(jobs) as pool:
                for t in pool.imap_unordered(export_range_worker, work):
                    tallies.append(t)
                    done += t["total"]
                    if progress:
                        progress(done)
        stats = _merge(tallies)
        if stats["total"] != TOTAL_ROWS:
            raise ArtifactError("exported %d rows, expected %d" % (stats["total"], TOTAL_ROWS))
        part_paths = [w[3] for w in work]
        gz_path = os.path.join(out_dir, BENCHMARK_FILENAME)
        merge_parts(out_dir, part_paths, gz_path)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    manifest, _ = build_manifest(out_dir, gz_path, stats, db_path, dataset_sha,
                                 generated_at, time.time() - started)
    return gz_path, stats, manifest


# ---------------------------------------------------------------------------
# Verify: read the exported FILE back and re-check it through the verifier
# ---------------------------------------------------------------------------

def readback_pass(gz_path, expected_last=TOTAL_ROWS - 1):
    """Stream the exported file once, checking the shape of every row.

    Checks header, field count, strict id sequence (0..expected_last) and
    re-renders EVERY row's parameter columns through the verifier. Yields
    (row_id, params, loss, recomputed); degraded (unparseable-degraded) lines
    parse to params=None, loss=None, recomputed=None."""
    with gzip.open(gz_path, "rt", encoding="ascii", newline="") as f:
        header = f.readline()
        if header.rstrip("\n") != HEADER:
            raise ValueError("bad header: %r" % header[:120])
        prev = None
        for line in f:
            row_id, params, loss = parse_csv_row(line.rstrip("\n"))
            if prev is not None and row_id != prev + 1:
                raise ValueError("id gap: %d after %d" % (row_id, prev))
            prev = row_id
            if params is None:
                recomputed = None
            else:
                recomputed = rendered_loss(render_chain(params), target_of(row_id))
            yield row_id, params, loss, recomputed
        if prev is None:
            raise ValueError("no rows")
        if prev != expected_last:
            raise ValueError("last id %d, expected %d" % (prev, expected_last))


def cmd_verify(args):
    csv_path = args.csv or os.path.join(HERE, "data", BENCHMARK_FILENAME)
    if not os.path.exists(csv_path):
        print("ERROR: no such export file: %s" % csv_path, file=sys.stderr)
        return 2
    db_path = resolve_db_path(args.db)

    digest = sha256_file(csv_path)
    manifest_path = os.path.join(os.path.dirname(csv_path), MANIFEST_FILENAME)
    manifest_sha = None
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            manifest_sha = json.load(f)["files"][BENCHMARK_FILENAME]["sha256"]
    print("file %s" % csv_path)
    print("sha256 %s%s" % (digest, "" if manifest_sha is None else
                           (" (matches manifest)" if digest == manifest_sha
                            else "  *** MISMATCHES manifest %s ***" % manifest_sha)))
    if manifest_sha is not None and digest != manifest_sha:
        print("VERIFY FAIL: export file checksum does not match its manifest", file=sys.stderr)
        return 1

    started = time.time()
    rows_read = 0
    blank_rows = 0
    threshold_failures = []
    recomputed_mismatches = []    # (id, recomputed, csv loss) beyond stored-tol
    sampled = {}                  # id -> (params, loss), for the DB cross-check
    want = None
    if args.n > 0:
        want = set(random.Random(args.seed).sample(range(TOTAL_ROWS), args.n))
    try:
        for row_id, params, loss, recomputed in readback_pass(csv_path):
            rows_read += 1
            if params is None:
                blank_rows += 1
                continue
            if recomputed >= LOSS_THRESHOLD:
                threshold_failures.append(row_id)
            if abs(recomputed - loss) <= STORED_TOL:
                pass
            elif len(recomputed_mismatches) < 10:
                recomputed_mismatches.append((row_id, recomputed, loss))
            if want is not None and row_id in want:
                sampled[row_id] = (params, loss)
    except ValueError as e:
        print("VERIFY FAIL: malformed export: %s" % e, file=sys.stderr)
        return 1
    readback_seconds = time.time() - started

    param_disagreements = []
    loss_disagreements = []
    if want is not None:
        missing = sorted(want - sampled.keys())
        conn = open_db(db_path)
        try:
            for db_id, text, stored in fetch_rows(conn, sorted(want)):
                try:
                    db_params = parse_chain(text)
                except UnparseableWitness:
                    param_disagreements.append((db_id, "unparseable in db"))
                    continue
                csv_params, csv_loss = sampled[db_id]
                if csv_params != db_params:
                    param_disagreements.append((db_id, "params differ"))
                if csv_loss != stored:
                    loss_disagreements.append((db_id, csv_loss, stored))
        finally:
            conn.close()
        print("sampled %d of %d ids (seed %d): cross-checked against the dataset artifact"
              % (len(sampled), len(want), args.seed))
        print("  parameter disagreements: %d" % len(param_disagreements))
        print("  loss disagreements: %d" % len(loss_disagreements))
        print("  sample ids missing from the export: %d" % len(missing))

    print("rows read: %d (expected %d)" % (rows_read, TOTAL_ROWS))
    print("readback re-render (every row): mismatches %d%s"
          % (len(recomputed_mismatches),
             "" if not recomputed_mismatches else "  e.g. %s"
             % ", ".join("%s rc=%.6f csv=%.6f" % (fmt_hex(i), r, c)
                         for i, r, c in recomputed_mismatches[:3])))
    print("threshold failures (recomputed >= 1): %d" % len(threshold_failures))
    print("blank/degraded rows: %d" % blank_rows)
    print("readback runtime: %.1f s" % readback_seconds)

    if rows_read != TOTAL_ROWS:
        print("VERIFY FAIL: row count", file=sys.stderr)
        return 1
    if blank_rows or threshold_failures or param_disagreements or loss_disagreements:
        print("VERIFY FAIL", file=sys.stderr)
        return 1
    if recomputed_mismatches:
        print("note: %d readback recomputations differ from the stored loss beyond %g "
              "(expected: only the two documented stored-loss artifacts %s "
              "— see the verifier README)" % (len(recomputed_mismatches), STORED_TOL,
              ", ".join("#%06x" % i for i in DOCUMENTED_STORED_MISMATCHES)))
    print("VERIFY PASS")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_export(args):
    db_path = resolve_db_path(args.db)
    out_dir = args.out_dir or os.path.join(HERE, "data")
    if args.jobs == 0:
        args.jobs = max(1, os.cpu_count() or 1)
    last = [0, time.time()]
    started = time.time()

    def progress(done):
        if done - last[0] >= 1_000_000:
            now = time.time()
            rate = (done - last[0]) / max(now - last[1], 1e-9)
            print("  %d / %d rows (%.0f rows/s)" % (done, TOTAL_ROWS, rate), flush=True)
            last[0] = done
            last[1] = now

    try:
        gz_path, stats, manifest = export_full(db_path, out_dir, args.jobs,
                                               progress=progress)
    except ArtifactError as e:
        print("ARTIFACT ERROR: %s" % e, file=sys.stderr)
        return 2
    except OSError as e:
        print("OUTPUT ERROR: %s" % e, file=sys.stderr)
        return 2
    print("wrote %s (%d bytes)" % (gz_path, os.path.getsize(gz_path)))
    print("rows: %d | pass %d | fail %d | unparseable %d | stored-mismatch %d"
          % (stats["total"], stats["pass"], stats["fail"],
             stats["unparseable"], stats["stored_mismatch"]))
    print("recomputed loss: max %.10f at %s, mean %.6f"
          % (stats["max_loss"][0], fmt_hex(stats["max_loss"][1]),
             stats["loss_sum"] / stats["total"]))
    print("dataset sha256 %s" % manifest["dataset"]["sha256"])
    print("export sha256 %s" % manifest["files"][BENCHMARK_FILENAME]["sha256"])
    print("manifest %s | checksums %s | runtime %.1f s"
          % (MANIFEST_FILENAME, CHECKSUMS_FILENAME, time.time() - started))
    if stats["fail"] or stats["unparseable"]:
        print("EXPORT FAILED: the covering claim does not hold for this artifact; "
              "the export must not be published", file=sys.stderr)
        return 1
    print("EXPORT OK (every row re-rendered through the verifier)")
    return 0


def add_db_arg(p):
    p.add_argument("--db", metavar="PATH", help="path to the dataset .sqlite3 (default: auto-discover the cached artifact)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)

    p = sub.add_parser("export", help="full flat export (re-verifies every row at export time)")
    add_db_arg(p)
    p.add_argument("--out-dir", metavar="DIR", help="output directory (default: research/benchmark/data)")
    p.add_argument("--jobs", type=int, default=0, help="worker processes; 0 = all cores")
    p.add_argument("--progress", action="store_true", help="per-million progress lines")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("verify", help="read the exported file back: completeness + re-render every row + seeded sample cross-checked against the dataset artifact")
    add_db_arg(p)
    p.add_argument("--csv", metavar="PATH",
                   help="path to the exported .csv.gz (default: research/benchmark/data/%s)" % BENCHMARK_FILENAME)
    p.add_argument("--n", type=int, default=100000, help="sample size for the dataset cross-check; 0 disables sampling (the readback pass still re-renders every row)")
    p.add_argument("--seed", type=int, default=20261007, help="sample seed")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("selftest", help="run the unittest suite")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=lambda a: 0 if unittest.main(
        argv=["selftest"] + (["-v"] if a.verbose else []),
        exit=False, module="__main__").result.wasSuccessful() else 1)

    args = ap.parse_args(argv)
    return args.func(args)


# ---------------------------------------------------------------------------
# Selftests
# ---------------------------------------------------------------------------

def make_synthetic_db(path, rows):
    """rows: list of (id, filter, loss). Creates the canonical schema."""
    import sqlite3
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE color (id INTEGER PRIMARY KEY, filter TEXT, loss REAL)")
    conn.executemany("INSERT INTO color VALUES (?, ?, ?)", rows)
    conn.commit()
    conn.close()


def chain_text(params):
    return ("invert(%s%%) sepia(%s%%) saturate(%s%%) hue-rotate(%sdeg) "
            "brightness(%s%%) contrast(%s%%)" % tuple(fmt_param(p) for p in params))


class TestFormatting(unittest.TestCase):
    def test_param_integer_form(self):
        self.assertEqual(fmt_param(95.0), "95")
        self.assertEqual(fmt_param(95), "95")

    def test_param_fractional_form(self):
        self.assertEqual(fmt_param(26.2), "26.2")
        self.assertEqual(fmt_param(14349.1), "14349.1")

    def test_param_roundtrip_exact(self):
        import random as _r
        rng = _r.Random(1)
        for _ in range(1000):
            v = rng.random() * 30000 * (rng.choice((1, 10)))
            self.assertEqual(float(fmt_param(v)), v)
            self.assertEqual(float(fmt_param(v)), float(repr(v)))

    def test_row_roundtrip(self):
        params = parse_chain(
            "invert(95%) sepia(18%) saturate(20940%) hue-rotate(66deg) "
            "brightness(157%) contrast(74%)")
        line = csv_row(0x42DEAD, params, 0.8793432176)
        self.assertEqual(
            line,
            "4382381,66,222,173,95,18,20940,66,157,74,0.8793432176")
        rid, p2, l2 = parse_csv_row(line)
        self.assertEqual(rid, 0x42DEAD)
        self.assertEqual(p2, params)
        self.assertEqual(l2, 0.8793432176)

    def test_header(self):
        self.assertEqual(HEADER,
                         "id,r,g,b,invert,sepia,saturate,hue_rotate,brightness,contrast,loss")

    def test_checksum_file_format(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "X.txt")
            write_checksums_file(p, [("ab" * 20, "a.csv.gz"), ("cd" * 20, "b.json")])
            with open(p) as f:
                self.assertEqual(f.read(), "%s  a.csv.gz\n%s  b.json\n" % ("ab" * 20, "cd" * 20))


class TestKnownAnswers(unittest.TestCase):
    def test_documented_example_recomputes_to_documented_loss(self):
        # docs/dataset.md: #42dead, loss 0.8793432176
        params = parse_chain(
            "invert(95%) sepia(18%) saturate(20940%) hue-rotate(66deg) "
            "brightness(157%) contrast(74%)")
        loss = rendered_loss(render_chain(params), target_of(0x42DEAD))
        self.assertAlmostEqual(loss, 0.8793432176, places=9)

    def test_fractional_row_parses_to_full_precision(self):
        # The parse-bug lesson: fractional params must parse whole.
        params = parse_chain(
            "invert(26.2%) sepia(78.3%) saturate(4245.5%) hue-rotate(56.9deg) "
            "brightness(241.7%) contrast(98.3%)")
        self.assertEqual(params, [26.2, 78.3, 4245.5, 56.9, 241.7, 98.3])


class TestSyntheticExport(unittest.TestCase):
    N = 256

    def build(self, d):
        rows = []
        losses = {}
        for i in range(self.N):
            params = [((i * 7 + j * 13) % 101) for j in range(5)] + [(i * 3) % 301]
            params[2] = (i * 4099) % 30001
            text = chain_text(params)
            rgb = render_chain(params)
            loss = rendered_loss(rgb, target_of(i))
            rows.append((i, text, loss))
            losses[i] = loss
        db = os.path.join(d, "synthetic.sqlite3")
        make_synthetic_db(db, rows)
        return db, losses

    def test_export_readback_and_verify(self):
        with tempfile.TemporaryDirectory() as d:
            db, losses = self.build(d)
            # Reuse the CLI against a small artifact by pointing TOTAL_ROWS
            # aside: export_full refuses non-full artifacts, so drive the
            # internal pieces directly over one range.
            part = os.path.join(d, "part.csv")
            t = export_range_worker((db, 0, self.N - 1, part, STORED_TOL))
            self.assertEqual(t["total"], self.N)
            self.assertEqual(t["pass"] + t["fail"], self.N)
            self.assertEqual(t["unparseable"], 0)
            self.assertEqual(t["stored_mismatch"], 0)
            gz = os.path.join(d, "b.csv.gz")
            merge_parts(d, [part], gz)
            got = {}
            for row_id, params, loss, recomputed in readback_pass(gz, self.N - 1):
                got[row_id] = (params, loss, recomputed)
            self.assertEqual(len(got), self.N)
            for i in range(self.N):
                params, loss, recomputed = got[i]
                self.assertEqual(loss, losses[i])
                self.assertAlmostEqual(recomputed, losses[i], places=9)
                # params read back re-render to the same loss
                self.assertAlmostEqual(
                    rendered_loss(render_chain(params), target_of(i)), losses[i], places=9)

    def test_degraded_unparseable_row_keeps_id_space_complete(self):
        with tempfile.TemporaryDirectory() as d:
            db, _ = self.build(d)
            import sqlite3
            conn = sqlite3.connect(db)
            conn.execute("UPDATE color SET filter = 'invert(2%)' WHERE id = 5")
            conn.commit()
            conn.close()
            part = os.path.join(d, "part.csv")
            t = export_range_worker((db, 0, self.N - 1, part, STORED_TOL))
            self.assertEqual(t["unparseable"], 1)
            self.assertEqual(t["total"], self.N)
            with open(part) as f:
                lines = f.read().splitlines()
            self.assertEqual(lines[5], "5,0,0,5,,,,,,,")
            rid, params, loss = parse_csv_row(lines[5])
            self.assertEqual(rid, 5)
            self.assertIsNone(params)
            self.assertIsNone(loss)


class TestVerifyHelpers(unittest.TestCase):
    def test_readback_rejects_bad_header(self):
        with tempfile.TemporaryDirectory() as d:
            gz = os.path.join(d, "x.csv.gz")
            with gzip.open(gz, "wt") as f:
                f.write("wrong,header\n")
            with self.assertRaises(ValueError):
                list(readback_pass(gz))


if __name__ == "__main__":
    sys.exit(main())
