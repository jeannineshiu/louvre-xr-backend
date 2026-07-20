from context_router import _decide_mode, route


def test_short_gaze_yields_no_response_regardless_of_crowd():
    mode, _, xr_action = _decide_mode({"gaze_duration": 2.0, "crowd": "crowded"})
    assert mode == "NO_RESPONSE"
    assert xr_action is None


def test_mid_gaze_low_crowd_is_brief_text():
    mode, _, xr_action = _decide_mode({"gaze_duration": 10.0, "crowd": "low"})
    assert mode == "BRIEF_TEXT"
    assert xr_action is None


def test_mid_gaze_crowded_is_glance_card():
    mode, _, xr_action = _decide_mode({"gaze_duration": 10.0, "crowd": "crowded"})
    assert mode == "GLANCE_CARD"
    assert xr_action == "show_card"


def test_long_gaze_low_crowd_is_full_voice():
    mode, _, xr_action = _decide_mode({"gaze_duration": 30.0, "crowd": "low"})
    assert mode == "FULL_VOICE"
    assert xr_action is None


def test_long_gaze_crowded_is_brief_text_prompt():
    mode, _, xr_action = _decide_mode({"gaze_duration": 30.0, "crowd": "crowded"})
    assert mode == "BRIEF_TEXT_PROMPT"
    assert xr_action == "show_quiet_prompt"


def test_unknown_crowd_value_treated_as_low():
    mode, _, _ = _decide_mode({"gaze_duration": 10.0, "crowd": "something_else"})
    assert mode == "BRIEF_TEXT"


def test_boundary_gaze_durations_are_inclusive_on_the_lower_bound():
    # exactly at GAZE_THRESHOLD_INTEREST (5.0) is no longer "< 5s"
    mode, _, _ = _decide_mode({"gaze_duration": 5.0, "crowd": "low"})
    assert mode == "BRIEF_TEXT"
    # exactly at GAZE_THRESHOLD_ENGAGED (15.0) is no longer "< 15s"
    mode, _, _ = _decide_mode({"gaze_duration": 15.0, "crowd": "low"})
    assert mode == "FULL_VOICE"


class _FakeRAG:
    def __init__(self, answer="an answer"):
        self.answer = answer
        self.calls = []

    def query(self, question, mode=None, max_length=None, history=None):
        self.calls.append({"question": question, "mode": mode, "max_length": max_length, "history": history})
        return {"answer": self.answer}


def test_route_returns_no_response_without_querying_rag():
    rag = _FakeRAG()
    decision = route("What is this?", rag, {"gaze_duration": 1.0, "crowd": "low"})
    assert decision.mode == "NO_RESPONSE"
    assert decision.answer == ""
    assert rag.calls == []


def test_route_queries_rag_with_the_decided_mode_and_max_length():
    rag = _FakeRAG(answer="Sophie's answer")
    decision = route("What is this?", rag, {"gaze_duration": 20.0, "crowd": "low"})
    assert decision.mode == "FULL_VOICE"
    assert decision.answer == "Sophie's answer"
    assert rag.calls[0]["mode"] == "FULL_VOICE"
    assert rag.calls[0]["max_length"] == 700
