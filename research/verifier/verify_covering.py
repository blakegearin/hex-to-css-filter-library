#!/usr/bin/env python3
"""Independent verifier for the CSS Filter Covering Dataset claim.

CLAIM: for every one of the 16,777,216 sRGB colors the dataset stores a
six-function CSS filter chain (the witness) which, applied to black, renders
the target color with a *rendered loss* under 1.

This tool re-derives that claim from the published SQLite artifact using only
the Python standard library. It is written from the W3C Filter Effects Level 1
definitions, not ported from the JavaScript search pipeline:

  * Filter functions operate directly on sRGB-encoded components
    (filter-effects-1 §5: "Filter Functions must operate in the sRGB color
    space").
  * Each function in the chain is a separate filter primitive; every
    primitive's RGBA result is clamped to the allowable range
    (§9.1: "The RGBA result from each filter primitive will be clamped into
    the allowable ranges..."), so clamping happens after each function, in
    float precision (no rounding to 8-bit channels; that is the dataset
    doc's "full floating-point precision, without rounding").
  * sepia() is the matrix of §13.1.2. saturate() and hue-rotate() are the
    feColorMatrix matrices of §9.6 (referenced from §13.1.3/§13.1.4), with
    luminance coefficients 0.213/0.715/0.072.
  * invert() is feComponentTransfer type=table tableValues="[amount]
    (1 - [amount])" (§13.1.5); a 2-entry table interpolates to the linear
    function F(c) = amount + c * (1 - 2*amount).
  * brightness()/contrast() are linear transfers with slope=amount and
    intercept=0 / -(0.5*amount)+0.5 (§13.1.7, §13.1.8).

The rendered loss of a row is |ΔR|+|ΔG|+|ΔB| (on 0-255) plus |ΔH|+|ΔS|+|ΔL|
(classic RGB->HSL, each on 0-100, achromatic colors read as H=0, S=0).
"Achromatic" is read against float noise: three channels that agree within
1e-9/255 quantize to one and the same gray in any browser, so they read as
H=0, S=0 -- otherwise the hue of a knife-edge gray would be decided by the
last bit of the platform's sin/cos, and a browser-perfect witness could fail
on a rounding detail instead of on real color error. See _ACHROMATIC_EPS.

Verification design note: parsing a witness can fail, and a failed parse must
never masquerade as a pass. This tool uses one fully-anchored regex that
accepts integer AND fractional parameters and reports three disjoint
counters: passed, failed (loss >= 1) and unparseable. An early JavaScript
scan in this project used /(\d+)(?:%|deg)/g, which silently parsed
"invert(26.2%)" as invert(2%) -- a faked verification of exactly the five
fractional-parameter rows. That is the bug class this counter design exists
to make impossible.

Spec: https://www.w3.org/TR/filter-effects-1/
License: MIT (tooling), matching the library.
"""

import argparse
import json
import math
import multiprocessing
import os
import random
import re
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import zlib

TOTAL_ROWS = 16777216
LOSS_THRESHOLD = 1.0
SNAPSHOT = "2026.10.07"
DB_FILENAME = "hex-to-css-filter-covering-dataset-%s.sqlite3" % SNAPSHOT

# Chain grammar: six functions, this exact order, this exact spacing, each
# taking one non-negative number (integer or decimal fraction) with its
# mandatory unit. Anchored at both ends; nothing else is a witness.
_PARAM = r"\d+(?:\.\d+)?"
CHAIN_RE = re.compile(
    r"^invert\((" + _PARAM + r")%\) sepia\((" + _PARAM + r")%\) saturate\((" + _PARAM + r")%\) "
    r"hue-rotate\((" + _PARAM + r")deg\) brightness\((" + _PARAM + r")%\) contrast\((" + _PARAM + r")%\)$"
)


class UnparseableWitness(Exception):
    pass


def parse_chain(text):
    """Return six float parameters (amounts, degrees) or raise UnparseableWitness."""
    if not isinstance(text, str):
        raise UnparseableWitness("witness is not text: %r" % type(text))
    m = CHAIN_RE.match(text)
    if m is None:
        raise UnparseableWitness("no match: %r" % text)
    return [float(g) for g in m.groups()]


def _clamp255(x):
    if x < 0.0:
        return 0.0
    if x > 255.0:
        return 255.0
    return x


def _invert(c, amount):
    # §13.1.5: type=table, tableValues="[amount] (1 - [amount])"; two-entry
    # tables interpolate linearly: F(v) = amount + v * (1 - 2*amount), v in 0..1.
    return _clamp255((amount + (c / 255.0) * (1.0 - 2.0 * amount)) * 255.0)


def _sepia(c, amount):
    # §13.1.2 matrix (rows R,G,B), amount in 0..1 semantics (may exceed).
    k = 1.0 - amount
    r, g, b = c
    return (
        _clamp255(r * (0.393 + 0.607 * k) + g * (0.769 - 0.769 * k) + b * (0.189 - 0.189 * k)),
        _clamp255(r * (0.349 - 0.349 * k) + g * (0.686 + 0.314 * k) + b * (0.168 - 0.168 * k)),
        _clamp255(r * (0.272 - 0.272 * k) + g * (0.534 - 0.534 * k) + b * (0.131 + 0.869 * k)),
    )


def _saturate(c, amount):
    # §9.6 type=saturate matrix (referenced by §13.1.3).
    s = amount
    r, g, b = c
    return (
        _clamp255(r * (0.213 + 0.787 * s) + g * (0.715 - 0.715 * s) + b * (0.072 - 0.072 * s)),
        _clamp255(r * (0.213 - 0.213 * s) + g * (0.715 + 0.285 * s) + b * (0.072 - 0.072 * s)),
        _clamp255(r * (0.213 - 0.213 * s) + g * (0.715 - 0.715 * s) + b * (0.072 + 0.928 * s)),
    )


def _hue_rotate(c, deg):
    # §9.6 type=hueRotate matrix (referenced by §13.1.4).
    rad = (deg / 180.0) * math.pi
    cos = math.cos(rad)
    sin = math.sin(rad)
    r, g, b = c
    return (
        _clamp255(
            r * (0.213 + cos * 0.787 - sin * 0.213)
            + g * (0.715 - cos * 0.715 - sin * 0.715)
            + b * (0.072 - cos * 0.072 + sin * 0.928)
        ),
        _clamp255(
            r * (0.213 - cos * 0.213 + sin * 0.143)
            + g * (0.715 + cos * 0.285 + sin * 0.140)
            + b * (0.072 - cos * 0.072 - sin * 0.283)
        ),
        _clamp255(
            r * (0.213 - cos * 0.213 - sin * 0.787)
            + g * (0.715 - cos * 0.715 + sin * 0.715)
            + b * (0.072 + cos * 0.928 + sin * 0.072)
        ),
    )


def _brightness(c, amount):
    # §13.1.7: linear, slope=amount, intercept=0.
    return tuple(_clamp255(x * amount) for x in c)


def _contrast(c, amount):
    # §13.1.8: linear, slope=amount, intercept=-(0.5*amount)+0.5.
    intercept = -(0.5 * amount) + 0.5
    return tuple(_clamp255(x * amount + intercept * 255.0) for x in c)


def render_chain(params):
    """Apply the witness chain to black in float precision; return (r, g, b) in 0..255."""
    c = (0.0, 0.0, 0.0)
    c = tuple(_invert(x, params[0] / 100.0) for x in c)
    c = _sepia(c, params[1] / 100.0)
    c = _saturate(c, params[2] / 100.0)
    c = _hue_rotate(c, params[3])
    c = _brightness(c, params[4] / 100.0)
    c = _contrast(c, params[5] / 100.0)
    return c


# Channel spread below which a rendered color reads as achromatic. A witness
# chain that lands on neutral gray produces three channels that differ only by
# last-bit float noise (verified: <= ~10 ulps, i.e. <= ~1e-12 on 0..255);
# computing a hue for those divides by noise and can invent |ΔH| up to 100
# loss units for colors the browser renders as identical 8-bit grays. The two
# knife-edge rows #a1a1a1 and #e3e3e3 in snapshot 2026.10.07 differ across
# libms by exactly one ulp. 1e-9/255 is orders of magnitude above arithmetic
# noise yet far below any color difference that matters for the threshold.
_ACHROMATIC_EPS = 1e-9 / 255.0


def rgb_to_hsl(r, g, b):
    """Classic RGB->HSL on 0..255 floats; returns (h, s, l) each on 0..100.

    Achromatic colors (channels agreeing within _ACHROMATIC_EPS) read as
    h = 0, s = 0."""
    r0, g0, b0 = r / 255.0, g / 255.0, b / 255.0
    mx = max(r0, g0, b0)
    mn = min(r0, g0, b0)
    lightness = (mx + mn) / 2.0
    if mx - mn <= _ACHROMATIC_EPS:
        return (0.0, 0.0, lightness * 100.0)
    delta = mx - mn
    saturation = delta / (2.0 - mx - mn) if lightness > 0.5 else delta / (mx + mn)
    if mx == r0:
        hue = (g0 - b0) / delta + (6.0 if g0 < b0 else 0.0)
    elif mx == g0:
        hue = (b0 - r0) / delta + 2.0
    else:
        hue = (r0 - g0) / delta + 4.0
    hue /= 6.0
    return (hue * 100.0, saturation * 100.0, lightness * 100.0)


def rendered_loss(rgb, target):
    """Mixed RGB+HSL rendered loss of float color `rgb` against 0..255 int target."""
    tr, tg, tb = target
    h, s, l = rgb_to_hsl(*rgb)
    th, ts, tl = rgb_to_hsl(float(tr), float(tg), float(tb))
    return (
        abs(rgb[0] - tr) + abs(rgb[1] - tg) + abs(rgb[2] - tb)
        + abs(h - th) + abs(s - ts) + abs(l - tl)
    )


def target_of(row_id):
    return ((row_id >> 16) & 255, (row_id >> 8) & 255, row_id & 255)


def verify_row(row_id, filter_text, stored_loss=None, stored_tol=1e-9):
    """The one row-level check, shared by every mode.
    Returns (status, loss) where status is one of
    'pass' | 'fail' | 'unparseable' | 'stored-mismatch'."""
    try:
        params = parse_chain(filter_text)
    except UnparseableWitness:
        return ("unparseable", None)
    rgb = render_chain(params)
    loss = rendered_loss(rgb, target_of(row_id))
    if loss >= LOSS_THRESHOLD:
        return ("fail", loss)
    if stored_loss is not None and stored_loss == stored_loss:  # skip NULL/NaN
        if abs(loss - stored_loss) > stored_tol:
            return ("stored-mismatch", loss)
    return ("pass", loss)


# ---------------------------------------------------------------------------
# Database scanning
# ---------------------------------------------------------------------------

def open_db(path):
    """Open the artifact read-only. Never creates: a missing path is an
    ArtifactError, and the write-capable fallback only ever sees a path that
    already exists."""
    if not os.path.exists(path):
        raise ArtifactError("no such file: %s" % path)
    try:
        conn = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
        conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
    except sqlite3.Error:
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA query_only = ON")
    return conn


def check_artifact(conn):
    """Artifact-level integrity. Raises ArtifactError on schema trouble."""
    row = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'color'").fetchone()
    sql = row[0] if row else ""
    if row is None or "id INTEGER PRIMARY KEY" not in sql or "filter TEXT" not in sql or "loss REAL" not in sql:
        raise ArtifactError("not a covering-dataset artifact: expected "
                            "CREATE TABLE color (id INTEGER PRIMARY KEY, filter TEXT, loss REAL), got %r"
                            % (row and row[0],))
    return conn.execute("SELECT count(*) FROM color").fetchone()[0]


class ArtifactError(Exception):
    pass


def scan_range_worker(args):
    """One [lo, hi] id range of the full scan. Runs in a worker process."""
    db_path, lo, hi, stored_tol = args
    conn = open_db(db_path)
    cur = conn.execute("SELECT id, filter, loss FROM color WHERE id BETWEEN ? AND ? ORDER BY id", (lo, hi))
    stats = _blank_stats()
    prev_id = None
    while True:
        rows = cur.fetchmany(10000)
        if not rows:
            break
        for row_id, filter_text, stored_loss in rows:
            if prev_id is not None and row_id != prev_id + 1:
                stats["gaps"] += 1
            prev_id = row_id
            _tally(stats, row_id, filter_text, stored_loss, stored_tol)
    conn.close()
    return stats


def _blank_stats():
    return {
        "total": 0,
        "pass": 0,
        "fail": 0,
        "unparseable": 0,
        "stored_mismatch": 0,
        "max_loss": (float("-inf"), None),
        "loss_sum": 0.0,
        "fail_examples": [],
        "unparse_examples": [],
        "mismatch_examples": [],
        "gaps": 0,
    }


def _tally(stats, row_id, filter_text, stored_loss, stored_tol):
    status, loss = verify_row(row_id, filter_text, stored_loss, stored_tol)
    stats["total"] += 1
    if status == "unparseable":
        stats["unparseable"] += 1
        if len(stats["unparse_examples"]) < 10:
            stats["unparse_examples"].append([row_id, str(filter_text)[:200]])
        return
    if loss > stats["max_loss"][0]:
        stats["max_loss"] = (loss, row_id)
    stats["loss_sum"] += loss
    if status == "fail":
        stats["fail"] += 1
        if len(stats["fail_examples"]) < 10:
            stats["fail_examples"].append([row_id, loss])
    elif status == "stored-mismatch":
        stats["stored_mismatch"] += 1
        if len(stats["mismatch_examples"]) < 10:
            stats["mismatch_examples"].append([row_id, loss, stored_loss])
    else:
        stats["pass"] += 1


def scan_ranges(db_path, ranges, stored_tol=1e-9, jobs=1, progress=None):
    """Scan explicit id ranges; multiprocessing when jobs > 1. Aggregates stats."""
    work = [(db_path, lo, hi, stored_tol) for lo, hi in ranges]
    results = []
    if jobs <= 1:
        for i, w in enumerate(work):
            results.append(scan_range_worker(w))
            if progress:
                progress(sum(r["total"] for r in results))
    else:
        ctx = multiprocessing.get_context("spawn")
        with ctx.Pool(jobs) as pool:
            done = 0
            for r in pool.imap_unordered(scan_range_worker, work):
                results.append(r)
                done += r["total"]
                if progress:
                    progress(done)
    return _merge(results)


def _merge(stats_list):
    out = _blank_stats()
    for s in stats_list:
        for k in ("total", "pass", "fail", "unparseable", "stored_mismatch", "gaps"):
            out[k] += s[k]
        out["loss_sum"] += s["loss_sum"]
        if s["max_loss"][1] is not None and s["max_loss"][0] > out["max_loss"][0]:
            out["max_loss"] = s["max_loss"]
        for key in ("fail_examples", "unparse_examples", "mismatch_examples"):
            out[key] = (out[key] + s[key])[:10]
    return out


def split_ranges(parts):
    """Split [0, 2^24) id space into `parts` contiguous ranges of near-equal size."""
    step = -(-TOTAL_ROWS // parts)
    ranges = []
    lo = 0
    while lo < TOTAL_ROWS:
        hi = min(TOTAL_ROWS - 1, lo + step - 1)
        ranges.append((lo, hi))
        lo = hi + 1
    return ranges


# ---------------------------------------------------------------------------
# CLI: scan mode (the release gate)
# ---------------------------------------------------------------------------

def _fmt_hex(row_id):
    return "#%06x" % row_id if row_id is not None else "-"


def cmd_scan(args):
    db_path = resolve_db_path(args.db)
    size = os.path.getsize(db_path)
    conn = open_db(db_path)
    try:
        rows = check_artifact(conn)
    finally:
        conn.close()
    if args.expect_rows is not None and rows != args.expect_rows:
        print("ARTIFACT ERROR: row count %d != expected %d" % (rows, args.expect_rows), file=sys.stderr)
        return 2
    if args.jobs == 0:
        args.jobs = max(1, (os.cpu_count() or 1))
    if args.jobs > 1:
        ranges = split_ranges(args.jobs * 8)
    else:
        ranges = [(0, TOTAL_ROWS - 1)]
    t0 = time.monotonic()
    state = {"last": t0, "last_done": 0}

    def progress(done):
        now = time.monotonic()
        if now - state["last"] > 2.0:
            dt = now - state["last"]
            rate = (done - state["last_done"]) / max(dt, 1e-9)
            state["last"], state["last_done"] = now, done
            print("  ... %d rows (%.1f%%), ~%.0f rows/s" % (done, 100.0 * done / TOTAL_ROWS, rate),
                  file=sys.stderr)

    stats = scan_ranges(db_path, ranges, args.stored_tol, jobs=args.jobs,
                        progress=progress if args.progress else None)
    elapsed = time.monotonic() - t0

    verdict = "PASS"
    exit_code = 0
    if stats["fail"] or stats["unparseable"] or (args.strict_stored and stats["stored_mismatch"]):
        verdict = "FAIL"
        exit_code = 1
    if stats["gaps"]:
        print("WARNING: %d gaps in the id sequence" % stats["gaps"], file=sys.stderr)

    mean = stats["loss_sum"] / stats["total"] if stats["total"] else float("nan")
    if args.json:
        out = {
            "db": db_path,
            "dbSize": size,
            "rows": rows,
            "processed": stats["total"],
            "passed": stats["pass"],
            "failed": stats["fail"],
            "unparseable": stats["unparseable"],
            "storedMismatches": stats["stored_mismatch"],
            "maxRecomputedLoss": stats["max_loss"][0],
            "maxLossId": stats["max_loss"][1],
            "meanRecomputedLoss": mean,
            "runtimeSeconds": round(elapsed, 3),
            "jobs": args.jobs,
            "verdict": verdict,
            "failExamples": stats["fail_examples"],
            "unparseExamples": stats["unparse_examples"],
            "mismatchExamples": stats["mismatch_examples"],
        }
        print(json.dumps(out, indent=2))
    else:
        print("CSS filter covering-claim verifier")
        print("  db:              %s (%d bytes)" % (db_path, size))
        print("  rows in table:   %d" % rows)
        print("  rows processed:  %d" % stats["total"])
        print("  passed:          %d" % stats["pass"])
        print("  failures:        %d   (recomputed rendered loss >= 1)" % stats["fail"])
        print("  unparseable:     %d   (witness text rejected; NEVER counted as passes)" % stats["unparseable"])
        print("  stored-loss mismatches: %d   (|recomputed - stored| > %g)" % (stats["stored_mismatch"], args.stored_tol))
        print("  max recomputed loss: %.10f at %s" % (stats["max_loss"][0], _fmt_hex(stats["max_loss"][1])))
        print("  mean recomputed loss: %.5f" % mean)
        print("  runtime: %.1f s with %d job(s)" % (elapsed, args.jobs))
        for label, examples in (("failing rows", stats["fail_examples"]),
                                ("unparseable witnesses", stats["unparse_examples"]),
                                ("mismatched stored loss", stats["mismatch_examples"])):
            if examples:
                print("  first %s:" % label)
                for ex in examples[:5]:
                    print("    %s" % (_fmt_hex(ex[0]) + ": " + ", ".join(str(x) for x in ex[1:])))
        print("VERDICT: %s — every row's witness re-renders from the spec matrices to loss < %g" % (verdict, LOSS_THRESHOLD))
    return exit_code


def resolve_db_path(explicit):
    candidates = []
    if explicit:
        candidates.append(explicit)
        if not os.path.exists(explicit):
            print("ERROR: no such database file: %s" % explicit, file=sys.stderr)
            sys.exit(2)
        return explicit
    home = os.path.expanduser("~")
    candidates.append(os.path.join(home, "Library", "Caches", "hex-to-css-filter-library",
                                   "datasets", SNAPSHOT, DB_FILENAME))
    candidates.append(os.path.join(home, ".cache", "hex-to-css-filter-library", "datasets",
                                   SNAPSHOT, DB_FILENAME))
    candidates.append(os.path.join(home, "AppData", "Local", "hex-to-css-filter-library",
                                   "datasets", SNAPSHOT, DB_FILENAME))
    candidates.append(DB_FILENAME)
    candidates.append(os.path.join(os.getcwd(), DB_FILENAME))
    for c in candidates:
        if os.path.exists(c):
            return c
    print("ERROR: dataset artifact not found. Pass --db /path/to/%s or download it:\n"
          "  curl -sSfL -O https://github.com/blakegearin/hex-to-css-filter-library/releases/"
          "download/dataset-%s/%s.gz\n"
          "  curl -sSfL -O https://github.com/blakegearin/hex-to-css-filter-library/releases/"
          "download/dataset-%s/CHECKSUMS.txt\n"
          "  sha256sum -c CHECKSUMS.txt && gunzip %s.gz"
          % (DB_FILENAME, SNAPSHOT, DB_FILENAME, SNAPSHOT, DB_FILENAME), file=sys.stderr)
    sys.exit(2)


# ---------------------------------------------------------------------------
# CLI: sample / row modes
# ---------------------------------------------------------------------------

def fetch_rows(conn, ids, batch=500):
    """Yield (id, filter, loss) for the given ids, batched through the PK index."""
    for i in range(0, len(ids), batch):
        chunk = ids[i:i + batch]
        for row in conn.execute("SELECT id, filter, loss FROM color WHERE id IN (%s)"
                                % ",".join("?" * len(chunk)), chunk):
            yield row


def cmd_sample(args):
    db_path = resolve_db_path(args.db)
    conn = open_db(db_path)
    rng = random.Random(args.seed)
    ids = rng.sample(range(TOTAL_ROWS), args.n)
    stats = _blank_stats()
    for row_id, filter_text, stored_loss in fetch_rows(conn, ids):
        _tally(stats, row_id, filter_text, stored_loss, args.stored_tol)
    conn.close()
    mean = stats["loss_sum"] / stats["total"] if stats["total"] else float("nan")
    print("sampled %d random rows (seed=%d): pass=%d fail=%d unparseable=%d stored-mismatch=%d"
          % (stats["total"], args.seed, stats["pass"], stats["fail"], stats["unparseable"],
             stats["stored_mismatch"]))
    print("  max recomputed loss: %.10f at %s | mean: %.5f"
          % (stats["max_loss"][0], _fmt_hex(stats["max_loss"][1]), mean))
    return 1 if (stats["fail"] or stats["unparseable"]) else 0


def cmd_row(args):
    db_path = resolve_db_path(args.db)
    text = args.color
    if text.startswith("#"):
        text = text[1:]
    try:
        row_id = int(text, 16)
    except ValueError:
        print("ERROR: pass a hex color like #42dead", file=sys.stderr)
        return 2
    conn = open_db(db_path)
    row = conn.execute("SELECT filter, loss FROM color WHERE id = ?", (row_id,)).fetchone()
    conn.close()
    if row is None:
        print("ERROR: id not in dataset: %s" % args.color, file=sys.stderr)
        return 2
    filter_text, stored_loss = row
    status, loss = verify_row(row_id, filter_text, stored_loss)
    if status == "unparseable":
        print("%s UNPARSEABLE witness: %r" % (_fmt_hex(row_id), filter_text))
        return 1
    rgb = render_chain(parse_chain(filter_text))
    print("color   %s  target rgb %d %d %d" % (_fmt_hex(row_id), *target_of(row_id)))
    print("witness %s" % filter_text)
    print("rendered float rgb  %.6f %.6f %.6f" % rgb)
    h, s, l = rgb_to_hsl(*rgb)
    print("rendered hsl 0-100  %.6f %.6f %.6f" % (h, s, l))
    verdict = {"pass": "PASS", "fail": "FAIL", "stored-mismatch": "PASS (stored column disagrees beyond tolerance)"}[status]
    print("recomputed loss %.10f | stored loss %s | threshold %g | %s"
          % (loss, "NULL" if stored_loss is None else "%.10f" % stored_loss,
             LOSS_THRESHOLD, verdict))
    return 0 if status in ("pass", "stored-mismatch") else 1


# ---------------------------------------------------------------------------
# CLI: golden mode — headless Chrome pixel sampling
# ---------------------------------------------------------------------------

GOLDEN_KNOWN_IDS = [
    0x000000, 0xFFFFFF, 0x42DEAD, 0x000001, 0xFEFEFE,
    0xFBFC02, 0xFBFC03, 0xFBFC1F, 0xFCFD02, 0xFCFD03,  # the fractional-parameter rows
    0x000100, 0x010000, 0x00FF7F, 0xFF00FF, 0x123456,
    0xA1A1A1, 0xE3E3E3,  # knife-edge neutrals (ulp-level achromatic boundary)
    0x010101, 0xE2E2E2,  # the two rows whose stored loss carries old-pipeline ulp hue
]
GOLDEN_KNOWN_IDS += list(range(16777216 - 100, 16777216))  # near-white corner
GOLDEN_KNOWN_IDS += [(i * 8388607 + 12345) % TOTAL_ROWS for i in range(12)]


def decode_png(path):
    """Decode an 8-bit non-interlaced PNG to a list of rows of (r, g, b) tuples."""
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG: %s" % path)
    pos = 8
    width = height = depth = ctype = interlace = None
    idat = bytearray()
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        ctype_chunk = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        (crc,) = struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])
        if crc != (zlib.crc32(ctype_chunk + chunk) & 0xFFFFFFFF):
            raise ValueError("PNG CRC mismatch in %s chunk" % ctype_chunk)
        pos += 12 + length
        if ctype_chunk == b"IHDR":
            width, height, depth, ctype, _comp, _filt, interlace = struct.unpack(">IIBBBBB", chunk)
            if depth != 8 or interlace != 0 or ctype not in (2, 6):
                raise ValueError("unsupported PNG (depth=%s color=%s interlace=%s)" % (depth, ctype, interlace))
        elif ctype_chunk == b"IDAT":
            idat += chunk
        elif ctype_chunk == b"IEND":
            break
    if width is None:
        raise ValueError("no IHDR in %s" % path)
    bpp = 3 if ctype == 2 else 4
    raw = zlib.decompress(bytes(idat))
    stride = width * bpp
    if len(raw) != (stride + 1) * height:
        raise ValueError("PNG data size mismatch")
    rows_out = []
    prev = bytearray(stride)
    pos = 0
    for _y in range(height):
        ft = raw[pos]
        line = bytearray(raw[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        if ft == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif ft == 3:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif ft == 4:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                above = prev[i]
                upper_left = prev[i - bpp] if i >= bpp else 0
                p = left + above - upper_left
                pl, pa, pu = abs(p - left), abs(p - above), abs(p - upper_left)
                predict = left if (pl <= pa and pl <= pu) else (above if pa <= pu else upper_left)
                line[i] = (line[i] + predict) & 255
        elif ft != 0:
            raise ValueError("unknown PNG row filter %d" % ft)
        rows_out.append(bytes(line))
        prev = line
    return width, height, bpp, rows_out


GOLDEN_GRID_COLS = 16


def build_golden_html(entries, cell=8):
    """entries: list of (filter_text, params, target_rgb). Laid out in a
    GOLDEN_GRID_COLS column grid; each cell is a `cell x cell` black div with
    the witness filter applied."""
    cols = GOLDEN_GRID_COLS
    rows = -(-len(entries) // cols)
    parts = [
        "<!doctype html><meta charset=utf-8><style>",
        "html,body{margin:0;padding:0;background:#000}",
        "div{position:absolute}",
        "</style>",
    ]
    for i, (filter_text, _params, _target) in enumerate(entries):
        x = (i % cols) * cell
        y = (i // cols) * cell
        parts.append('<div style="left:%dpx;top:%dpx;width:%dpx;height:%dpx;background:#000;filter:%s"></div>'
                     % (x, y, cell, cell, filter_text))
    return cols * cell, rows * cell, "\n".join(parts)


def chrome_binary(override):
    if override:
        return override
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chrome"),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def cmd_golden(args):
    db_path = resolve_db_path(args.db)
    chrome = chrome_binary(args.chrome)
    if chrome is None:
        print("ERROR: no Chrome/Chromium binary found; pass --chrome /path", file=sys.stderr)
        return 2
    conn = open_db(db_path)
    ids = list(GOLDEN_KNOWN_IDS)
    if args.n:
        rng = random.Random(args.seed)
        ids += rng.sample(range(TOTAL_ROWS), args.n)
    picked = list(dict.fromkeys(ids))  # order-preserving dedupe
    rows = {rid: ftxt for rid, ftxt, _loss in fetch_rows(conn, picked, batch=1000)}
    conn.close()
    entries = []
    unparseable = 0
    for rid in picked:
        ftxt = rows.get(rid)
        if ftxt is None:
            continue
        try:
            params = parse_chain(ftxt)
        except UnparseableWitness:
            unparseable += 1
            continue
        entries.append((ftxt, params, target_of(rid)))
    if unparseable:
        print("ERROR: %d golden witnesses unparseable" % unparseable, file=sys.stderr)
        return 1

    width_px, height_px, html = build_golden_html(entries, cell=args.cell)
    tmp = tempfile.mkdtemp(prefix="hex-golden-")
    html_path = os.path.join(tmp, "golden.html")
    png_path = os.path.join(tmp, "golden.png")
    with open(html_path, "w") as fh:
        fh.write(html)
    cmd = [
        chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run",
        "--hide-scrollbars", "--force-color-profile=srgb", "--force-device-scale-factor=1",
        "--disable-extensions", "--user-data-dir=%s" % os.path.join(tmp, "profile"),
        "--window-size=%d,%d" % (width_px, height_px),
        "--screenshot=%s" % png_path,
        "file://%s" % html_path,
    ]
    # Chrome writes the screenshot then often refuses to exit; poll for the
    # file to appear and stabilize, then reap the process.
    log = open(os.path.join(tmp, "chrome.log"), "wb")
    proc = subprocess.Popen(cmd, stdout=log, stderr=log)
    deadline = time.monotonic() + args.chrome_timeout
    png_ready = False
    while time.monotonic() < deadline:
        if proc.poll() is not None and not os.path.exists(png_path):
            break
        if os.path.exists(png_path) and os.path.getsize(png_path) > 0:
            size1 = os.path.getsize(png_path)
            time.sleep(0.3)
            if os.path.getsize(png_path) == size1:
                png_ready = True
                break
        time.sleep(0.1)
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    log.close()
    if not png_ready:
        print("ERROR: Chrome produced no screenshot within %ds (see %s)"
              % (args.chrome_timeout, os.path.join(tmp, "chrome.log")), file=sys.stderr)
        return 2
    w, h, bpp, img = decode_png(png_path)
    if w != width_px or h != height_px:
        print("ERROR: screenshot %dx%d != window %dx%d" % (w, h, width_px, height_px), file=sys.stderr)
        return 2

    cell = args.cell
    worst_dev = (0.0, None, None, None)
    deviation_bands = {}
    exceed = []
    for i, (_ftxt, params, _target) in enumerate(entries):
        rgb = render_chain(params)
        px = (((i % GOLDEN_GRID_COLS) * cell + cell // 2),
              ((i // GOLDEN_GRID_COLS) * cell + cell // 2))
        row_bytes = img[px[1]]
        off = px[0] * bpp
        got = (row_bytes[off], row_bytes[off + 1], row_bytes[off + 2])
        for ch in range(3):
            d = abs(rgb[ch] - got[ch])
            deviation_bands[int(math.floor(d))] = deviation_bands.get(int(math.floor(d)), 0) + 1
            if d > worst_dev[0]:
                worst_dev = (d, i, got, tuple(round(x, 3) for x in rgb))
            if d > args.tol:
                exceed.append((i, ch, rgb[ch], got[ch], d))
    print("golden set: %d witnesses rendered by %s" % (len(entries), os.path.basename(chrome)))
    print("  Chrome version: %s" % subprocess.run([chrome, "--version"], stdout=subprocess.PIPE).stdout.decode().strip())
    print("  channel deviation |verifier float - browser pixel|, floor(bands): %s"
          % " ".join("%d:%d" % (k, deviation_bands[k]) for k in sorted(deviation_bands)))
    print("  worst deviation %.3f on witness %d (browser %s vs verifier %s)"
          % (worst_dev[0], worst_dev[1], worst_dev[2], worst_dev[3]))
    if exceed:
        print("  EXCEEDED tolerance %.2f on %d channel(s), first 10:" % (args.tol, len(exceed)))
        for e in exceed[:10]:
            print("    witness %d ch%d verifier %.4f browser %d dev %.4f" % (e[0], e[1], e[2], e[3], e[4]))
        print("VERDICT: FAIL — verifier arithmetic disagrees with the browser beyond rounding")
        return 1
    print("VERDICT: PASS — verifier matches real browser output within %.2f/255 per channel" % args.tol)
    return 0


# ---------------------------------------------------------------------------
# CLI: selftest mode — known-answer + parser + synthetic scan tests
# ---------------------------------------------------------------------------

class TestParser(unittest.TestCase):
    def test_valid_integer_chain(self):
        p = parse_chain("invert(95%) sepia(18%) saturate(20940%) hue-rotate(66deg) "
                        "brightness(157%) contrast(74%)")
        self.assertEqual(p, [95.0, 18.0, 20940.0, 66.0, 157.0, 74.0])

    def test_valid_fractional_chain(self):
        p = parse_chain("invert(26.2%) sepia(78.3%) saturate(4245.5%) hue-rotate(56.9deg) "
                        "brightness(241.7%) contrast(98.3%)")
        self.assertEqual(p, [26.2, 78.3, 4245.5, 56.9, 241.7, 98.3])

    def test_the_regex_bug_regression(self):
        # The old /(\d+)(?:%|deg)/g scan read "invert(26.2%)" as 2%. The strict
        # parser must read it as 26.2%.
        import re as _re
        legacy = [int(m[1]) for m in _re.finditer(r"(\d+)(?:%|deg)", "invert(26.2%)")]
        self.assertEqual(legacy, [2])
        self.assertEqual(parse_chain("invert(26.2%) sepia(0%) saturate(100%) "
                                     "hue-rotate(0deg) brightness(100%) contrast(100%)")[0], 26.2)

    def test_rejects(self):
        good = "invert(95%) sepia(18%) saturate(20940%) hue-rotate(66deg) brightness(157%) contrast(74%)"
        bad_variants = [
            "",
            "none",
            good.replace(" sepia", "  sepia"),          # double space
            good.replace(" sepia", " invert"),          # wrong order / duplicate
            good[:-1],                                  # missing unit
            good + ";",                                 # trailing semicolon
            good + " blur(2px)",                        # extra function
            "INVERT(95%)" + good[11:],                  # case sensitivity
            good.replace("95%", " 95%"),                # space inside parens
            good.replace("95%", "+95%"),                # leading sign
            good.replace("95%", "-95%"),                # negative not a witness
            good.replace("95%", ".5%"),                 # no leading digit
            good.replace("95%", "5.%"),                 # trailing dot
            good.replace("66deg", "66"),                # missing deg
            good.replace("20940%", "20940deg"),         # swapped units
            good.replace("95", "1e2"),                  # exponent syntax
        ]
        for b in bad_variants:
            with self.assertRaises(UnparseableWitness, msg="must reject %r" % b):
                parse_chain(b)

    def test_rejects_non_text(self):
        for b in (None, 42, b"invert(95%)"):
            with self.assertRaises(UnparseableWitness):
                parse_chain(b)


class TestSpecMatrices(unittest.TestCase):
    """Known-answer tests hand-computed from the W3C spec matrices."""

    IDENTITY = "invert(0%) sepia(0%) saturate(100%) hue-rotate(0deg) brightness(100%) contrast(100%)"

    def _params(self, text):
        return parse_chain(text)

    def test_identity_chain_renders_black(self):
        self.assertEqual(render_chain(self._params(self.IDENTITY)), (0.0, 0.0, 0.0))

    def test_invert_full_white(self):
        self.assertEqual(render_chain([100, 0, 100, 0, 100, 100]), (255.0, 255.0, 255.0))

    def test_invert_half_gray(self):
        # invert(50%) of black: F(0) = amount -> 127.5 per channel.
        c = tuple(_invert(x, 0.5) for x in (0.0, 0.0, 0.0))
        self.assertEqual(c, (127.5, 127.5, 127.5))

    def test_sepia_on_neutral_gray(self):
        # Hand: sepia(100%) row sums: R: 0.393+0.769+0.189 = 1.351
        #                              G: 0.349+0.686+0.168 = 1.203
        #                              B: 0.272+0.534+0.131 = 0.937
        # On gray 127.5: (172.2525, 153.3825, 119.4675).
        chain = "invert(50%) sepia(100%) saturate(100%) hue-rotate(0deg) brightness(100%) contrast(100%)"
        rgb = render_chain(self._params(chain))
        for got, want in zip(rgb, (172.2525, 153.3825, 119.4675)):
            self.assertAlmostEqual(got, want, delta=1e-9)

    def test_hue_rotate_180_on_gray(self):
        # cos(180deg) = -1, sin(180deg) ~= 0 (1.2246e-16). Every hueRotate row
        # sums to 1, so gray is a fixed point: 127.5 stays (127.5, 127.5, 127.5).
        chain = "invert(50%) sepia(0%) saturate(100%) hue-rotate(180deg) brightness(100%) contrast(100%)"
        rgb = render_chain(self._params(chain))
        for got in rgb:
            self.assertAlmostEqual(got, 127.5, delta=1e-6)

    def test_hue_rotate_180_on_red(self):
        # Hand: red 255 rotated 180deg -> rows a00 = 0.213 - 0.787 = -0.574
        # (clamps to 0), a10 = 0.213 + 0.213 = 0.426, a20 = 0.426.
        c = _hue_rotate((255.0, 0.0, 0.0), 180.0)
        self.assertAlmostEqual(c[0], 0.0, delta=1e-9)
        self.assertAlmostEqual(c[1], 255.0 * 0.426, delta=1e-6)
        self.assertAlmostEqual(c[2], 255.0 * 0.426, delta=1e-6)

    def test_contrast_zero_is_flat_gray(self):
        # §6.1: contrast 0% -> completely gray: slope 0, intercept 0.5 -> 127.5
        chain = "invert(47%) sepia(7%) saturate(2949%) hue-rotate(60deg) brightness(39%) contrast(0%)"
        self.assertEqual(render_chain(self._params(chain)), (127.5, 127.5, 127.5))

    def test_brightness_linear_and_clamped(self):
        chain = "invert(25%) sepia(0%) saturate(100%) hue-rotate(0deg) brightness(200%) contrast(100%)"
        self.assertEqual(render_chain(self._params(chain)), (127.5, 127.5, 127.5))
        chain3 = chain.replace("brightness(200%)", "brightness(400%)")
        self.assertEqual(render_chain(self._params(chain3)), (255.0, 255.0, 255.0))  # clamps

    def test_saturate_zero_desaturates_to_luma(self):
        # saturate(0%) row sums use the 0.213/0.715/0.072 coefficients.
        c = _saturate((255.0, 0.0, 0.0), 0.0)
        self.assertAlmostEqual(c[0], 255.0 * 0.213, delta=1e-9)
        self.assertAlmostEqual(c[1], 255.0 * 0.213, delta=1e-9)
        self.assertAlmostEqual(c[2], 255.0 * 0.213, delta=1e-9)

    def test_documented_example_row(self):
        # docs/dataset.md: #42dead, stored loss 0.8793432176.
        chain = ("invert(95%) sepia(18%) saturate(20940%) hue-rotate(66deg) "
                 "brightness(157%) contrast(74%)")
        rgb = render_chain(self._params(chain))
        loss = rendered_loss(rgb, (0x42, 0xDE, 0xAD))
        self.assertAlmostEqual(loss, 0.8793432176, delta=1e-6)
        self.assertLess(loss, LOSS_THRESHOLD)

    def test_fractional_exception_row(self):
        # docs/dataset.md: #fbfc02, stored loss 0.9697630455.
        chain = ("invert(26.2%) sepia(78.3%) saturate(4245.5%) hue-rotate(56.9deg) "
                 "brightness(241.7%) contrast(98.3%)")
        rgb = render_chain(self._params(chain))
        loss = rendered_loss(rgb, (0xFB, 0xFC, 0x02))
        self.assertAlmostEqual(loss, 0.9697630455, delta=1e-5)

    def test_knife_edge_neutrals(self):
        # #a1a1a1 and #e3e3e3: the chain's last hue-rotate row sums leave the
        # three channels one ulp apart; libm luck decides whether mx == mn
        # holds exactly. With the achromatic tolerance both rows re-render to
        # the stored losses (and the browser golden set pins the pixels).
        rgb_a = render_chain(self._params(
            "invert(59%) sepia(37%) saturate(0%) hue-rotate(237deg) brightness(91%) contrast(166%)"))
        loss_a = rendered_loss(rgb_a, (161, 161, 161))
        self.assertAlmostEqual(loss_a, 0.7814227320, delta=1e-6)
        self.assertLess(loss_a, LOSS_THRESHOLD)
        rgb_e = render_chain(self._params(
            "invert(100%) sepia(100%) saturate(0%) hue-rotate(120deg) brightness(92%) contrast(94%)"))
        loss_e = rendered_loss(rgb_e, (227, 227, 227))
        self.assertAlmostEqual(loss_e, 0.5892282849, delta=1e-6)
        self.assertLess(loss_e, LOSS_THRESHOLD)

    def test_hsl_achromatic_tolerance(self):
        # One-ulp channel differences read achromatic; a real difference does not.
        h, s, l = rgb_to_hsl(161.0, 161.0, 161.0 + 1e-12)
        self.assertEqual((h, s), (0.0, 0.0))
        self.assertAlmostEqual(l, 161.0 / 255.0 * 100.0, delta=1e-9)
        h, s, l = rgb_to_hsl(255.0, 128.0, 0.0)
        self.assertGreater(h, 0.0)
        self.assertGreater(s, 0.0)

    def test_hsl_known_values(self):
        self.assertEqual(rgb_to_hsl(0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
        self.assertEqual(rgb_to_hsl(255.0, 255.0, 255.0), (0.0, 0.0, 100.0))
        self.assertEqual(rgb_to_hsl(127.5, 127.5, 127.5), (0.0, 0.0, 50.0))
        h, s, l = rgb_to_hsl(255.0, 0.0, 0.0)
        self.assertAlmostEqual(h, 0.0, delta=1e-9)
        self.assertAlmostEqual(s, 100.0, delta=1e-9)
        self.assertAlmostEqual(l, 50.0, delta=1e-9)
        h, s, l = rgb_to_hsl(0.0, 255.0, 0.0)
        self.assertAlmostEqual(h, 100.0 / 3.0, delta=1e-9)  # 120deg on the 0-100 scale
        h, s, l = rgb_to_hsl(0.0, 0.0, 255.0)
        self.assertAlmostEqual(h, 100.0 * 2.0 / 3.0, delta=1e-9)  # 240deg
        # wraparound: yellow (max r+g) -> 60deg -> 100/6
        h, s, l = rgb_to_hsl(255.0, 255.0, 0.0)
        self.assertAlmostEqual(h, 100.0 / 6.0, delta=1e-9)


class TestSyntheticScan(unittest.TestCase):
    """A parse error or a failing witness in a scan must land in its own
    counter and flip the gate — never counted as a pass."""

    def _make_db(self, path):
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE color (id INTEGER PRIMARY KEY, filter TEXT, loss REAL)")
        conn.execute("INSERT INTO color VALUES (?, ?, ?)",
                     (0, "invert(47%) sepia(7%) saturate(2949%) hue-rotate(60deg) brightness(39%) contrast(177%)", 0.0))
        conn.execute("INSERT INTO color VALUES (?, ?, ?)",
                     (1, "invert(50%) sepia(100%) saturate(30000%) hue-rotate(0deg) brightness(100%) contrast(300%)", 0.5))
        conn.execute("INSERT INTO color VALUES (?, ?, ?)",
                     (2, "invert(0%) sepia(0%) saturate(0%) hue-rotate(0deg) brightness(0%) contrast(100%)", 0.0))
        conn.execute("INSERT INTO color VALUES (?, ?, ?)", (3, "no such chain here", 0.0))
        conn.commit()
        conn.close()

    def test_counters_and_gate(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "test.sqlite3")
            self._make_db(path)
            stats = scan_ranges(path, [(0, TOTAL_ROWS - 1)], stored_tol=1e-9, jobs=1)
            self.assertEqual(stats["total"], 4)
            self.assertEqual(stats["pass"], 1)          # only id 0 (its stored row)
            self.assertGreaterEqual(stats["fail"], 1)   # id 2: brightness(0) on target #000001
            self.assertEqual(stats["unparseable"], 1)   # id 3
            self.assertEqual(stats["pass"] + stats["fail"] + stats["unparseable"] + stats["stored_mismatch"],
                             stats["total"])
            conn = open_db(path)
            rows = check_artifact(conn)
            conn.close()
            self.assertEqual(rows, 4)


def cmd_selftest(args):
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for cls in (TestParser, TestSpecMatrices, TestSyntheticScan):
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2 if args.verbose else 1)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("selftest: OK — verifier arithmetic matches hand-computed W3C spec values "
              "and the counters gate correctly")
        return 0
    return 1


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="verify_covering.py",
        description="Independent verifier for the CSS filter covering dataset claim.")
    parser.add_argument("--db", help="path to %s" % DB_FILENAME)
    sub = parser.add_subparsers(dest="mode", required=True)

    p_scan = sub.add_parser("scan", help="verify every row; the release gate")
    p_scan.add_argument("--jobs", type=int, default=1, help="parallel id-range workers (0 = all cores)")
    p_scan.add_argument("--stored-tol", type=float, default=1e-9,
                        help="tolerance for recomputed vs stored loss column")
    p_scan.add_argument("--expect-rows", type=int, default=TOTAL_ROWS,
                        help="artifact row-count gate (0 disables)")
    p_scan.add_argument("--strict-stored", action="store_true",
                        help="store-loss mismatches fail the gate")
    p_scan.add_argument("--json", action="store_true", help="machine-readable output")
    p_scan.add_argument("--progress", action="store_true", help="periodic stderr progress")
    p_scan.set_defaults(func=cmd_scan)

    p_sample = sub.add_parser("sample", help="verify N random rows")
    p_sample.add_argument("--n", type=int, default=100000)
    p_sample.add_argument("--seed", type=int, default=1)
    p_sample.add_argument("--stored-tol", type=float, default=1e-9)
    p_sample.set_defaults(func=cmd_sample)

    p_row = sub.add_parser("row", help="verify one color and show the math")
    p_row.add_argument("color", help="hex target, e.g. #42dead")
    p_row.set_defaults(func=cmd_row)

    p_golden = sub.add_parser("golden", help="compare against headless Chrome pixels")
    p_golden.add_argument("--n", type=int, default=256, help="extra random witnesses beyond the known set")
    p_golden.add_argument("--seed", type=int, default=7)
    p_golden.add_argument("--chrome", help="path to Chrome/Chromium binary")
    p_golden.add_argument("--cell", type=int, default=8, help="cell size in device pixels")
    p_golden.add_argument("--tol", type=float, default=1.0,
                          help="max |verifier float - browser pixel| per channel, in 0-255 units; "
                               "1.0 is one 8-bit code value, the rounding budget float32 Chrome gets")
    p_golden.add_argument("--chrome-timeout", type=int, default=120,
                          help="seconds to wait for the Chrome screenshot")
    p_golden.set_defaults(func=cmd_golden)

    p_self = sub.add_parser("selftest", help="known-answer and parser tests")
    p_self.add_argument("-v", "--verbose", action="store_true")
    p_self.set_defaults(func=cmd_selftest)

    args = parser.parse_args(argv)
    if hasattr(args, "expect_rows") and args.expect_rows == 0:
        args.expect_rows = None
    try:
        return args.func(args)
    except ArtifactError as exc:
        print("ARTIFACT ERROR: %s" % exc, file=sys.stderr)
        return 2
    except sqlite3.Error as exc:
        print("ARTIFACT ERROR: sqlite: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
