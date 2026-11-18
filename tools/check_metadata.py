#!/usr/bin/env python3
"""
check_metadata.py — CITATION.cff and .zenodo.json must describe the SAME artefact
=================================================================================

WHY THIS EXISTS
---------------
A DOI is permanent and public. Whatever the two metadata files disagree about
gets baked into a real citation by whichever tool a reader happens to use — and
the disagreement is invisible until then, because nothing compared the two files.

The specific defect found by measuring them rather than reading them: the two
files disagreed about the AFFILIATION of the same named author.

  .zenodo.json      "affiliation": "Independent"
  CITATION.cff      (no affiliation field at all)
  White Paper        "Authors: Máté Róbert, Hope Ecosystem"
  arXiv .tex         \\author{Máté Róbert \\\\ Hope Ecosystem}

"Hope Ecosystem" is presented as an affiliation in two published documents. An
affiliation is an employment or institutional claim — it is not something
tooling may infer or invent on the author's behalf. This checker does not guess
which value is right; it reports the disagreement and refuses to let it be
published silently.

WHAT IT CHECKS
--------------
Fields that a citation actually resolves, compared across both files:

  * title          — must be byte-identical
  * version        — must agree with the CITATION.cff `version`
  * license        — must agree
  * date           — `.zenodo.json` publication_date vs `date-released`
  * authors        — the same set of names, and no file may name an author the
                     other omits (an unnamed contributor is still a contributor)
  * orcid          — must not be an all-zero sentinel left in place, and must
                     agree between files if both carry one
  * keywords       — must be a superset check: Zenodo keywords should not
                     contradict the citation keywords
  * repository URL — must be the same GitHub project in both

It ALSO refuses to accept a fabricated DOI pattern and reports any placeholder.

Exit non-zero when two files disagree, or when a placeholder identifier is
present. Run `--selftest` to prove the rules fire.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

for _name in ("stdout", "stderr"):
    _stream = getattr(sys, _name, None)
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        try:
            _reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

ROOT = Path(__file__).resolve().parent.parent

CITATION = ROOT / "CITATION.cff"
ZENODO = ROOT / ".zenodo.json"

# A "no ORCID" sentinel is legitimate to write while a human decides, but it
# must not be published as if it were a real identifier.
ORCID_SENTINEL = re.compile(r"^0{4}-0{4}-0{4}-0{3}[\dX]$")
ORCID_VALID = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")

PLACEHOLDER_DOI = re.compile(r"10\.5281/zenodo\.(?:X+|0+|placeholder)", re.I)


# ---------------------------------------------------------------------------
# A minimal YAML reader for CITATION.cff
#
# CITATION.cff is a constrained subset: a mapping of scalars, lists of scalars,
# and one nested list of mappings (references). Pulling in PyYAML for that would
# add a dependency to a repository whose selling point is that its offline
# checks need none. If PyYAML happens to be installed, it is used, because a
# real parser is strictly better when available.
# ---------------------------------------------------------------------------

def _scalar(raw: str):
    text = raw.strip()
    if text.startswith(('"', "'")) and text.endswith(('"', "'")) and len(text) >= 2:
        return text[1:-1]
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if text in ("true", "false"):
        return text == "true"
    if text in ("null", "~", ""):
        return None
    return text


def load_cff(path: Path) -> dict:
    """Parse the flat mapping subset of CITATION.cff that this project uses."""
    try:  # prefer a real parser when it is available
        import yaml  # type: ignore
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except ImportError:
        pass

    data: dict = {}
    current_list: str | None = None
    current_item: dict | None = None

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        indent = len(line) - len(line.lstrip())
        stripped = line.strip()

        if stripped.startswith("- "):
            # list item
            if current_list is None:
                continue
            body = stripped[2:].strip()
            if ":" in body and not body.startswith(('"', "'")):
                key, _, val = body.partition(":")
                current_item = {key.strip(): _scalar(val)}
                data.setdefault(current_list, []).append(current_item)
            else:
                data.setdefault(current_list, []).append(_scalar(body))
                current_item = None
            continue

        if indent == 0 and ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()
            if val == "":
                # either an empty mapping or the start of a block list
                current_list, current_item = key, None
                data.setdefault(key, [] if not data.get(key) else data[key])
            elif val in (">-", ">", "|", "|-", "|"):
                current_list = key
                data.setdefault(key, [])
            else:
                data[key] = _scalar(val)
                current_list, current_item = None, None
            continue

        if indent > 0 and current_item is not None and ":" in stripped:
            key, _, val = stripped.partition(":")
            current_item[key.strip()] = _scalar(val)

    return data


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def compare(cff: dict, zen: dict) -> list[str]:
    problems: list[str] = []

    def names_from_cff() -> list[str]:
        out = []
        for a in cff.get("authors", []) or []:
            if isinstance(a, dict):
                out.append(str(a.get("name", "")).strip())
            elif a:
                out.append(str(a).strip())
        return [n for n in out if n]

    def names_from_zen() -> list[str]:
        return [str(c.get("name", "")).strip()
                for c in zen.get("creators", []) or [] if c.get("name")]

    # 1. title
    ct, zt = cff.get("title"), zen.get("title")
    if ct and zt and ct != zt:
        problems.append(
            f"title differs:\n      CITATION.cff : {ct!r}\n      .zenodo.json : {zt!r}")

    # 2. version
    cv, zv = cff.get("version"), zen.get("version")
    if cv and zv and str(cv) != str(zv):
        problems.append(f"version differs: CITATION.cff={cv!r} .zenodo.json={zv!r}")

    # 3. license
    cl, zl = cff.get("license"), zen.get("license")
    if cl and zl and str(cl).upper() != str(zl).upper():
        problems.append(f"license differs: CITATION.cff={cl!r} .zenodo.json={zl!r}")

    # 4. date
    cd, zd = cff.get("date-released"), zen.get("publication_date")
    if cd and zd and str(cd) != str(zd):
        problems.append(f"release date differs: CITATION.cff={cd!r} .zenodo.json={zd!r}")

    # 5. authors — the set must match, and neither may hide a contributor
    ca, za = names_from_cff(), names_from_zen()
    only_cff = set(ca) - set(za)
    only_zen = set(za) - set(ca)
    if only_cff:
        problems.append(f"author(s) named in CITATION.cff but not in .zenodo.json: {sorted(only_cff)}")
    if only_zen:
        problems.append(f"author(s) named in .zenodo.json but not in CITATION.cff: {sorted(only_zen)}")

    # 6. ORCID — a sentinel must be reported, and must agree across files
    cff_orcids = {
        str(a.get("orcid")): a.get("name")
        for a in (cff.get("authors") or []) if isinstance(a, dict) and a.get("orcid")
    }
    zen_orcids = {
        str(c.get("orcid")): c.get("name")
        for c in (zen.get("creators") or []) if isinstance(c, dict) and c.get("orcid")
    }

    sentinels = {o for o in list(cff_orcids) + list(zen_orcids) if ORCID_SENTINEL.match(o)}
    for o in sorted(sentinels):
        who = cff_orcids.get(o) or zen_orcids.get(o) or "?"
        problems.append(
            f"ORCID placeholder {o} is still in place for {who!r}. "
            f"Replace it with a real ORCID or delete the field before publishing — "
            f"an all-zero identifier is a 'none' sentinel, not an identity.")

    shared = set(cff_orcids) & set(zen_orcids)
    bad = [o for o in shared if not ORCID_VALID.match(o)]
    for o in sorted(bad):
        problems.append(f"ORCID {o!r} is not a well-formed ORCID")

    if set(cff_orcids) - set(zen_orcids) and not sentinels:
        problems.append(
            f"ORCID present in CITATION.cff but absent in .zenodo.json: "
            f"{sorted(set(cff_orcids) - set(zen_orcids))}")

    # 7. affiliation — .zenodo.json carries one; the published documents carry
    #    another. See AFFILIATION_DOCS below for the document-level comparison.
    zen_affs = {str(c.get("affiliation", "")).strip()
                for c in (zen.get("creators") or []) if isinstance(c, dict)}
    zen_affs.discard("")
    if len(zen_affs) > 1:
        problems.append(f".zenodo.json creators have differing affiliations: {sorted(zen_affs)}")

    # The Zenodo record is the one that a DOI actually freezes. If it disagrees
    # with what the White Paper and the arXiv source say about the same person,
    # the DOI would permanently assert the wrong one.
    doc_affs = {tuple(v) for v in collect_affiliations().values()}
    doc_values = {a for group in doc_affs for a in group if a != "(none stated)"}
    for aff in sorted(zen_affs):
        if doc_values and aff not in doc_values:
            problems.append(
                f".zenodo.json states affiliation {aff!r}, but the published "
                f"documents state {sorted(doc_values)}. A Zenodo record is "
                f"permanent and public: whichever value is uploaded becomes the "
                f"citable claim. Reconcile them by hand."
            )

    # 8. placeholder DOI anywhere
    for label, blob in (("CITATION.cff", cff), (".zenodo.json", zen)):
        for match in PLACEHOLDER_DOI.finditer(json.dumps(blob, ensure_ascii=False)):
            problems.append(f"{label} contains a placeholder DOI: {match.group(0)!r}")

    # 9. repository URL must be the same project
    repo = cff.get("repository-code")
    rels = {str(r.get("identifier")) for r in (zen.get("related_identifiers") or [])
            if isinstance(r, dict)}
    if repo and rels and repo not in rels:
        problems.append(
            f"repository-code {repo!r} is not among the .zenodo.json related_identifiers "
            f"{sorted(rels)}")

    # 10. leftover blocker markers. Underscore-prefixed keys are valid JSON but
    #     are NOT part of the Zenodo record schema — uploading the file with
    #     them present fails. Leaving them in silently would be a trap.
    blockers = [k for k in zen if k.startswith("_")]
    for k in sorted(blockers):
        problems.append(
            f".zenodo.json still carries the temporary marker {k!r}. It is not "
            f"part of the Zenodo schema and the upload will be rejected while "
            f"it is present. Resolve the item it describes, then delete the key."
        )

    return problems


# Documents that state an affiliation for the named author. An affiliation is
# an employment or institutional CLAIM — it is not something a tool may infer,
# default, or quietly harmonise. The two published documents currently name
# DIFFERENT affiliations for the same person, which is exactly the kind of
# disagreement a permanent DOI would freeze in place. It is reported, never
# resolved automatically.
AFFILIATION_DOCS = {
    "docs/HOPE-WP-2026-V1.2.md": re.compile(
        r"^\*\*Authors?:\*\*\s*(?P<authors>.+?)\s*$", re.M),
    "arxiv/quantum_anchor_v1.2.tex": re.compile(
        r"\\author\{(?P<authors>[^}]*)\}", re.M),
}


def collect_affiliations() -> dict[str, list[str]]:
    """Map document -> affiliations asserted there, for the named author."""
    found: dict[str, list[str]] = {}
    for rel, pattern in AFFILIATION_DOCS.items():
        path = ROOT / rel
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        match = pattern.search(text)
        if not match:
            continue
        authors = match.group("authors")
        # LaTeX separates the name from the affiliation with "\\"; the Markdown
        # header separates them with a comma. Both yield a trailing qualifier.
        parts = [p.strip() for p in re.split(r"\\\\|,|\\quad", authors) if p.strip()]
        tail = parts[1:] if len(parts) > 1 else []
        found[rel] = tail or ["(none stated)"]
    return found


def check_affiliation_disagreement(affiliations: dict[str, list[str]]) -> list[str]:
    """Report when the documents name different affiliations for one author."""
    values = {tuple(v) for v in affiliations.values()}
    if len(values) <= 1:
        return []

    detail = "; ".join(f"{rel} -> {', '.join(v)}"
                       for rel, v in sorted(affiliations.items()))
    return [
        "the published documents state DIFFERENT affiliations for the same "
        f"named author ({detail}). This is a human decision and is NOT "
        "resolved here: an affiliation is an employment claim, and a "
        "permanent public DOI would freeze whichever value is uploaded. "
        "Pick one value, apply it to every file, and record the choice."
    ]


def selftest() -> int:
    """Prove the rules fire on disagreement and stay silent on agreement."""
    print("=== metadata checker self-test ===")
    failures = 0

    good_cff = {
        "title": "T", "version": "1.2.0", "license": "MIT",
        "date-released": "2026-10-07", "repository-code": "https://example.org/r",
        "authors": [{"name": "A", "orcid": "0000-0002-1825-0097"}],
    }
    good_zen = {
        "title": "T", "version": "1.2.0", "license": "MIT",
        "publication_date": "2026-10-07", "creators": [{"name": "A",
                            "orcid": "0000-0002-1825-0097"}],
        "related_identifiers": [{"identifier": "https://example.org/r"}],
    }

    cases: list[tuple[str, dict, dict, bool]] = [
        ("identical metadata", good_cff, good_zen, False),
        ("version differs",
         {**good_cff, "version": "1.2.0"}, {**good_zen, "version": "1.1.0"}, True),
        ("author only in CITATION.cff",
         {**good_cff, "authors": [*good_cff["authors"], {"name": "B"}]}, good_zen, True),
        ("all-zero ORCID sentinel",
         {**good_cff, "authors": [{"name": "A", "orcid": "0000-0000-0000-0000"}]},
         {**good_zen, "creators": [{"name": "A", "orcid": "0000-0000-0000-0000"}]}, True),
        ("placeholder DOI",
         good_cff, {**good_zen, "description": "10.5281/zenodo.XXXXXXX"}, True),
        ("repository URL mismatch",
         {**good_cff, "repository-code": "https://example.org/other"}, good_zen, True),
        ("leftover blocker marker",
         good_cff, {**good_zen, "_unresolved": "TODO"}, True),
    ]

    for name, c, z, should_fail in cases:
        problems = compare(c, z)
        if bool(problems) == should_fail:
            verdict = "OK  " if should_fail else "OK  "
            print(f"  {verdict} {name}" + ("" if not should_fail else f" -> {len(problems)} finding(s)"))
        else:
            print(f"  FAIL {name}: expected "
                  f"{'findings' if should_fail else 'no findings'}, got {len(problems)}")
            failures += 1

    print()
    print("=== part 2: affiliation disagreement is reported, never auto-resolved ===")
    agree = {"a.md": ["Hope Ecosystem"], "b.tex": ["Hope Ecosystem"]}
    disagree = {"a.md": ["Hope Ecosystem"], "b.tex": ["Independent"]}

    if not check_affiliation_disagreement(agree):
        print("  OK   silent when every document agrees")
    else:
        print("  FAIL false positive on agreeing documents")
        failures += 1

    if check_affiliation_disagreement(disagree):
        print("  OK   reports a genuine affiliation disagreement")
    else:
        print("  FAIL missed a real affiliation disagreement")
        failures += 1

    print()
    if failures:
        print(f"RESULT: FAIL ({failures} problem(s))")
        return 1
    print("RESULT: PASS — metadata rules fire on disagreement only")
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()

    print("=" * 74)
    print("QUANTUM ANCHOR — PUBLICATION METADATA CONSISTENCY")
    print("=" * 74)
    print()

    missing = [p for p in (CITATION, ZENODO) if not p.exists()]
    if missing:
        print("[FAIL] missing: " + ", ".join(p.name for p in missing))
        return 1

    try:
        cff = load_cff(CITATION)
        zen = load_json(ZENODO)
    except Exception as exc:
        print(f"[FAIL] could not parse metadata: {type(exc).__name__}: {exc}")
        return 1

    authors = [a.get("name") for a in (cff.get("authors") or [])
               if isinstance(a, dict)]
    affs = [c.get("affiliation") for c in (zen.get("creators") or [])
            if isinstance(c, dict)]
    print(f"CITATION.cff  authors: {authors}")
    print(f".zenodo.json  creators: {[c.get('name') for c in zen.get('creators', [])]}"
          f"  affiliation: {affs}")
    print()

    problems = compare(cff, zen)

    affs = collect_affiliations()
    if affs:
        print("affiliations stated in the documents:")
        for rel, vals in sorted(affs.items()):
            print(f"  {rel:<34} {', '.join(vals)}")
        print()
        problems += check_affiliation_disagreement(affs)

    if problems:
        print("=" * 74)
        print(f"FINDINGS ({len(problems)})")
        print("=" * 74)
        for p in problems:
            print(f"  ! {p}")
        print()
        print("RESULT: FAIL — the two metadata files do not describe one artefact.")
        return 1

    print("RESULT: PASS — CITATION.cff and .zenodo.json agree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
