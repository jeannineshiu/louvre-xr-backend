from qa_pipeline import _chitchat_reply


def test_bare_greeting_gets_greeting_reply():
    assert _chitchat_reply("hi") == _chitchat_reply("Hello!")
    assert "Sophie" in _chitchat_reply("hey")


def test_thanks_gets_thanks_reply_not_greeting_reply():
    reply = _chitchat_reply("thanks")
    assert reply == _chitchat_reply("Thank you so much!")
    assert reply != _chitchat_reply("hi")


def test_bye_gets_bye_reply():
    assert "visit" in _chitchat_reply("bye").lower() or "revoir" in _chitchat_reply("bye").lower()


def test_real_question_starting_with_greeting_word_is_not_chitchat():
    assert _chitchat_reply("hi, what is this statue made of?") is None


def test_real_question_is_not_chitchat():
    assert _chitchat_reply("Tell me about the Venus de Milo") is None


def test_empty_or_whitespace_is_not_chitchat():
    assert _chitchat_reply("") is None
    assert _chitchat_reply("   ") is None


def test_chinese_greeting_gets_chinese_reply():
    reply = _chitchat_reply("你好")
    assert reply is not None
    assert "你" in reply


def test_french_thanks_gets_french_reply():
    reply = _chitchat_reply("merci beaucoup")
    assert reply is not None
    assert "plaisir" in reply.lower()


def test_case_insensitive_and_trailing_punctuation():
    assert _chitchat_reply("OK!") is not None
    assert _chitchat_reply("Cool.") is not None
