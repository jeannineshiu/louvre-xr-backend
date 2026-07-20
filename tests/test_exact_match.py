from rag_engine import _exact_match_ids


def test_exhibit_name_matches_verbatim():
    assert _exact_match_ids("Tell me about the Venus de Milo") == ["venus_de_milo"]


def test_artist_shared_by_multiple_exhibits_matches_all_of_them():
    ids = _exact_match_ids("who is Aristide Maillol")
    assert set(ids) == {"air_maillol", "la_nuit_maillol", "hommage_a_cezanne_maillol"}


def test_short_exhibit_name_uses_word_boundaries_not_substring():
    # "Air" must not match inside unrelated words like "fair"/"hair".
    assert _exact_match_ids("what a nice fair, lots of hair around") == []
    assert _exact_match_ids("tell me about Air") == ["air_maillol"]


def test_no_match_for_unrelated_question():
    assert _exact_match_ids("random unrelated question about pizza") == []


def test_unknown_artist_is_not_matchable():
    # "Unknown (...)" artist strings shouldn't turn the word "unknown" into
    # a match trigger.
    assert _exact_match_ids("the artist is unknown") == []


def test_case_insensitive():
    assert _exact_match_ids("VENUS DE MILO") == ["venus_de_milo"]
