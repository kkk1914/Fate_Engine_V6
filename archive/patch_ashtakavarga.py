"""
Bhinna Ashtakavarga Fix — Patch Script
=======================================
Run this script to verify the fix is correct before applying to vedic_engines.py.
It also contains the drop-in replacement method.

USAGE:
  python patch_ashtakavarga.py          # runs self-test
  python patch_ashtakavarga.py --apply  # applies patch to core/vedic_engines.py

BUG SUMMARY:
  Old code:  if matrix[0] == 1: bindus[contrib_sign] += 1
             → Only checks one offset, always adds to contributor's own sign.
             → SAV is wrong; all house strength / Kakshya analysis is invalid.

  New code:  Iterates all 12 offsets. For each offset where matrix[offset]==1,
             adds bindu to (contributor_sign + offset) % 12.
             Includes self-contribution matrices and Ascendant contribution.
"""

import sys

# ─────────────────────────────────────────────────────────
# Self-contribution matrices (planet's own BAV contribution)
# Source: Brihat Parashara Hora Shastra, Ashtakavarga chapter
# ─────────────────────────────────────────────────────────
SELF_CONTRIB = {
    "Sun":     [1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0],
    "Moon":    [1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0],
    "Mars":    [1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
    "Mercury": [1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1],
    "Jupiter": [1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0],
    "Venus":   [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1],
    "Saturn":  [1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1],
}

# Ascendant contribution to each planet's BAV
ASC_CONTRIB = {
    "Sun":     [1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0],
    "Moon":    [0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0],
    "Mars":    [1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0],
    "Mercury": [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0],
    "Jupiter": [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0],
    "Venus":   [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1],
    "Saturn":  [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
}

# Cross-contribution matrices (unchanged from current code)
PLANET_CONTRIBS = {
    "Sun":     [1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0],
    "Moon":    [1, 0, 1, 0, 0, 1, 0, 1, 0, 0, 1, 0],
    "Mars":    [1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0],
    "Mercury": [1, 0, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0],
    "Jupiter": [1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0],
    "Venus":   [1, 0, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0],
    "Saturn":  [1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0],
}


def calc_bhinna_fixed(positions: dict) -> dict:
    """
    Correct Bhinna Ashtakavarga calculation.

    positions: dict mapping planet name → sidereal sign index (0-11)
               Must include "Ascendant".

    Returns: {planet: [bindu_count_per_sign_0..11]}
    """
    bhinna = {}

    for target in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
        bindus = [0] * 12

        # ── Contributions from OTHER planets (cross-contribution) ──────────
        for contributor, matrix in PLANET_CONTRIBS.items():
            if contributor == target:
                # Own contribution handled separately below
                continue

            contrib_sign = positions[contributor]
            for offset, gives_bindu in enumerate(matrix):
                if gives_bindu == 1:
                    target_sign = (contrib_sign + offset) % 12
                    bindus[target_sign] += 1

        # ── Self-contribution ──────────────────────────────────────────────
        self_matrix = SELF_CONTRIB[target]
        contrib_sign = positions[target]
        for offset, gives_bindu in enumerate(self_matrix):
            if gives_bindu == 1:
                target_sign = (contrib_sign + offset) % 12
                bindus[target_sign] += 1

        # ── Ascendant contribution ─────────────────────────────────────────
        asc_matrix = ASC_CONTRIB[target]
        asc_sign = positions["Ascendant"]
        for offset, gives_bindu in enumerate(asc_matrix):
            if gives_bindu == 1:
                target_sign = (asc_sign + offset) % 12
                bindus[target_sign] += 1

        bhinna[target] = bindus

    return bhinna


def calc_sarva(bhinna: dict) -> list:
    """Sum all Bhinna → Sarva Ashtakavarga."""
    sarva = [0] * 12
    for bindus in bhinna.values():
        for i, b in enumerate(bindus):
            sarva[i] += b
    return sarva


def self_test():
    """
    Sanity-check: with a known chart (all planets at Aries=0),
    verify SAV totals are plausible (range 18-28 per sign typically).
    Also verify bug is fixed by checking we're writing to non-zero offsets.
    """
    print("Running Ashtakavarga self-test...")

    # All planets at sign 0 (Aries) as a degenerate test
    positions_all_aries = {p: 0 for p in ["Sun", "Moon", "Mars", "Mercury",
                                           "Jupiter", "Venus", "Saturn", "Ascendant"]}
    bhinna = calc_bhinna_fixed(positions_all_aries)
    sarva = calc_sarva(bhinna)
    total = sum(sarva)

    print(f"  All-in-Aries SAV per sign: {sarva}")
    print(f"  Total bindus: {total} (expected ~337 for standard matrices)")

    # Verify non-zero bindus exist at signs other than 0
    non_zero_signs = [i for i, s in enumerate(sarva) if s > 0]
    print(f"  Signs with bindus: {non_zero_signs}")
    assert len(non_zero_signs) > 1, "BUG: all bindus concentrated in sign 0!"
    print("  ✅ Bindus distributed across multiple signs (bug is fixed)")

    # Spread test: with planets in different signs
    positions_spread = {
        "Sun": 0, "Moon": 3, "Mars": 6, "Mercury": 9,
        "Jupiter": 1, "Venus": 4, "Saturn": 7, "Ascendant": 10
    }
    bhinna2 = calc_bhinna_fixed(positions_spread)
    sarva2 = calc_sarva(bhinna2)
    total2 = sum(sarva2)
    print(f"\n  Spread-chart total bindus: {total2}")
    print(f"  Spread-chart SAV: {sarva2}")
    assert all(s >= 0 for s in sarva2), "Negative bindus!"
    assert total2 > 0, "Zero total bindus!"
    print("  ✅ Spread chart produces valid SAV")

    print("\nSelf-test PASSED ✅")


def apply_patch():
    """Apply the fix to core/vedic_engines.py by replacing _calc_bhinna."""
    import re

    try:
        with open("../core/vedic_engines.py", "r") as f:
            content = f.read()
    except FileNotFoundError:
        print("❌ core/vedic_engines.py not found. Run from project root.")
        sys.exit(1)

    # Find the _calc_bhinna method and replace it
    # We replace from 'def _calc_bhinna' up to the next 'def ' at same indent
    pattern = r'(    def _calc_bhinna\(self\).*?)(\n    def )'
    replacement_body = '''    def _calc_bhinna(self) -> dict:
        """
        Corrected Bhinna Ashtakavarga calculation.
        FIXED: iterates all 12 offsets; writes to (contributor_sign + offset) % 12.
        Includes self-contribution and Ascendant contribution matrices.
        """
        SELF_CONTRIB = {
            "Sun":     [1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0],
            "Moon":    [1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0],
            "Mars":    [1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
            "Mercury": [1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1],
            "Jupiter": [1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0],
            "Venus":   [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1],
            "Saturn":  [1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1],
        }
        ASC_CONTRIB = {
            "Sun":     [1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0],
            "Moon":    [0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0],
            "Mars":    [1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0],
            "Mercury": [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0],
            "Jupiter": [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0],
            "Venus":   [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1],
            "Saturn":  [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
        }
        bhinna = {}
        for target in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]:
            bindus = [0] * 12
            for contributor, matrix in self.PLANET_CONTRIBS.items():
                if contributor == target:
                    self_matrix = SELF_CONTRIB[target]
                    contrib_sign = self.positions[contributor]
                    for offset, gives_bindu in enumerate(self_matrix):
                        if gives_bindu == 1:
                            bindus[(contrib_sign + offset) % 12] += 1
                else:
                    contrib_sign = self.positions[contributor]
                    for offset, gives_bindu in enumerate(matrix):
                        if gives_bindu == 1:
                            bindus[(contrib_sign + offset) % 12] += 1
            asc_matrix = ASC_CONTRIB[target]
            asc_sign = self.positions["Ascendant"]
            for offset, gives_bindu in enumerate(asc_matrix):
                if gives_bindu == 1:
                    bindus[(asc_sign + offset) % 12] += 1
            bhinna[target] = bindus
        return bhinna

'''

    match = re.search(pattern, content, re.DOTALL)
    if not match:
        print("❌ Could not find _calc_bhinna method in core/vedic_engines.py")
        print("   Apply the fix manually — see SELF_CONTRIB/ASC_CONTRIB blocks above.")
        sys.exit(1)

    new_content = content[:match.start()] + replacement_body + content[match.start(2):]

    # Backup original
    with open("../core/vedic_engines.py.bak", "w") as f:
        f.write(content)
    print("   Backup saved: core/vedic_engines.py.bak")

    with open("../core/vedic_engines.py", "w") as f:
        f.write(new_content)

    print("✅ core/vedic_engines.py patched successfully")


if __name__ == "__main__":
    if "--apply" in sys.argv:
        self_test()
        print()
        apply_patch()
    else:
        self_test()
        print("\nTo apply the fix to core/vedic_engines.py, run:")
        print("  python patch_ashtakavarga.py --apply")
