import os
from unittest.mock import patch
from types import SimpleNamespace

from streamlit.testing.v1 import AppTest
import streamlit as st
from src.retrieval_adapter import RetrievalStatus


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


def test_terran_direct_qa_uses_the_bound_semantic_handle():
    st.cache_resource.clear()
    captured = {}
    model = object()
    handle = object()

    def retrieve(_query, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            status=RetrievalStatus.SUCCESS,
            hits=[],
            degraded=False,
            warnings=[],
            error=None,
        )

    with patch("src.embeddings.load_model", return_value=model), patch(
        "src.universe_registry.load_semantic_handle", return_value=handle
    ), patch("src.retrieval_adapter.retrieve_evidence_result", side_effect=retrieve), patch(
        "src.llm.answer", return_value="answer"
    ), patch("socket.create_connection", side_effect=AssertionError("network disabled")):
        at = AppTest.from_file("app.py").run(timeout=30)
        at.text_area(key="te_input").input("Who is Mirror Spock?")
        at.button(key="te_submit").click().run(timeout=30)

    assert captured["universe_id"] == "terran_empire"
    assert captured["model"] is model
    assert captured["semantic_handle"] is handle


def test_normal_terran_qa_passes_bound_resources_to_pipeline():
    st.cache_resource.clear()
    captured = {}
    model = object()
    handle = object()
    classify = lambda *_args, **_kwargs: {"route": "qa", "label": "Q&A", "method": "rules", "reason": "test"}

    def execute(_layers, _input, resources):
        captured.update(resources)
        return {"error": "test stop", "outputs": {}, "trace": [], "final_output": None}

    with patch("src.router.classify_request", classify), patch(
        "src.embeddings.load_model", return_value=model
    ), patch("src.universe_registry.load_semantic_handle", return_value=handle), patch(
        "src.pipeline_executor.execute_pipeline", side_effect=execute
    ), patch("socket.create_connection", side_effect=AssertionError("network disabled")), patch.dict(
        os.environ, {"GROQ_API_KEY": "test-groq-key"}
    ):
        at = AppTest.from_file("app.py").run(timeout=30)
        at.selectbox(key="normal_universe").select("Empire Terran")
        at.text_area(key="main_input").input("Who is Mirror Spock?")
        at.button[0].click().run(timeout=30)

    assert captured["universe_id"] == "terran_empire"
    assert captured["model"] is model
    assert captured["semantic_handle"] is handle


def test_normal_lore_provider_failure_shows_no_story_or_exception():
    st.cache_resource.clear()
    model = object()
    handle = object()
    classify = lambda *_args, **_kwargs: {"route": "lore", "label": "Lore", "method": "rules", "reason": "test"}

    with patch("src.router.classify_request", classify), patch(
        "src.embeddings.load_model", return_value=model
    ), patch("src.universe_registry.load_semantic_handle", return_value=handle), patch(
        "src.pipeline_executor.execute_pipeline",
        return_value={"error": "Le crédit Anthropic est insuffisant pour générer du lore.", "outputs": {}, "trace": [], "final_output": None},
    ), patch("socket.create_connection", side_effect=AssertionError("network disabled")), patch.dict(
        os.environ, {"ANTHROPIC_API_KEY": "test-anthropic-key"}
    ):
        at = AppTest.from_file("app.py").run(timeout=30)
        at.selectbox(key="normal_universe").select("Tolkien / Elfique")
        at.text_area(key="main_input").input("Invent an elf settlement")
        at.button[0].click().run(timeout=30)

    assert any("crédit Anthropic" in error.value for error in at.error)
    assert not any("Lore généré" in markdown.value for markdown in at.markdown)
    assert not at.exception
