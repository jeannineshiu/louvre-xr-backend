from navigation_routes import EXHIBIT_NAMES, ROUTES


def test_every_route_key_references_known_exhibit_ids():
    for from_id, to_id in ROUTES:
        assert from_id in EXHIBIT_NAMES, f"unknown from_id: {from_id}"
        assert to_id in EXHIBIT_NAMES, f"unknown to_id: {to_id}"


def test_every_route_has_non_empty_directions():
    for key, directions in ROUTES.items():
        assert isinstance(directions, str)
        assert directions.strip(), f"empty directions for {key}"


def test_routes_contains_no_self_loops():
    for from_id, to_id in ROUTES:
        assert from_id != to_id, f"self-loop route: {from_id}"


def test_known_route_lookup():
    key = ("winged_victory_of_samothrace", "venus_de_milo")
    assert key in ROUTES
    assert "Venus de Milo" in EXHIBIT_NAMES.values()
