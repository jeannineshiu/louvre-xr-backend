from splat_registry import resolve_splat


def test_resolve_by_exhibit_id():
    assert resolve_splat("hommage_a_cezanne_maillol") == "L'Hommage à Cézanne"


def test_resolve_by_url_strips_path_and_extension():
    assert resolve_splat("https://cdn/splats/cezanne_v2.splat") == "L'Hommage à Cézanne"


def test_resolve_by_display_name_is_passthrough():
    assert resolve_splat("Venus de Milo") == "Venus de Milo"


def test_resolve_is_case_and_accent_insensitive():
    assert resolve_splat("VENUS DE MILO") == "Venus de Milo"
    assert resolve_splat("hommage a cezanne") == "L'Hommage à Cézanne"


def test_unknown_identifier_returns_none():
    assert resolve_splat("random_object") is None


def test_empty_or_none_returns_none():
    assert resolve_splat(None) is None
    assert resolve_splat("") is None
    assert resolve_splat("   ") is None


def test_substring_fallback_matches_on_word_boundary_only():
    # "air" is a real exhibit id/name; must not match inside an unrelated word like "chair"
    assert resolve_splat("my_chair_prop") is None
    assert resolve_splat("gallery_air_v3.ply") == "Air"
