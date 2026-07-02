"""
Splat registry — identifies which exhibit a frontend "Splat" refers to.

The WebXR frontend loads Gaussian-splat captures of sculptures. It sends the
splat's identifier (a filename, URL, slug, or short name) to POST /ask as the
`splat` field, and this module resolves it to a canonical exhibit — so Sophie
answers about the right work without a camera scan.

Resolution is forgiving:
  1. The input is normalised — URL paths and splat extensions (.splat/.ply/.ksplat/.spz)
     are stripped, accents removed, case/punctuation ignored.
  2. Every exhibit id and display name is accepted automatically.
  3. Aliases from splat_mapping.json are applied.
  4. As a fallback, the longest alias/name that appears as a substring wins.

Editing the mapping: add entries to splat_mapping.json — no code change needed.
"""

import json
import re
import unicodedata
from pathlib import Path

from exhibits_data import EXHIBITS

_MAPPING_FILE = Path(__file__).parent / "splat_mapping.json"

# id -> canonical display name, e.g. "hommage_a_cezanne_maillol" -> "L'Hommage à Cézanne"
_ID_TO_NAME: dict[str, str] = {e["id"]: e["name"] for e in EXHIBITS}
_VALID_IDS: set[str] = set(_ID_TO_NAME)


def _normalize(value: str) -> str:
    """Lowercase, drop accents, strip URL path + splat extension, collapse punctuation to spaces."""
    s = value.strip().split("?", 1)[0].split("#", 1)[0]  # drop query/fragment
    s = s.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]          # keep last path segment
    s = re.sub(r"\.(splat|ply|ksplat|spz)$", "", s, flags=re.IGNORECASE)  # drop splat ext
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()  # strip accents
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()             # punctuation/underscores -> space
    return s


def _load_aliases() -> dict[str, str]:
    """Build normalised alias -> exhibit_id map: exhibit ids + names + JSON aliases."""
    alias_to_id: dict[str, str] = {}

    # Every exhibit id and display name resolves to itself
    for exhibit_id, name in _ID_TO_NAME.items():
        alias_to_id[_normalize(exhibit_id)] = exhibit_id
        alias_to_id[_normalize(name)] = exhibit_id

    # Overlay user-defined aliases from the JSON file
    try:
        raw = json.loads(_MAPPING_FILE.read_text(encoding="utf-8"))
        for alias, exhibit_id in raw.get("aliases", {}).items():
            if exhibit_id in _VALID_IDS:
                alias_to_id[_normalize(alias)] = exhibit_id
            # Unknown target ids are ignored silently — a typo in the mapping
            # should not crash the server.
    except (OSError, json.JSONDecodeError):
        pass  # missing/broken mapping file → ids + names still work

    return alias_to_id


# Built once at import. Longest-first ordering is used for substring fallback.
_ALIAS_TO_ID: dict[str, str] = _load_aliases()
_ALIASES_BY_LENGTH: list[str] = sorted(_ALIAS_TO_ID, key=len, reverse=True)


def resolve_splat(value: str | None) -> str | None:
    """
    Resolve a frontend splat identifier to a canonical exhibit display name.

    Returns None if `value` is empty or no exhibit can be identified.

    Examples:
        resolve_splat("hommage_a_cezanne_maillol")               -> "L'Hommage à Cézanne"
        resolve_splat("https://cdn/splats/cezanne_v2.splat")     -> "L'Hommage à Cézanne"
        resolve_splat("Venus de Milo")                           -> "Venus de Milo"
        resolve_splat("random_object")                           -> None
    """
    if not value or not value.strip():
        return None

    norm = _normalize(value)
    if not norm:
        return None

    # 1) Exact normalised match (id, name, or alias)
    exhibit_id = _ALIAS_TO_ID.get(norm)
    if exhibit_id:
        return _ID_TO_NAME[exhibit_id]

    # 2) Substring fallback — longest alias that appears in the identifier wins,
    #    matched on word boundaries so "air" won't match inside "chair".
    for alias in _ALIASES_BY_LENGTH:
        if re.search(rf"\b{re.escape(alias)}\b", norm):
            return _ID_TO_NAME[_ALIAS_TO_ID[alias]]

    return None


def list_mapping() -> dict[str, str]:
    """Return alias -> exhibit display name, for the /splats debug endpoint."""
    return {alias: _ID_TO_NAME[eid] for alias, eid in sorted(_ALIAS_TO_ID.items())}
