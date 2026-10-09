#!/usr/bin/env python3
"""Delta-E-2000 and per-channel colorimetric stats for the CSS filter covering dataset.

THE QUOTABLE CLAIM this tool measures: "integer CSS filters cover sRGB within
Delta-E-2000 of X", one number for every one of the 16,777,216 colors. The
colors are scored THROUGH the independent Python verifier's model
(research/verifier/verify_covering.py): each row's witness is parsed and
rendered by `parse_chain`/`render_chain` and re-scored by the verifier's own
`rendered_loss`, so the colorimetry and the <1% covering claim share one
trust path. Per the spec, every published statistic flows through the
verifier.

Colorimetry definitions (standard, not invented here):

  * sRGB -> CIELAB, D65 (IEC 61966-2-1 / CIE 15:2004): sRGB-encoded 8-bit
    codes, component-wise inverse gamma (linear = c/12.92 for the encoded
    value c <= 0.04045, else ((c+0.055)/1.055)^2.4), the standard sRGB->XYZ
    matrix, and CIELAB against the D65 2-deg reference white
    (0.95047, 1.00000, 1.08883).
  * CIEDE2000 (the 2000 supplement to CIE 15.2, kL = kC = kH = 1) exactly as
    formulated by Sharma, Wu & Dalley, "The CIEDE2000 color-difference
    formula: implementation notes, supplementary test data, and mathematical
    observations", Color Research & Application 30(4), 2005. All 34 published
    Lab-pair/Delta-E00 test values of that paper's Table I are embedded
    verbatim in the selftest, plus the published CIELAB values of the sRGB
    primaries. No published deviation is tolerated beyond 4-decimal rounding.

Two renderings per row are scored, both against the target's Lab:
  * "quantized": the rendered float RGB rounded to 8-bit codes, i.e. what
    a browser actually paints (the verifier's golden mode measured every
    Chrome pixel equal to round(float) up to one code value, including a
    half-code tie flip; ties are documented below), and
  * "float": the verifier's unrounded chain output, the model value.

Report: max/mean, percentiles and distribution buckets (histogram-derived),
per-channel maximum errors (integer code values and float), the worst
colors with their witnesses, and a hardness cross-check: Delta-E by loss
band plus the overlap of the worst-Delta-E population with the
near-threshold (loss >= 0.99) rows. Those near-threshold rows are the same
population the companion hardness-map artifact is derived from.

Machine-readable stats (JSON) and a human summary (Markdown) are both
written by `scan` and are fully regenerable from the dataset artifact
alone; no intermediate files are consulted.

Stdlib only; Python 3.8+. Uses math.cbrt when available (3.11+).

Usage:
  python3 de2000_stats.py selftest [-v]
  python3 de2000_stats.py row '#38cac2'
  python3 de2000_stats.py sample --n 100000
  python3 de2000_stats.py scan --jobs 0 [--progress] [--json-out PATH] [--md-out PATH]

License: MIT (tooling), matching the library. Dataset: CC-BY-4.0.
"""

import argparse
import bisect
import hashlib
import heapq
import json
import math
import multiprocessing
import os
import platform
import random
import sqlite3
import sys
import tempfile
import time
import unittest
from collections import namedtuple
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "verifier"))

from verify_covering import (  # noqa: E402  (path set above, by design)
    LOSS_THRESHOLD,
    SNAPSHOT,
    TOTAL_ROWS,
    ArtifactError,
    UnparseableWitness,
    check_artifact,
    fetch_rows,
    open_db,
    parse_chain,
    render_chain,
    rendered_loss,
    resolve_db_path,
    split_ranges,
    target_of,
    verify_row,
    _fmt_hex as fmt_hex,
)

TOP_K = 200  # worst colors retained per worker and merged globally
# Recomputed-loss bands; the [0.99, 1.0) band is the near-threshold hardness
# proxy (the survivor-based hardness-map artifact replaces this).
LOSS_BINS = (0.0, 0.5, 0.9, 0.99, 1.0, float("inf"))
NEAR_THRESHOLD_BAND = 3  # the LOSS_BINS index of [0.99, 1.0)
# The dataset's published average rendered loss (docs/dataset.md:
# "Average rendered loss: 0.78803"; the scan's recomputed full-precision mean
# is 0.788036482548). `scan` recomputes every row's loss through the
# verifier's rendered_loss, so a different artifact or broken arithmetic
# shows up here first.
PUBLISHED_MEAN_LOSS = 0.788036482548

# ---------------------------------------------------------------------------
# sRGB -> CIELAB (D65)
# ---------------------------------------------------------------------------

# IEC 61966-2-1 sRGB -> XYZ (D65) matrix rows divided by the reference white,
# so the channel sums feed CIELAB f() directly as X/Xn, Y/Yn, Z/Zn.
_XR, _XG, _XB = 0.4124564 / 0.95047, 0.3575761 / 0.95047, 0.1804375 / 0.95047
_YR, _YG, _YB = 0.2126729, 0.7151522, 0.0721750
_ZR, _ZG, _ZB = 0.0193339 / 1.08883, 0.1191920 / 1.08883, 0.9503041 / 1.08883

_CIE_EPS = (6.0 / 29.0) ** 3          # 0.008856451679035631
_CIE_LIN = 841.0 / 108.0              # 1 / (3 * (6/29)^2)
_CIE_OFF = 4.0 / 29.0

if hasattr(math, "cbrt"):
    _cbrt = math.cbrt
else:
    def _cbrt(x):
        return x ** (1.0 / 3.0)


def _lab_from_ratios(rx, ry, rz):
    """CIELAB from already-white-normalized XYZ ratios."""
    fx = _cbrt(rx) if rx > _CIE_EPS else rx * _CIE_LIN + _CIE_OFF
    fy = _cbrt(ry) if ry > _CIE_EPS else ry * _CIE_LIN + _CIE_OFF
    fz = _cbrt(rz) if rz > _CIE_EPS else rz * _CIE_LIN + _CIE_OFF
    return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))


# Per-channel lookup tables for the quantized path (linearized 8-bit codes,
# each pre-multiplied by its matrix row entry).
_SRGB_LIN = [
    (c / 255.0) / 12.92 if (c / 255.0) <= 0.04045
    else ((c / 255.0 + 0.055) / 1.055) ** 2.4
    for c in range(256)
]
_LIN_RX = [_XR * v for v in _SRGB_LIN]
_LIN_GX = [_XG * v for v in _SRGB_LIN]
_LIN_BX = [_XB * v for v in _SRGB_LIN]
_LIN_RY = [_YR * v for v in _SRGB_LIN]
_LIN_GY = [_YG * v for v in _SRGB_LIN]
_LIN_BY = [_YB * v for v in _SRGB_LIN]
_LIN_RZ = [_ZR * v for v in _SRGB_LIN]
_LIN_GZ = [_ZG * v for v in _SRGB_LIN]
_LIN_BZ = [_ZB * v for v in _SRGB_LIN]


def srgb_int_to_lab(r, g, b):
    """CIELAB (D65) of an 8-bit sRGB code triple."""
    rx = _LIN_RX[r] + _LIN_GX[g] + _LIN_BX[b]
    ry = _LIN_RY[r] + _LIN_GY[g] + _LIN_BY[b]
    rz = _LIN_RZ[r] + _LIN_GZ[g] + _LIN_BZ[b]
    return _lab_from_ratios(rx, ry, rz)


def _linf(c255):
    v = c255 / 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def srgb_float_to_lab(r, g, b):
    """CIELAB (D65) of float sRGB components in 0..255 (the model value)."""
    lr, lg, lb = _linf(r), _linf(g), _linf(b)
    rx = _XR * lr + _XG * lg + _XB * lb
    ry = _YR * lr + _YG * lg + _YB * lb
    rz = _ZR * lr + _ZG * lg + _ZB * lb
    return _lab_from_ratios(rx, ry, rz)


# ---------------------------------------------------------------------------
# CIEDE2000 (kL = kC = kH = 1)
# ---------------------------------------------------------------------------

_25_7 = 25.0 ** 7  # 6103515625.0


def ciede2000(lab1, lab2):
    """Sharma/Wu/Dalley 2005 formulation, published parameter weighting 1."""
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    C1 = math.hypot(a1, b1)
    C2 = math.hypot(a2, b2)
    Cb = 0.5 * (C1 + C2)
    Cb7 = Cb ** 7
    G = 0.5 * (1.0 - math.sqrt(Cb7 / (Cb7 + _25_7)))
    a1p = (1.0 + G) * a1
    a2p = (1.0 + G) * a2
    C1p = math.hypot(a1p, b1)
    C2p = math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360.0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360.0
    dLp = L2 - L1
    dCp = C2p - C1p
    if C1p * C2p == 0.0:
        dhp = 0.0
    else:
        dh = h2p - h1p
        if dh > 180.0:
            dhp = dh - 360.0
        elif dh < -180.0:
            dhp = dh + 360.0
        else:
            dhp = dh
    dHp = 2.0 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp) / 2.0)
    Lb = 0.5 * (L1 + L2)
    Cbp = 0.5 * (C1p + C2p)
    if C1p * C2p == 0.0:
        hbp = h1p + h2p
    else:
        dabs = abs(h1p - h2p)
        if dabs <= 180.0:
            hbp = 0.5 * (h1p + h2p)
        elif h1p + h2p < 360.0:
            hbp = 0.5 * (h1p + h2p + 360.0)
        else:
            hbp = 0.5 * (h1p + h2p - 360.0)
    hrad = math.radians(hbp)
    T = (1.0
         - 0.17 * math.cos(hrad - math.radians(30.0))
         + 0.24 * math.cos(2.0 * hrad)
         + 0.32 * math.cos(3.0 * hrad + math.radians(6.0))
         - 0.20 * math.cos(4.0 * hrad - math.radians(63.0)))
    d50 = Lb - 50.0
    d50sq = d50 * d50
    SL = 1.0 + 0.015 * d50sq / math.sqrt(20.0 + d50sq)
    SC = 1.0 + 0.045 * Cbp
    SH = 1.0 + 0.015 * Cbp * T
    dtheta = 30.0 * math.exp(-(((hbp - 275.0) / 25.0) ** 2))
    Cbp7 = Cbp ** 7
    RC = 2.0 * math.sqrt(Cbp7 / (Cbp7 + _25_7))
    RT = -math.sin(2.0 * math.radians(dtheta)) * RC
    tL = dLp / SL
    tC = dCp / SC
    tH = dHp / SH
    return math.sqrt(tL * tL + tC * tC + tH * tH + RT * tC * tH)


# ---------------------------------------------------------------------------
# Row scoring: THE single row-eval core for colorimetry.
# ---------------------------------------------------------------------------

RowScore = namedtuple("RowScore",
                      "status loss de_q de_f ch_int_err ch_float_err lab_target rgb")


def score_row(row_id, filter_text, stored_loss=None, stored_tol=1e-9):
    """Render a witness through the verifier's model and score it.

    Returns a RowScore(status, loss, de_q, de_f, ch_int_err, ch_float_err,
    lab_target, rgb), or None for an unparseable witness. `status`/`loss`
    follow verify_row exactly (the loss arithmetic is the verifier's own
    `rendered_loss`, proved equal by selftest); de_q is Delta-E-2000 of the
    browser-style quantized rendering, de_f of the float rendering;
    ch_int_err/ch_float_err are the three per-channel absolute errors
    (integer code values, and float); lab_target is the target's own Lab;
    rgb is the verifier's rendered float RGB (the model value) so callers
    never re-render.
    """
    try:
        params = parse_chain(filter_text)
    except UnparseableWitness:
        return None
    rgb = render_chain(params)
    target = target_of(row_id)
    loss = rendered_loss(rgb, target)
    ir = (round(rgb[0]), round(rgb[1]), round(rgb[2]))
    lab_t = srgb_int_to_lab(*target)
    lab_i = srgb_int_to_lab(*ir)
    lab_f = srgb_float_to_lab(*rgb)
    de_q = ciede2000(lab_t, lab_i)
    de_f = ciede2000(lab_t, lab_f)
    ei = (abs(ir[0] - target[0]), abs(ir[1] - target[1]), abs(ir[2] - target[2]))
    ef = (abs(rgb[0] - target[0]), abs(rgb[1] - target[1]), abs(rgb[2] - target[2]))
    if loss >= LOSS_THRESHOLD:
        status = "fail"
    elif stored_loss is not None and stored_loss == stored_loss and abs(loss - stored_loss) > stored_tol:
        status = "stored-mismatch"
    else:
        status = "pass"
    return RowScore(status, loss, de_q, de_f, ei, ef, lab_t, rgb)


# ---------------------------------------------------------------------------
# Histogram / aggregation machinery
# ---------------------------------------------------------------------------

def _make_edges():
    edges = []
    x = 0.001
    while x <= 0.02 + 1e-9:
        edges.append(round(x, 4)); x += 0.001
    x = 0.025
    while x <= 0.10 + 1e-9:
        edges.append(round(x, 4)); x += 0.005
    x = 0.11
    while x <= 0.50 + 1e-9:
        edges.append(round(x, 4)); x += 0.01
    x = 0.55
    while x <= 1.00 + 1e-9:
        edges.append(round(x, 4)); x += 0.05
    x = 1.1
    while x <= 2.00 + 1e-9:
        edges.append(round(x, 4)); x += 0.1
    x = 2.5
    while x <= 10.0 + 1e-9:
        edges.append(round(x, 4)); x += 0.5
    x = 15.0
    while x <= 100.0 + 1e-9:
        edges.append(round(x, 4)); x += 5.0
    return edges


EDGES = _make_edges()
# A value v lands in bucket bisect_right(EDGES, v): bucket i covers
# [EDGES[i-1], EDGES[i]) (bucket 0 covers [0, EDGES[0]), the last is [100, inf)).


def bucket_of(value):
    return bisect.bisect_right(EDGES, value)


def _blank_stats():
    return {
        "total": 0,
        "pass": 0,
        "fail": 0,
        "unparseable": 0,
        "stored_mismatch": 0,
        "gaps": 0,
        "fractional": 0,  # witnesses with a documented fractional parameter
        "de_sum_q": 0.0,
        "de_max_q": (float("-inf"), None),
        "de_sum_f": 0.0,
        "de_max_f": (float("-inf"), None),
        "loss_sum": 0.0,
        "ch_int_max": [0, 0, 0],
        "ch_int_nonzero": [0, 0, 0],
        "ch_float_max": [0.0, 0.0, 0.0],
        "hist": [0] * (len(EDGES) + 1),
        "bins": [{"count": 0, "de_sum": 0.0, "de_max": (float("-inf"), None), "l_sum": 0.0}
                 for _ in range(len(LOSS_BINS) - 1)],
        "top": [],  # min-heap of (de_q, id, de_f, loss), capped at TOP_K
    }


def _beats(cand, cur):
    """True if (value, id) `cand` should replace current max `cur`: larger
    value, ties broken toward the SMALLER id so the reported "at #hex" of a
    tied maximum (e.g. the all-zero band) is independent of job scheduling."""
    if cand[1] is None:
        return False
    if cur[1] is None or cand[0] > cur[0]:
        return True
    return cand[0] == cur[0] and cand[1] < cur[1]


def _tally(stats, row_id, filter_text, stored_loss, stored_tol=1e-9, top_k=TOP_K):
    scored = score_row(row_id, filter_text, stored_loss, stored_tol)
    stats["total"] += 1
    if scored is None:
        stats["unparseable"] += 1
        return
    if isinstance(filter_text, str) and "." in filter_text:
        stats["fractional"] += 1
    stats["de_sum_q"] += scored.de_q
    stats["de_sum_f"] += scored.de_f
    stats["loss_sum"] += scored.loss
    if _beats((scored.de_q, row_id), stats["de_max_q"]):
        stats["de_max_q"] = (scored.de_q, row_id)
    if _beats((scored.de_f, row_id), stats["de_max_f"]):
        stats["de_max_f"] = (scored.de_f, row_id)
    for ch in range(3):
        if scored.ch_int_err[ch] > stats["ch_int_max"][ch]:
            stats["ch_int_max"][ch] = scored.ch_int_err[ch]
        if scored.ch_int_err[ch] != 0:
            stats["ch_int_nonzero"][ch] += 1
        if scored.ch_float_err[ch] > stats["ch_float_max"][ch]:
            stats["ch_float_max"][ch] = scored.ch_float_err[ch]
    stats["hist"][bucket_of(scored.de_q)] += 1
    b = 0
    while scored.loss >= LOSS_BINS[b + 1]:
        b += 1
    band = stats["bins"][b]
    band["count"] += 1
    band["de_sum"] += scored.de_q
    band["l_sum"] += scored.lab_target[0]
    if _beats((scored.de_q, row_id), band["de_max"]):
        band["de_max"] = (scored.de_q, row_id)
    top = stats["top"]
    entry = (scored.de_q, row_id, scored.de_f, scored.loss)
    if len(top) < top_k:
        heapq.heappush(top, entry)
    elif entry > top[0]:
        heapq.heapreplace(top, entry)
    if scored.status == "fail":
        stats["fail"] += 1
    elif scored.status == "stored-mismatch":
        stats["stored_mismatch"] += 1
    else:
        stats["pass"] += 1


def _merge(stats_list):
    out = _blank_stats()
    for s in stats_list:
        for k in ("total", "pass", "fail", "unparseable", "stored_mismatch", "gaps", "fractional"):
            out[k] += s[k]
        out["de_sum_q"] += s["de_sum_q"]
        out["de_sum_f"] += s["de_sum_f"]
        out["loss_sum"] += s["loss_sum"]
        if _beats(s["de_max_q"], out["de_max_q"]):
            out["de_max_q"] = s["de_max_q"]
        if _beats(s["de_max_f"], out["de_max_f"]):
            out["de_max_f"] = s["de_max_f"]
        for ch in range(3):
            out["ch_int_max"][ch] = max(out["ch_int_max"][ch], s["ch_int_max"][ch])
            out["ch_int_nonzero"][ch] += s["ch_int_nonzero"][ch]
            out["ch_float_max"][ch] = max(out["ch_float_max"][ch], s["ch_float_max"][ch])
        for i, c in enumerate(s["hist"]):
            out["hist"][i] += c
        for i, band in enumerate(s["bins"]):
            ob = out["bins"][i]
            ob["count"] += band["count"]
            ob["de_sum"] += band["de_sum"]
            ob["l_sum"] += band["l_sum"]
            if _beats(band["de_max"], ob["de_max"]):
                ob["de_max"] = band["de_max"]
    all_entries = []
    for s in stats_list:
        all_entries.extend(s["top"])
    # Each worker heap already holds only its own K largest entries; the
    # global worst K is the K LARGEST among their union (nsmallest was the
    # first-draft bug: it kept the heap-floor entries and lost the true max).
    out["top"] = sorted(heapq.nlargest(TOP_K, all_entries))
    return out


# ---------------------------------------------------------------------------
# Parallel scan (same contiguous id-range shape as the verifier's scan)
# ---------------------------------------------------------------------------

def scan_range_worker(args):
    db_path, lo, hi, stored_tol, top_k = args
    conn = open_db(db_path)
    cur = conn.execute("SELECT id, filter, loss FROM color WHERE id BETWEEN ? AND ? ORDER BY id",
                       (lo, hi))
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
            _tally(stats, row_id, filter_text, stored_loss, stored_tol, top_k)
    conn.close()
    return stats


def scan_ranges(db_path, ranges, stored_tol=1e-9, jobs=1, progress=None):
    work = [(db_path, lo, hi, stored_tol, TOP_K) for lo, hi in ranges]
    results = []
    if jobs <= 1:
        for w in work:
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


# ---------------------------------------------------------------------------
# Derived numbers
# ---------------------------------------------------------------------------
# _fmt_hex is imported from the verifier as fmt_hex; the two were
# byte-identical, so the shared definition lives on the trust path.

def processed(stats):
    return stats["total"] - stats["unparseable"]


def _r(x, nd=12):
    """JSON convention for mean-like floats: round to 12 decimals. Raw
    float64 sums depend on worker addition order (last-ulp noise ~1e-16);
    rounded values are byte-identical across job counts, and 12 decimals
    is a trillion times finer than any measurement here."""
    return round(x, nd) if x is not None and x == x else x


def percentile(stats, p):
    """(lower, upper) histogram edges bracketing the p-th percentile of de_q."""
    n = processed(stats)
    if n <= 0:
        return (float("nan"), float("nan"))
    target = max(1, math.ceil(p * n / 100.0))
    cum = 0
    for i, c in enumerate(stats["hist"]):
        cum += c
        if cum >= target:
            lo = 0.0 if i == 0 else EDGES[i - 1]
            hi = EDGES[i] if i < len(EDGES) else float("inf")
            return (lo, hi)
    return (float("nan"), float("nan"))


def band_below(stats, value):
    """Rows with de_q strictly below `value` (value must be a histogram edge,
    or an interior point; exact hits land in the bucket above either way)."""
    return sum(stats["hist"][:bisect.bisect_right(EDGES, value)])


def report_percentiles(stats):
    """The four percentile braces the reports quote: median, p90, p99, p99.9,
    each as its (lower, upper) histogram-edge bracket."""
    return (percentile(stats, 50.0), percentile(stats, 90.0),
            percentile(stats, 99.0), percentile(stats, 99.9))


def headline(stats):
    de_max = max(stats["de_max_q"][0], stats["de_max_f"][0])
    n = processed(stats)
    mean_q = stats["de_sum_q"] / n if n else float("nan")
    bound = math.ceil(de_max * 1000.0) / 1000.0
    return {
        "statement": ("integer CSS filters cover sRGB within Delta-E-2000 of %.3f "
                      "(measured maximum %.6f over all %d rendered colors; mean %.4f)"
                      % (bound, de_max, n, mean_q)),
        "max": de_max,
        "quotableBound": bound,
        "mean": mean_q,
    }


# ---------------------------------------------------------------------------
# Published reference data: Sharma, Wu & Dalley 2005, Table I
# (Color Research & Application 30(4), 219-227: "CIEDE2000 total color
# difference test data"). Transcribed from the published PDF AND independently
# verified, digit-for-digit, against the authors' own machine-readable file
# (https://www.hajim.rochester.edu/ece/~gsharma/ciede2000/dataNprograms/ciede2000testdata.txt,
# sha256 44aebb39107128328add54fbef5ac8ee89909e50508f448a1580adea2058a4b8,
# 34 rows). The final column is the published Delta-E00, to 4 decimals. Because
# this table is the authors' data, reproducing it is an EXTERNAL fact-check of
# the formula below, not a self-consistent assertion: a wrong CIEDE2000 cannot
# pass it.
# ---------------------------------------------------------------------------

SHARMA_2005_TABLE_I = [
    (50.0000, 2.6772, -79.7751, 50.0000, 0.0000, -82.7485, 2.0425),
    (50.0000, 3.1571, -77.2803, 50.0000, 0.0000, -82.7485, 2.8615),
    (50.0000, 2.8361, -74.0200, 50.0000, 0.0000, -82.7485, 3.4412),
    (50.0000, -1.3802, -84.2814, 50.0000, 0.0000, -82.7485, 1.0000),
    (50.0000, -1.1848, -84.8006, 50.0000, 0.0000, -82.7485, 1.0000),
    (50.0000, -0.9009, -85.5211, 50.0000, 0.0000, -82.7485, 1.0000),
    (50.0000, 0.0000, 0.0000, 50.0000, -1.0000, 2.0000, 2.3669),
    (50.0000, -1.0000, 2.0000, 50.0000, 0.0000, 0.0000, 2.3669),
    (50.0000, 2.4900, -0.0010, 50.0000, -2.4900, 0.0009, 7.1792),
    (50.0000, 2.4900, -0.0010, 50.0000, -2.4900, 0.0010, 7.1792),
    (50.0000, 2.4900, -0.0010, 50.0000, -2.4900, 0.0011, 7.2195),
    (50.0000, 2.4900, -0.0010, 50.0000, -2.4900, 0.0012, 7.2195),
    (50.0000, -0.0010, 2.4900, 50.0000, 0.0009, -2.4900, 4.8045),
    (50.0000, -0.0010, 2.4900, 50.0000, 0.0010, -2.4900, 4.8045),
    (50.0000, -0.0010, 2.4900, 50.0000, 0.0011, -2.4900, 4.7461),
    (50.0000, 2.5000, 0.0000, 50.0000, 0.0000, -2.5000, 4.3065),
    (50.0000, 2.5000, 0.0000, 73.0000, 25.0000, -18.0000, 27.1492),
    (50.0000, 2.5000, 0.0000, 61.0000, -5.0000, 29.0000, 22.8977),
    (50.0000, 2.5000, 0.0000, 56.0000, -27.0000, -3.0000, 31.9030),
    (50.0000, 2.5000, 0.0000, 58.0000, 24.0000, 15.0000, 19.4535),
    (50.0000, 2.5000, 0.0000, 50.0000, 3.1736, 0.5854, 1.0000),
    (50.0000, 2.5000, 0.0000, 50.0000, 3.2972, 0.0000, 1.0000),
    (50.0000, 2.5000, 0.0000, 50.0000, 1.8634, 0.5757, 1.0000),
    (50.0000, 2.5000, 0.0000, 50.0000, 3.2592, 0.3350, 1.0000),
    (60.2574, -34.0099, 36.2677, 60.4626, -34.1751, 39.4387, 1.2644),
    (63.0109, -31.0961, -5.8663, 62.8187, -29.7946, -4.0864, 1.2630),
    (61.2901, 3.7196, -5.3901, 61.4292, 2.2480, -4.9620, 1.8731),
    (35.0831, -44.1164, 3.7933, 35.0232, -40.0716, 1.5901, 1.8645),
    (22.7233, 20.0904, -46.6940, 23.0331, 14.9730, -42.5619, 2.0373),
    (36.4612, 47.8580, 18.3852, 36.2715, 50.5065, 21.2231, 1.4146),
    (90.8027, -2.0831, 1.4410, 91.1528, -1.6435, 0.0447, 1.4441),
    (90.9257, -0.5406, -0.9208, 88.6381, -0.8985, -0.7239, 1.5381),
    (6.7747, -0.2908, -2.4247, 5.8714, -0.0985, -2.2286, 0.6377),
    (2.0776, 0.0795, -1.1350, 0.9033, -0.0636, -0.5514, 0.9082),
]

# Published CIELAB (D65) of the fully-on sRGB primaries (IEC 61966-2-1
# conversion, as tabulated in the sRGB standard's literature):
SRGB_PUBLISHED_LAB = {
    (255, 0, 0): (53.235, 80.108, 67.220),
    (0, 255, 0): (87.734, -86.183, 83.179),
    (0, 0, 255): (32.297, 79.181, -107.862),
}

# Perceptibility bands for the report: the interpretation table published
# with the CIEDE2000 supplementary paper (Sharma et al. 2005) and the
# Mahy et al. 1994 scale quoted in the color-difference literature.
BANDS = [
    (0.01, "distinguishable only by instruments"),
    (0.10, "imperceptible even to a trained observer"),
    (0.25, "small; perceptible to a trained observer"),
    (1.00, "perceptible only through very close observation"),
    (2.00, "perceptible through close observation (below a JND by most scales)"),
    (10.00, "large difference, perceptible at a glance"),
]


def sha256_file(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def method_meta(db_path, elapsed, jobs):
    return {
        "tool": "research/colorimetry/de2000_stats.py",
        "trustPath": ("renders every witness through research/verifier/verify_covering.py "
                      "(parse_chain/render_chain/rendered_loss); loss statuses are verify_row-identical"),
        "colorimetry": ("sRGB->CIELAB D65 (IEC 61966-2-1 inverse gamma + matrix, white "
                        "0.95047/1.0/1.08883); CIEDE2000 per Sharma/Wu/Dalley 2005 "
                        "(kL=kC=kH=1), validated on all 34 Table I pairs; quantized "
                        "variant uses round() to 8-bit codes (browser-quantized "
                        "rendering per the verifier's golden mode)"),
        "python": platform.python_version(),
        "pythonImplementation": platform.python_implementation(),
        "platform": "%s %s (%s)" % (platform.system(), platform.release(), platform.machine()),
        "jobs": jobs,
        "runtimeSeconds": round(elapsed, 2),
        "cpuCount": os.cpu_count(),
        "artifact": {"snapshot": SNAPSHOT, "path": os.path.abspath(db_path), "sha256": None},
    }


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

def cmd_selftest(args):
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for cls in (TestColorimetry, TestHistogram, TestRowSemantics, TestSyntheticScan):
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2 if args.verbose else 1)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("selftest: OK. Conversion matches published anchors and all 34 "
              "Sharma/Wu/Dalley 2005 Table I pairs; row semantics match the verifier")
        return 0
    return 1


def cmd_row(args):
    db_path = resolve_db_path(args.db)
    text = args.color.lstrip("#") if args.color.startswith("#") else args.color
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
    scored = score_row(row_id, filter_text, stored_loss)
    if scored is None:
        print("%s UNPARSEABLE witness: %r" % (fmt_hex(row_id), filter_text))
        return 1
    rgb = scored.rgb
    target = target_of(row_id)
    ir = tuple(round(v) for v in rgb)
    lab_i = srgb_int_to_lab(*ir)
    print("color    %s  target rgb %d %d %d" % (fmt_hex(row_id), *target))
    print("witness  %s" % filter_text)
    print("rendered float  %11.4f %11.4f %11.4f   quantized  %3d %3d %3d"
          % (rgb[0], rgb[1], rgb[2], ir[0], ir[1], ir[2]))
    print("target CIELAB   %11.4f %11.4f %11.4f  (L*, a*, b*, D65)" % scored.lab_target)
    print("rendered CIELAB %11.4f %11.4f %11.4f  (quantized)" % lab_i)
    print("dE2000 quantized %.6f | float %.6f" % (scored.de_q, scored.de_f))
    print("channel abs err  int %d %d %d | float %.4f %.4f %.4f"
          % (scored.ch_int_err[0], scored.ch_int_err[1], scored.ch_int_err[2],
             scored.ch_float_err[0], scored.ch_float_err[1], scored.ch_float_err[2]))
    print("rendered loss %.10f | stored %s | threshold %g | %s"
          % (scored.loss, "NULL" if stored_loss is None else "%.10f" % stored_loss,
              LOSS_THRESHOLD, scored.status))
    return 0 if scored.status in ("pass", "stored-mismatch") else 1


def cmd_sample(args):
    db_path = resolve_db_path(args.db)
    conn = open_db(db_path)
    rng = random.Random(args.seed)
    ids = rng.sample(range(TOTAL_ROWS), args.n)
    stats = _blank_stats()
    for row_id, filter_text, stored_loss in fetch_rows(conn, ids):
        _tally(stats, row_id, filter_text, stored_loss)
    conn.close()
    n = processed(stats)
    print("sampled %d random rows (seed=%d): pass=%d fail=%d unparseable=%d stored-mismatch=%d"
          % (stats["total"], args.seed, stats["pass"], stats["fail"], stats["unparseable"],
             stats["stored_mismatch"]))
    if n:
        lo, hi = percentile(stats, 99.0)
        print("  dE2000: max quantized %.6f at %s | max float %.6f | mean %.6f"
              % (stats["de_max_q"][0], fmt_hex(stats["de_max_q"][1]),
                 stats["de_max_f"][0], stats["de_sum_q"] / n))
        print("  p99 within [%.4f, %.4f); per-channel int max err R%d G%d B%d"
              % (lo, hi, stats["ch_int_max"][0], stats["ch_int_max"][1], stats["ch_int_max"][2]))
    return 1 if (stats["fail"] or stats["unparseable"]) else 0


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
    ranges = split_ranges(args.jobs * 8) if args.jobs > 1 else [(0, TOTAL_ROWS - 1)]

    digest = sha256_file(db_path) if args.sha256 else None

    t0 = time.monotonic()
    state = {"last": t0, "last_done": 0}

    def progress(done):
        now = time.monotonic()
        if now - state["last"] > 5.0:
            dt = now - state["last"]
            rate = (done - state["last_done"]) / max(dt, 1e-9)
            state["last"], state["last_done"] = now, done
            print("  ... %d rows (%.1f%%), ~%.0f rows/s" % (done, 100.0 * done / TOTAL_ROWS, rate),
                  file=sys.stderr)

    stats = scan_ranges(db_path, ranges, args.stored_tol, jobs=args.jobs,
                        progress=progress if args.progress else None)
    elapsed = time.monotonic() - t0

    # Invariants first: the stats are only quotable if the arithmetic self-checks.
    errors = []
    n = processed(stats)
    if n and sum(stats["hist"]) != n:
        errors.append("histogram counts %d != rows scored %d" % (sum(stats["hist"]), n))
    if stats["pass"] + stats["fail"] + stats["unparseable"] + stats["stored_mismatch"] != stats["total"]:
        errors.append("counters do not sum to rows processed")
    if stats["fail"] or stats["unparseable"]:
        errors.append("covering gate violated: %d failures, %d unparseable"
                      % (stats["fail"], stats["unparseable"]))
    if stats["total"] != TOTAL_ROWS:
        errors.append("processed %d rows, expected %d" % (stats["total"], TOTAL_ROWS))
    if stats["gaps"]:
        errors.append("%d gaps in the id sequence" % stats["gaps"])
    mean_loss = stats["loss_sum"] / n if n else float("nan")
    if n and abs(mean_loss - PUBLISHED_MEAN_LOSS) > 1e-3:
        errors.append("mean recomputed loss %.5f disagrees with the published "
                      "average rendered loss 0.78803 (docs/dataset.md; full "
                      "precision %.8f). Different artifact or broken arithmetic?"
                      % (mean_loss, PUBLISHED_MEAN_LOSS))

    # Worst-row details: fetch their witness texts by id.
    worst = sorted(stats["top"], key=lambda e: e[0], reverse=True)
    conn = open_db(db_path)
    detail = {}
    if worst:
        for row_id, chain, stored in conn.execute(
                "SELECT id, filter, loss FROM color WHERE id IN (%s)"
                % ",".join("?" * len(worst)), [w[1] for w in worst]):
            detail[row_id] = (chain, stored)
    conn.close()

    meta = method_meta(db_path, elapsed, args.jobs)
    meta["artifact"]["sizeBytes"] = size
    meta["artifact"]["sha256"] = digest
    meta["generatedUtc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = build_json(stats, meta, worst, detail, errors)
    md_text = build_markdown(stats, meta, worst, detail, errors)

    with open(args.json_out, "w") as fh:
        fh.write(doc)
    with open(args.md_out, "w") as fh:
        fh.write(md_text)

    print(headline(stats)["statement"])
    print("  rows processed %d | failures %d | unparseable %d | stored-mismatch %d"
          % (stats["total"], stats["fail"], stats["unparseable"], stats["stored_mismatch"]))
    print("  max dE2000 quantized %.6f at %s | float %.6f | mean %.6f"
          % (stats["de_max_q"][0], fmt_hex(stats["de_max_q"][1]),
             stats["de_max_f"][0], stats["de_sum_q"] / max(n, 1)))
    print("  per-channel int max error R%d G%d B%d (nonzero rows: %d/%d/%d)"
          % (stats["ch_int_max"][0], stats["ch_int_max"][1], stats["ch_int_max"][2],
             stats["ch_int_nonzero"][0], stats["ch_int_nonzero"][1], stats["ch_int_nonzero"][2]))
    print("  runtime %.1f s with %d job(s); artifact sha256 %s"
          % (elapsed, args.jobs, digest or "(skipped)"))
    print("  wrote %s and %s" % (args.json_out, args.md_out))
    if errors:
        for e in errors:
            print("INVARIANT ERROR: %s" % e, file=sys.stderr)
        return 1
    print("VERDICT: stats consistent; colorimetric report quotable")
    return 0


# ---------------------------------------------------------------------------
# Outputs (JSON + Markdown, both fully derived from `stats` + `meta`)
# ---------------------------------------------------------------------------

def loss_band_rows(stats):
    """Rows of the near-threshold hardness band [0.99, 1.0)."""
    return stats["bins"][NEAR_THRESHOLD_BAND]["count"]


def hardness_cross_check(stats, worst):
    """Sanity link to the hardness-map population: colors whose recomputed loss
    sits in [0.99, 1.0) resisted integer-lattice search the hardest (the
    hardness map derives from those survivors). Two independent signals:
      * OVERLAP: does the worst-Delta-E population come from that band?
      * CLUSTERING: do the worst-Delta-E colors sit at the lightness
        extremes (the hardness-map finding: hardness clusters near extreme
        saturation/value), measured as mean L* of each population."""
    total = processed(stats)
    hard = loss_band_rows(stats)
    base = hard / total if total else 0.0
    overlaps = {}
    for k in (50, 100, 200):
        sub = worst[:k]
        if not sub:
            continue
        hits = sum(1 for e in sub if e[3] >= LOSS_BINS[NEAR_THRESHOLD_BAND])
        overlaps[str(k)] = {
            "hits": hits,
            "expectedByChance": round(k * base, 2),
            "enrichmentFactor": (hits / (k * base)) if k * base > 0 else None,
        }
    top_losses = [e[3] for e in worst]
    # Clustering: mean L* (D65) of the worst-DE targets vs. the near-threshold
    # band vs. the whole dataset. A spatial signal ties colorimetric worst
    # cases to the same extreme regions the hardness map reports.
    def mean_lstar(entries):
        if not entries:
            return None
        return sum(srgb_int_to_lab(*target_of(e[1]))[0] for e in entries) / len(entries)
    all_l = sum(b["l_sum"] for b in stats["bins"])
    dataset_mean_l = all_l / total if total else None
    hard_mean_l = stats["bins"][NEAR_THRESHOLD_BAND]["l_sum"] / hard if hard else None
    return {
        "population": "recomputed loss in [0.99, 1.0) (near threshold)",
        "populationRows": hard,
        "populationShare": base,
        "worstTopKOverlap": overlaps,
        "meanLossOfWorstTopK": _r(sum(top_losses) / len(top_losses)) if top_losses else None,
        "meanLossOverall": _r(stats["loss_sum"] / total) if total else None,
        "clustering": {
            "note": "mean L* (D65) of the target colors; lower means darker",
            "worstDE": _r(mean_lstar(worst), 10),
            "nearThresholdBand": _r(hard_mean_l, 10),
            "wholeDataset": _r(dataset_mean_l, 10),
        },
        "note": ("proxy for the hardness-map population pending the survivor-based map; its "
                 "survivor lists replace this; recompute the overlap against the map "
                 "when it lands"),
    }


def _bins_out(stats):
    out = []
    for i in range(len(LOSS_BINS) - 1):
        band = stats["bins"][i]
        lo, hi = LOSS_BINS[i], LOSS_BINS[i + 1]
        if math.isfinite(hi):
            label = "%.2f <= loss < %.2f" % (lo, hi)
        else:
            label = "loss >= 1 (gate violation)"
        out.append({
            "lossBand": label,
            "rows": band["count"],
            "meanDE2000": _r(band["de_sum"] / band["count"]) if band["count"] else None,
            "maxDE2000": band["de_max"][0] if band["de_max"][1] is not None else None,
            "maxAt": fmt_hex(band["de_max"][1]),
            "meanTargetLstar": _r(band["l_sum"] / band["count"], 10) if band["count"] else None,
        })
    return out


def build_json(stats, meta, worst, detail, errors):
    n = processed(stats)
    hl = headline(stats)
    med, p90, p99, p999 = report_percentiles(stats)
    bands = [{"below": b, "interpretation": why, "rowsBelow": band_below(stats, b),
              "share": 100.0 * band_below(stats, b) / n if n else 0.0} for b, why in BANDS]
    top_rows = []
    for de_q, row_id, de_f, loss in worst:
        chain, stored = detail.get(row_id, (None, None))
        target = target_of(row_id)
        top_rows.append({
            "id": row_id,
            "hex": fmt_hex(row_id),
            "dE2000Quantized": de_q,
            "dE2000Float": de_f,
            "recomputedLoss": loss,
            "storedLoss": stored,
            "targetRgb": list(target),
            "targetLstar": srgb_int_to_lab(*target)[0],
            "witness": chain,
        })
    doc = {
        "schema": "de2000-stats/1",
        "claim": hl["statement"],
        "headline": {
            "quotableMaxDE2000": hl["quotableBound"],
            "measuredMaxDE2000": hl["max"],
            "meanDE2000": _r(hl["mean"]),
            "worstQuantizedAt": fmt_hex(stats["de_max_q"][1]),
            "worstFloatAt": fmt_hex(stats["de_max_f"][1]),
        },
        "rows": {
            "processed": stats["total"],
            "passed": stats["pass"],
            "failed": stats["fail"],
            "unparseable": stats["unparseable"],
            "storedMismatches": stats["stored_mismatch"],
            "gaps": stats["gaps"],
            "fractionalWitnessRows": stats["fractional"],
            "meanRecomputedLoss": _r(stats["loss_sum"] / n) if n else None,
        },
        "deltaE2000Quantized": {
            "max": stats["de_max_q"][0],
            "mean": _r(stats["de_sum_q"] / n) if n else None,
            "medianBucket": list(med),
            "p90Bucket": list(p90),
            "p99Bucket": list(p99),
            "p99_9Bucket": list(p999),
        },
        "deltaE2000Float": {
            "max": stats["de_max_f"][0],
            "mean": _r(stats["de_sum_f"] / n) if n else None,
        },
        "histogram": {"edges": EDGES, "counts": stats["hist"]},
        "perceptibilityBands": bands,
        "perChannelError": {
            "quantized": {
                "maxR": stats["ch_int_max"][0], "maxG": stats["ch_int_max"][1],
                "maxB": stats["ch_int_max"][2],
                "nonzeroRowsR": stats["ch_int_nonzero"][0],
                "nonzeroRowsG": stats["ch_int_nonzero"][1],
                "nonzeroRowsB": stats["ch_int_nonzero"][2],
            },
            "float": {
                "maxR": stats["ch_float_max"][0], "maxG": stats["ch_float_max"][1],
                "maxB": stats["ch_float_max"][2],
            },
        },
        "lossBands": _bins_out(stats),
        "hardnessCrossCheck": hardness_cross_check(stats, worst),
        "worst": top_rows,
        "method": meta,
        "invariantErrors": errors,
    }
    return json.dumps(doc, indent=2)


def _md_table(L, headers, rows):
    """One Markdown table; separator cells mirror the header cell widths."""
    L.append("| " + " | ".join(headers) + " |")
    L.append("| " + " | ".join("-" * len(h) for h in headers) + " |")
    for r in rows:
        L.append("| " + " | ".join(r) + " |")


def build_markdown(stats, meta, worst, detail, errors):
    n = processed(stats)
    hl = headline(stats)
    L = []
    L.append("# Delta-E2000 colorimetric stats for the CSS filter covering dataset")
    L.append("")
    L.append("Snapshot %s, artifact sha256 `%s`, generated %s by `%s`. Every number below is recomputable from the dataset artifact alone:"
             % (SNAPSHOT, (meta["artifact"]["sha256"] or "(checksum skipped)"),
                meta["generatedUtc"], meta["tool"]))
    L.append("")
    L.append("```sh")
    L.append("python3 research/colorimetry/de2000_stats.py scan --jobs 0")
    L.append("```")
    L.append("")
    L.append("## The quotable statement")
    L.append("")
    L.append("> **%s**" % hl["statement"])
    L.append("")
    if stats["fractional"]:
        L.append("(Strictly: %d witnesses use a documented fractional parameter; the sentence holds for integer-only chains on the remaining %s colors. The fractional exceptions are listed in docs/dataset.md and included in every number here.)"
                 % (stats["fractional"], "{:,}".format(n - stats["fractional"])))
        L.append("")
    if stats["fail"] or stats["unparseable"]:
        L.append("**The covering gate is violated in this artifact** (%d failures, %d unparseable); the colorimetric numbers describe the stored witnesses, but the covering claim itself does not hold. See the verifier README."
                 % (stats["fail"], stats["unparseable"]))
        L.append("")
    L.append("The rendered RGB comes from the independent verifier's model (`research/verifier/verify_covering.py`, the same trust path as the <1% covering claim), converted to CIELAB (D65) and scored with CIEDE2000 against the target. The headline uses the browser-quantized rendering (8-bit codes, what a user sees); the float-model variant is reported alongside. `selftest` reproduces all 34 published test pairs of Sharma/Wu/Dalley 2005 (Table I) and the published sRGB-primary CIELAB anchors within 4-decimal rounding.")
    L.append("")
    L.append("## Headline numbers")
    L.append("")
    med, p90, p99, p999 = report_percentiles(stats)
    _md_table(L, ["quantity", "value"], [
        ["colors scored", "{:,}".format(n)],
        ["max Delta-E2000 (quantized rendering)", "%.6f at `%s`"
         % (stats["de_max_q"][0], fmt_hex(stats["de_max_q"][1]))],
        ["max Delta-E2000 (float rendering)", "%.6f at `%s`"
         % (stats["de_max_f"][0], fmt_hex(stats["de_max_f"][1]))],
        ["mean Delta-E2000 (quantized)", "%.6f" % (stats["de_sum_q"] / n)],
        ["mean Delta-E2000 (float)", "%.6f" % (stats["de_sum_f"] / n)],
        ["median / p90 / p99 / p99.9",
         "in buckets [%.4f, %.4f) / [%.4f, %.4f) / [%.4f, %.4f) / [%.4f, %.4f)"
         % (med[0], med[1], p90[0], p90[1], p99[0], p99[1], p999[0], p999[1])],
        ["per-channel max error, quantized (8-bit code values)",
         "R %d, G %d, B %d" % tuple(stats["ch_int_max"])],
        ["per-channel max error, float (0-255)",
         "R %.4f, G %.4f, B %.4f" % tuple(stats["ch_float_max"])],
        ["rows with nonzero quantized channel error",
         "R %s, G %s, B %s" % tuple("{:,}".format(v) for v in stats["ch_int_nonzero"])],
    ])
    L.append("")
    L.append("## Distribution of Delta-E2000")
    L.append("")
    dist_rows = []
    for b, why in BANDS:
        c = band_below(stats, b)
        dist_rows.append(["%.2f" % b, why, "{:,}".format(c), "%.4f%%" % (100.0 * c / n)])
    _md_table(L, ["Delta-E2000 below",
                  "interpretation (Sharma 2005 / Mahy et al. 1994 published bands)",
                  "colors", "share"], dist_rows)
    L.append("")
    L.append("Full histogram: %d buckets over the %d edges (%g to %g; the first bucket "
             "is [0, %g) and the last is [%g, inf)) in `de2000_stats.json`."
             % (len(EDGES) + 1, len(EDGES), EDGES[0], EDGES[-1], EDGES[0], EDGES[-1]))
    L.append("")
    L.append("## Worst-scoring colors")
    L.append("")
    worst_rows = []
    for i, (de_q, row_id, de_f, loss) in enumerate(worst):
        chain, stored = detail.get(row_id, (None, None))
        scored = score_row(row_id, chain, stored) if chain else None
        target = target_of(row_id)
        if scored is not None:
            ir = tuple(round(v) for v in scored.rgb)  # measured, not reconstructed
        else:
            ir = target
        worst_rows.append([str(i + 1), "`%s`" % fmt_hex(row_id), "%.4f" % de_q, "%.4f" % de_f,
                           "%.5f" % loss,
                           "%.6f" % stored if stored is not None and stored == stored else "-",
                           "%d,%d,%d" % target, "%d,%d,%d" % ir, "`%s`" % (chain or "-")])
    _md_table(L, ["rank", "color", "Delta-E2000", "float", "recomputed loss", "stored loss",
                  "target rgb", "rendered int", "witness"], worst_rows)
    L.append("")
    L.append("These are all %d retained worst colors; the JSON's `worst[]` adds the per-row "
             "target L* and machine-readable fields." % len(worst))
    L.append("")
    L.append("## Hardness cross-check")
    L.append("")
    L.append("`loss` is the mixed RGB+HSL rendered metric of the covering claim. Colors whose loss sits just under the threshold (>= 0.99) are the near-threshold population that burned search escalation rounds: the same survivors the hardness map artifact is built from. Mean Delta-E2000 per loss band and the overlap of the worst Delta-E population with the near-threshold band test whether colorimetric difficulty and search difficulty share a cause:")
    L.append("")
    band_rows = []
    for row in _bins_out(stats):
        band_rows.append([row["lossBand"], "{:,}".format(row["rows"]),
                          "%.6f" % row["meanDE2000"] if row["meanDE2000"] is not None else "-",
                          "%.6f" % row["maxDE2000"] if row["maxDE2000"] is not None else "-",
                          "`%s`" % row["maxAt"],
                          "%.1f" % row["meanTargetLstar"] if row["meanTargetLstar"] is not None else "-"])
    _md_table(L, ["loss band", "rows", "mean Delta-E2000", "max Delta-E2000", "at",
                  "mean target L*"], band_rows)
    hc = hardness_cross_check(stats, worst)
    cl = hc["clustering"]
    overlap = ["- overlap with the worst %s Delta-E colors: %s of them in the band (chance: %.1f%s)"
               % (k, ov["hits"], ov["expectedByChance"],
                  (", enrichment x%.1f" % ov["enrichmentFactor"]) if ov["enrichmentFactor"] else "")
               for k, ov in hc["worstTopKOverlap"].items()]
    overlap.append("- mean recomputed loss of the worst %d Delta-E colors: %.5f (overall mean recomputed loss: %.5f)."
                   % (len(worst), hc["meanLossOfWorstTopK"], hc["meanLossOverall"]))
    L.append("")
    L.append("Near-threshold band (`0.99 <= loss < 1.00`): %s rows (%.4f%% of all)."
             % ("{:,}".format(hc["populationRows"]), 100.0 * hc["populationShare"]))
    L.append("")
    for line in overlap:
        L.append(line)
    L.append("")
    if None not in (cl["worstDE"], cl["nearThresholdBand"], cl["wholeDataset"]):
        L.append("Clustering (mean target L*, D65): worst-%d Delta-E population %.1f; near-threshold band %.1f; whole cube %.1f."
                 % (len(worst), cl["worstDE"], cl["nearThresholdBand"], cl["wholeDataset"]))
    else:
        L.append("Clustering (mean target L*): worst-DE %s; near-threshold %s; dataset %s."
                 % tuple("n/a" if cl[k] is None else "%.1f" % cl[k]
                         for k in ("worstDE", "nearThresholdBand", "wholeDataset")))
    L.append("")
    L.append("This section reports cross-check numbers only. What they mean is prose, not code: it lives in README.md and the writeup and must be re-checked against each regenerated snapshot. The loss-band population is a proxy: the survivor-based hardness map supersedes it. Rerun `scan` when it lands.")
    L.append("")
    L.append("## Method and runtime")
    L.append("")
    bullets = [
        "- sRGB -> CIELAB (D65): IEC 61966-2-1 inverse gamma + matrix, reference white (0.95047, 1.0, 1.08883). CIEDE2000 exactly as published by Sharma, Wu & Dalley (2005), kL = kC = kH = 1. All 34 Table I pairs are reproduced to 4-decimal rounding by `selftest`. Cross-validated against the independent `coloraide` implementation (`crosscheck_coloraide.py`). Every published worst-row value can also be recomputed without this tool's colorimetry at all via `recheck_rows_coloraide.py` (optional dev deps).",
        "- Each row: witness parsed and rendered by the verifier's `parse_chain`/`render_chain`, loss recomputed by its `rendered_loss` with `verify_row`-identical status semantics (proved by selftest), then CIELAB + CIEDE2000 for the quantized and float renderings.",
        "- Quantized rendering uses round() to 8-bit codes. Exact-half ties, if a witness has one, can flip one code value across platforms inside the verifier's browser-golden tolerance (1.0/255). The float columns quantify the per-snapshot magnitude.",
        "- Runtime: %.1f s over all %s rows with %d job(s) on %s (%d CPUs), Python %s %s. Streaming `SELECT ... WHERE id BETWEEN ? AND ?` over contiguous id ranges (the verifier's scan shape). Cost is transcendental-bound at about 20 math calls per row (9 cbrt, 4 atan2, plus the CIEDE2000 trig) and scales linearly in jobs."
        % (meta["runtimeSeconds"], "{:,}".format(TOTAL_ROWS), meta["jobs"], meta["platform"],
           meta["cpuCount"], meta["pythonImplementation"], meta["python"]),
        "- Machine-readable stats: `de2000_stats.json` (histogram edges/counts, bands, worst colors, method, checksum). This Markdown file and the JSON are both produced by one `scan` run from the artifact alone. Runtime and timestamp are the only run-dependent fields. Averages are stored rounded to 10+ decimals, so the numbers are byte-stable across job counts: float summation noise stays below the rounding.",
    ]
    for b in bullets:
        L.append(b)
        L.append("")
    if errors:
        L.append("## Invariant errors")
        L.append("")
        for e in errors:
            L.append("- %s" % e)
            L.append("")
    L.append("License: MIT (tooling), matching the library; dataset CC-BY-4.0.")
    L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestColorimetry(unittest.TestCase):
    """Published-data known answers: sRGB->Lab anchors and the full 34-pair
    CIEDE2000 supplementary test set of Sharma, Wu & Dalley 2005 (Table I)."""

    def test_black_and_white_anchors(self):
        self.assertEqual(srgb_int_to_lab(0, 0, 0), (0.0, 0.0, 0.0))
        # The published IEC 61966-2-1 Y row sums to 1.0000001 (last-digit
        # rounding of the standard), so white lands at L* = 100.0000038 --
        # expected, and irrelevant to Delta-E since both samples pass through
        # the same transform.
        L, a, b = srgb_int_to_lab(255, 255, 255)
        ysum = 0.2126729 + 0.7151522 + 0.0721750
        self.assertAlmostEqual(L, 116.0 * _cbrt(ysum) - 16.0, delta=1e-9)
        self.assertLess(abs(a), 1e-3)
        self.assertLess(abs(b), 1e-3)

    def test_primary_anchors_published(self):
        for rgb, want in SRGB_PUBLISHED_LAB.items():
            got = srgb_int_to_lab(*rgb)
            for g, w in zip(got, want):
                self.assertAlmostEqual(g, w, delta=0.02,
                                       msg="%r -> %r vs published %r" % (rgb, got, want))

    def test_sharma_2005_table_i_all_34_pairs(self):
        worst_dev = 0.0
        for L1, a1, b1, L2, a2, b2, want in SHARMA_2005_TABLE_I:
            got = ciede2000((L1, a1, b1), (L2, a2, b2))
            worst_dev = max(worst_dev, abs(got - want))
            self.assertAlmostEqual(got, want, delta=5e-4,
                                   msg="pair %r: got %.6f want %.4f"
                                       % ((L1, a1, b1, L2, a2, b2), got, want))
        self.assertLess(worst_dev, 5e-4)

    def test_symmetry_and_identity(self):
        lab1 = srgb_int_to_lab(123, 200, 45)
        lab2 = srgb_int_to_lab(200, 13, 99)
        self.assertAlmostEqual(ciede2000(lab1, lab2), ciede2000(lab2, lab1), delta=1e-12)
        self.assertEqual(ciede2000(lab1, lab1), 0.0)

    def test_lightness_only_hand_answers(self):
        # Achromatic pairs reduce to dE00 = dL' / SL with Lbar at the midpoint:
        # dL = 1 at Lbar 49.5 -> SL = 1 + 0.015*0.25/sqrt(20.25) (hand-checked).
        self.assertAlmostEqual(ciede2000((50.0, 0.0, 0.0), (49.0, 0.0, 0.0)),
                               1.0 / (1.0 + 0.015 * 0.25 / math.sqrt(20.25)), delta=1e-12)
        # L* 0 vs 50: Lbar 25, d50^2 = 625, SL = 1 + 0.015*625/sqrt(645).
        self.assertAlmostEqual(ciede2000((0.0, 0.0, 0.0), (50.0, 0.0, 0.0)),
                               50.0 / (1.0 + 0.015 * 625.0 / math.sqrt(645.0)), delta=1e-12)

    def test_adjacent_codes_are_tiny(self):
        lab0 = srgb_int_to_lab(0, 0, 0)
        lab1 = srgb_int_to_lab(0, 0, 1)
        d = ciede2000(lab0, lab1)
        self.assertGreater(d, 0.0)
        self.assertLess(d, 1.0)

    def test_float_lab_matches_int_lab_on_codes(self):
        for r, g, b in ((0, 0, 0), (255, 255, 255), (66, 222, 173), (56, 202, 194)):
            li = srgb_int_to_lab(r, g, b)
            lf = srgb_float_to_lab(float(r), float(g), float(b))
            for a, c in zip(li, lf):
                self.assertAlmostEqual(a, c, delta=1e-12)

    def test_ciede2000_accepts_lab_tuples_from_row_core(self):
        # de of a row against itself must be zero in both variants when the
        # chain renders the target exactly (identity chain on #000000).
        s = score_row(0x000000,
                      "invert(0%) sepia(0%) saturate(100%) hue-rotate(0deg) brightness(100%) contrast(100%)",
                      0.0)
        self.assertEqual(s.de_q, 0.0)
        self.assertEqual(s.de_f, 0.0)


class TestHistogram(unittest.TestCase):

    def test_edges_monotonic_and_cover(self):
        self.assertTrue(all(e < f for e, f in zip(EDGES, EDGES[1:])))
        self.assertEqual(EDGES[0], 0.001)
        self.assertEqual(EDGES[-1], 100.0)

    def test_bucket_boundaries(self):
        self.assertEqual(bucket_of(0.0), 0)
        self.assertEqual(bucket_of(0.0009999), 0)
        self.assertEqual(bucket_of(0.001), 1)          # exact hits land above their edge
        self.assertEqual(bucket_of(1.0), len([e for e in EDGES if e <= 1.0]))
        self.assertEqual(bucket_of(100.0), len([e for e in EDGES if e <= 100.0]))
        self.assertEqual(bucket_of(1000.0), len(EDGES))

    def test_band_below_and_percentile(self):
        stats = _blank_stats()
        stats["total"] = 1001
        for k in range(1001):
            stats["hist"][bucket_of(k * 0.0005)] += 1
        lo, hi = percentile(stats, 99.0)
        self.assertLess(hi, 0.55)
        self.assertGreaterEqual(lo, 0.4)
        # 0.5 is an edge; the k=1000 row sits exactly on it and lands ABOVE it.
        self.assertEqual(band_below(stats, 0.5), 1000)
        self.assertEqual(band_below(stats, 0.55), 1001)


class TestRowSemantics(unittest.TestCase):
    """score_row must agree with the verifier's own verify_row everywhere:
    same statuses, same loss: the colorimetry changes nothing about the
    gate's arithmetic."""

    CASES = [
        (0x42DEAD, "invert(95%) sepia(18%) saturate(20940%) hue-rotate(66deg) brightness(157%) contrast(74%)", 0.8793432176),
        (0xFBFC02, "invert(26.2%) sepia(78.3%) saturate(4245.5%) hue-rotate(56.9deg) brightness(241.7%) contrast(98.3%)", 0.9697630455),
        (0xA1A1A1, "invert(59%) sepia(37%) saturate(0%) hue-rotate(237deg) brightness(91%) contrast(166%)", 0.7814227320),
        (0x000000, "invert(0%) sepia(0%) saturate(100%) hue-rotate(0deg) brightness(100%) contrast(100%)", 0.0),
        (0x000000, "not a witness", 0.0),
    ]

    def test_score_row_agrees_with_verify_row(self):
        for row_id, chain, stored in self.CASES:
            s1 = score_row(row_id, chain, stored)
            s2 = verify_row(row_id, chain, stored)
            if s1 is None:
                self.assertEqual(s2[0], "unparseable")
                continue
            self.assertEqual(s1.status, s2[0])
            self.assertEqual(s1.loss, s2[1])  # bit-identical: the same rendered_loss call
            self.assertGreaterEqual(s1.de_q, 0.0)
            self.assertGreaterEqual(s1.de_f, 0.0)
            for e in s1.ch_int_err:
                self.assertIn(e, (0, 1))   # loss < 1 forces sub-1 float error
            for e in s1.ch_float_err:
                self.assertLess(e, 1.0)

    def test_known_rows_colorimetry(self):
        s = score_row(0x42DEAD, self.CASES[0][1], self.CASES[0][2])
        self.assertLess(s.de_q, 0.5)
        self.assertLess(s.de_f, 0.5)


class TestSyntheticScan(unittest.TestCase):
    """End-to-end invariants on a small hand-built DB: disjoint counters,
    histogram totals equal scored rows, top heap ordered and complete."""

    ROWS = [
        (0, "invert(0%) sepia(0%) saturate(100%) hue-rotate(0deg) brightness(100%) contrast(100%)", 0.0),
        (1, "invert(95%) sepia(18%) saturate(20940%) hue-rotate(66deg) brightness(157%) contrast(74%)", 0.9999),
        (2, "invert(0%) sepia(0%) saturate(0%) hue-rotate(0deg) brightness(0%) contrast(100%)", 0.5),
        (3, "garbage", 0.0),
        (4, "invert(26.2%) sepia(78.3%) saturate(4245.5%) hue-rotate(56.9deg) brightness(241.7%) contrast(98.3%)", 0.9697630455),
    ]

    def _make_db(self, path):
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE color (id INTEGER PRIMARY KEY, filter TEXT, loss REAL)")
        conn.executemany("INSERT INTO color VALUES (?, ?, ?)", self.ROWS)
        conn.commit()
        conn.close()

    def test_scan_invariants(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "t.sqlite3")
            self._make_db(path)
            stats = scan_ranges(path, [(0, TOTAL_ROWS - 1)], jobs=1)
            self.assertEqual(stats["total"], 5)
            self.assertEqual(stats["unparseable"], 1)
            self.assertEqual(stats["fractional"], 1)  # the #fbfc02-style row
            self.assertEqual(stats["pass"] + stats["fail"] + stats["stored_mismatch"] + stats["unparseable"],
                             stats["total"])
            self.assertEqual(sum(stats["hist"]), processed(stats))
            direct = [score_row(r[0], r[1], r[2]) for r in self.ROWS]
            scored = [s for s in direct if s is not None]
            worst_de = max(s.de_q for s in scored)
            self.assertAlmostEqual(stats["de_max_q"][0], worst_de, delta=1e-12)
            self.assertEqual(len(stats["top"]), len(scored))
            self.assertEqual(stats["top"], sorted(stats["top"]))
            self.assertEqual(sum(b["count"] for b in stats["bins"]), processed(stats))
            # NaN stored losses must not crash status handling:
            stats2 = _blank_stats()
            _tally(stats2, 0, self.ROWS[0][1], float("nan"))
            self.assertEqual(stats2["pass"], 1)

    def test_build_outputs_dont_crash(self):
        stats = _blank_stats()
        _tally(stats, 0, self.ROWS[0][1], 0.0)
        _tally(stats, 1, self.ROWS[1][1], 0.9999)
        _tally(stats, 3, self.ROWS[3][1], 0.0)
        worst = sorted(stats["top"], key=lambda e: e[0], reverse=True)
        detail = {w[1]: ("chain text", 0.9999) for w in worst}
        meta = method_meta("nowhere", 1.0, 1)
        meta["generatedUtc"] = "x"
        doc = json.loads(build_json(stats, meta, worst, detail, []))
        self.assertEqual(doc["rows"]["processed"], 3)
        md = build_markdown(stats, meta, worst, detail, [])
        self.assertIn("quotable statement", md)


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(
        prog="de2000_stats.py",
        description="Delta-E2000 and per-channel colorimetric stats through the "
                    "covering-dataset verifier's model.")
    parser.add_argument("--db", help="path to the covering-dataset sqlite artifact "
                                     "(auto-discovered from the library cache if omitted)")
    sub = parser.add_subparsers(dest="mode", required=True)

    p = sub.add_parser("scan", help="compute the full colorimetric report; writes JSON + Markdown")
    p.add_argument("--jobs", type=int, default=1, help="parallel id-range workers (0 = all cores)")
    p.add_argument("--stored-tol", type=float, default=1e-9)
    p.add_argument("--expect-rows", type=int, default=TOTAL_ROWS, help="artifact row-count gate (0 disables)")
    p.add_argument("--json-out", default=os.path.join(here, "de2000_stats.json"))
    p.add_argument("--md-out", default=os.path.join(here, "de2000_summary.md"))
    p.add_argument("--progress", action="store_true")
    p.add_argument("--no-sha256", dest="sha256", action="store_false",
                   help="skip the artifact checksum (a few seconds on 1.7 GiB)")
    p.set_defaults(func=cmd_scan, sha256=True)

    p = sub.add_parser("sample", help="stats over N random rows (no files written)")
    p.add_argument("--n", type=int, default=100000)
    p.add_argument("--seed", type=int, default=1)
    p.set_defaults(func=cmd_sample)

    p = sub.add_parser("row", help="full colorimetric detail for one color")
    p.add_argument("color", help="hex target, e.g. #38cac2")
    p.set_defaults(func=cmd_row)

    p = sub.add_parser("selftest", help="published-data known answers + invariant tests")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_selftest)

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
