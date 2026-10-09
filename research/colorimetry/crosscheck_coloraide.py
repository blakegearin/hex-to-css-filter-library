#!/usr/bin/env python3
"""Dev-only cross-validation of de2000_stats.py against the independent
`coloraide` color library (pip install coloraide; NOT a runtime dependency
of the artifact; the published stats only need the Python standard library).

Compares, on seeded-random and adversarial inputs:
  1. the pure CIEDE2000 formula on Lab pairs (white-point independent) --
     agreement should be float noise;
  2. the sRGB -> CIELAB (D65) conversion per channel value;
  3. end-to-end Delta-E2000 between pairs of 8-bit sRGB colors.

Known convention differences, reported but not failed: coloraide derives the
D65 reference white from the chromaticity coordinates (0.9504559, 1,
1.0890578) and carries the sRGB->XYZ matrix to more digits, while this tool
uses the classical CIE tabulated white (0.95047, 1, 1.08883) and the
published IEC 61966-2-1 rounded matrix, the convention the published
sRGB-primary CIELAB anchors are computed with. It shifts individual L*a*b*
values by up to ~1.1e-2 (measured over 200k triples) and cancels almost
entirely inside a Delta-E between two nearby colors (<3e-4 measured; targets
and renderings always are).

Usage: python3 crosscheck_coloraide.py [--lab-pairs 200000] [--srgb-pairs 50000]
Exit 0 = agreement within documented tolerances.
"""

import argparse
import random
import sys

import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from de2000_stats import ciede2000, srgb_int_to_lab  # noqa: E402

from coloraide import Color  # noqa: E402


def ours(lab1, lab2):
    return ciede2000(lab1, lab2)


def theirs(lab1, lab2):
    c1 = Color("lab-d65", data=list(lab1))
    c2 = Color("lab-d65", data=list(lab2))
    return c1.delta_e(c2, method="2000")


def lab_d65(rgb01):
    return Color("srgb", data=list(rgb01)).convert("lab-d65").coords()


def rand_lab_pair(rng):
    mode = rng.random()
    if mode < 0.2:  # both near achromatic (the atan2/mean-hue edge cases)
        L1, L2 = rng.uniform(0, 100), rng.uniform(0, 100)
        return (L1, 0.0, 0.0), (L2, rng.uniform(-1e-4, 1e-4), rng.uniform(-1e-4, 1e-4))
    if mode < 0.4:  # hue straddling the 0/360 wrap
        a = rng.uniform(-1, 1)
        b1 = -abs(rng.uniform(0.01, 20))
        b2 = abs(rng.uniform(0.01, 20))
        return (rng.uniform(20, 80), a, b1), (rng.uniform(20, 80), a, b2)
    if mode < 0.55:  # one color exactly neutral (pairs 7/8 of the published set)
        return (rng.uniform(0, 100), 0.0, 0.0), (rng.uniform(0, 100), rng.uniform(-128, 128), rng.uniform(-128, 128))
    return ((rng.uniform(0, 100), rng.uniform(-128, 128), rng.uniform(-128, 128)),
            (rng.uniform(0, 100), rng.uniform(-128, 128), rng.uniform(-128, 128)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lab-pairs", type=int, default=200000)
    ap.add_argument("--srgb-pairs", type=int, default=50000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    # 1) pure formula on Lab pairs.
    worst = 0.0
    for _ in range(args.lab_pairs):
        lab1, lab2 = rand_lab_pair(rng)
        d = abs(ours(lab1, lab2) - theirs(lab1, lab2))
        worst = max(worst, d)
    print("1) CIEDE2000 on %d random Lab pairs: max |ours - coloraide| = %.3e"
          % (args.lab_pairs, worst))
    formula_ok = worst < 1e-8

    # 2) sRGB -> CIELAB per code triple.
    worst_lab = [0.0, 0.0, 0.0]
    for _ in range(args.srgb_pairs):
        rgb = [rng.randrange(256) for _ in range(3)]
        ours_lab = srgb_int_to_lab(*rgb)
        theirs_lab = lab_d65([c / 255.0 for c in rgb])
        for i in range(3):
            worst_lab[i] = max(worst_lab[i], abs(ours_lab[i] - theirs_lab[i]))
    print("2) sRGB->Lab on %d random code triples: max |dL*| %.5f, |da*| %.5f, |db*| %.5f"
          % (args.srgb_pairs, *worst_lab))
    lab_ok = max(worst_lab) < 2e-2  # white-point/matrix convention, measured ~1.1e-2

    # 3) end-to-end Delta-E2000 between 8-bit sRGB pairs.
    worst_de = 0.0
    for _ in range(args.srgb_pairs):
        c1 = [rng.randrange(256) for _ in range(3)]
        c2 = [min(255, max(0, c + rng.choice((-2, -1, 0, 1, 2)))) for c in c1]
        ours_lab1, ours_lab2 = srgb_int_to_lab(*c1), srgb_int_to_lab(*c2)
        their_lab1, their_lab2 = lab_d65([v / 255.0 for v in c1]), lab_d65([v / 255.0 for v in c2])
        d = abs(ours(ours_lab1, ours_lab2) - theirs(their_lab1, their_lab2))
        worst_de = max(worst_de, d)
    print("3) end-to-end Delta-E2000 on %d nearby sRGB pairs: max |ours - coloraide| = %.5f"
          % (args.srgb_pairs, worst_de))
    de_ok = worst_de < 5e-3

    if formula_ok and lab_ok and de_ok:
        print("CROSSCHECK PASS: formula agrees to %.1e; conversion differs" % worst)
        print("only by the documented D65-white/matrix convention (~1e-2 in L*a*b*,")
        print("end-to-end Delta-E of nearby colors agrees to %.1e)." % worst_de)
        return 0
    print("CROSSCHECK FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
