from unittest.mock import patch

from streamlit.testing.v1 import AppTest


def test_auto_generic_request_stops_before_router_or_provider():
    with patch("src.router.classify_request", side_effect=AssertionError("router must not run")) as classify:
        with patch("src.embeddings.load_model", return_value=object()), patch("src.universe_registry.load_semantic_handle", return_value=object()), patch("src.llm.answer") as answer, patch("anthropic.Anthropic") as anthropic, patch("socket.create_connection", side_effect=AssertionError("network disabled")):
            at = AppTest.from_file("app.py").run(timeout=30)
            at.text_area(key="main_input").input("Tell me about history")
            at.button[0].click().run(timeout=30)

    classify.assert_not_called()
    answer.assert_not_called()
    anthropic.assert_not_called()
    assert any("SELECTION_REQUIRED" in error.value for error in at.error)


def test_explicit_terran_translation_stops_before_provider():
    classify = lambda *_args, **_kwargs: {"route": "translate", "label": "Translation", "method": "rules", "reason": "test"}
    with patch("src.router.classify_request", classify), patch("src.embeddings.load_model", return_value=object()), patch("src.universe_registry.load_semantic_handle", return_value=object()), patch("src.llm.answer") as answer, patch("anthropic.Anthropic") as anthropic, patch("socket.create_connection", side_effect=AssertionError("network disabled")):
        at = AppTest.from_file("app.py").run(timeout=30)
        at.selectbox(key="normal_universe").select("Empire Terran")
        at.text_area(key="main_input").input("Translate: the warrior walks")
        at.button[0].click().run(timeout=30)

    answer.assert_not_called()
    anthropic.assert_not_called()
    assert any("CAPABILITY_UNSUPPORTED" in error.value for error in at.error)


def test_explicit_tolkien_selection_overrides_spock_detection():
    classify = lambda *_args, **_kwargs: {"route": "qa", "label": "Q&A", "method": "rules", "reason": "test"}
    with patch("src.router.classify_request", classify), patch("src.embeddings.load_model", return_value=object()), patch("src.universe_registry.load_semantic_handle", return_value=object()), patch("src.llm.answer") as answer, patch("anthropic.Anthropic") as anthropic, patch("socket.create_connection", side_effect=AssertionError("network disabled")):
        at = AppTest.from_file("app.py").run(timeout=30)
        at.selectbox(key="normal_universe").select("Tolkien / Elfique")
        at.text_area(key="main_input").input("Who is Mirror Spock?")
        at.button[0].click().run(timeout=30)

    answer.assert_not_called()
    anthropic.assert_not_called()
    assert any("Univers : Tolkien's Middle-earth" in caption.value for caption in at.caption)
