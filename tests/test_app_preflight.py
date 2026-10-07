import os
from unittest.mock import patch
from types import SimpleNamespace

from streamlit.testing.v1 import AppTest
import streamlit as st
from src.retrieval_adapter import RetrievalStatus


def test_normal_mode_route_error_is_rendered_before_pipeline():
    st.cache_resource.clear()
    classify = lambda *_args, **_kwargs: {
        "route": None,
        "label": "Routage indisponible",
        "method": "error",
        "reason": "provider unavailable",
        "error": "DeepSeek est temporairement indisponible.",
    }
    with patch("src.router.classify_request", classify), patch(
        "src.embeddings.load_model", return_value=object()
    ), patch("src.universe_registry.load_semantic_handle", return_value=object()), patch(
        "src.pipeline_executor.execute_pipeline"
    ) as execute, patch("socket.create_connection", side_effect=AssertionError("network disabled")):
        at = AppTest.from_file("app.py").run(timeout=30)
        at.selectbox(key="normal_universe").select("Tolkien / Elfique")
        at.text_area(key="main_input").input("A curious request")
        at.button[0].click().run(timeout=30)

    execute.assert_not_called()
    assert any("DeepSeek est temporairement indisponible" in error.value for error in at.error)
    assert not at.exception


def test_normal_french_lexical_translation_renders_dictionary_entries_without_sentence_pipeline():
    st.cache_resource.clear()
    classify = lambda *_args, **_kwargs: {
        "route": "translate",
        "label": "Traduction",
        "method": "rules",
        "reason": "test",
    }
    lexical_result = {
        "status": "SUCCESS",
        "kind": "lexical",
        "normalized_gloss": "walk",
        "error": None,
        "entries": [
            {"word": "vanta -", "language": "Quenya", "translation": "to walk", "source": "quenya.pdf", "page": 12},
            {"word": "pada", "language": "Sindarin", "translation": "walk", "source": "sindarin.pdf", "page": 8},
        ],
    }
    with patch("src.router.classify_request", classify), patch(
        "src.embeddings.load_model", return_value=object()
    ), patch("src.universe_registry.load_semantic_handle", return_value=object()), patch(
        "src.normal_mode.run_normal_translation", return_value=lexical_result
    ) as translate, patch("src.pipeline_executor.execute_pipeline") as execute, patch(
        "socket.create_connection", side_effect=AssertionError("network disabled")
    ), patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-deepseek-key"}):
        at = AppTest.from_file("app.py").run(timeout=30)
        at.selectbox(key="normal_universe").select("Tolkien / Elfique")
        at.text_area(key="main_input").input('Comment se dit "marcher" en elfique ?')
        at.button[0].click().run(timeout=30)

    translate.assert_called_once()
    assert translate.call_args.args == ('Comment se dit "marcher" en elfique ?',)
    assert translate.call_args.kwargs["provider_name"] == "deepseek"
    assert translate.call_args.kwargs["api_key"] == "test-deepseek-key"
    assert translate.call_args.kwargs["resources"]["universe_id"] == "tolkien"
    execute.assert_not_called()
    rendered = "\n".join(item.value for item in at.markdown)
    captions = "\n".join(item.value for item in at.caption)
    normal_plans = [item.value for item in at.caption if item.value.startswith("Pipeline :")]
    assert normal_plans == ["Pipeline : Normalisation fournisseur → Dictionnaire SQLite"]
    assert "L04" not in normal_plans[0]
    assert "L05" not in normal_plans[0]
    assert "L06" not in normal_plans[0]
    assert "Quenya" in rendered and "vanta -" in rendered
    assert "Sindarin" in rendered and "pada" in rendered
    assert "quenya.pdf · page 12" in captions
    assert "sindarin.pdf · page 8" in captions
    assert not at.exception


def test_normal_qa_sources_render_integer_relevance_and_episode_refs():
    st.cache_resource.clear()
    classify = lambda *_args, **_kwargs: {"route": "qa", "label": "Q&A", "method": "rules", "reason": "test"}
    hit = {
        "source_path": "data/key_figures.txt",
        "text": "The Intendant is mirror Kira.",
        "relevance_score": 0.734,
        "score": 0.734,
        "episode_refs": [{"series": "Star Trek: Deep Space Nine", "title": "Crossover", "season": 2, "episode": 23}],
    }
    retrieval_layer = SimpleNamespace(output=[hit], metadata={"retrieval_result": {}})
    result = {
        "error": None,
        "outputs": {"L02": retrieval_layer},
        "trace": [],
        "final_output": "Kira [1]",
        "final_type": "text",
    }
    with patch("src.router.classify_request", classify), patch(
        "src.embeddings.load_model", return_value=object()
    ), patch("src.universe_registry.load_semantic_handle", return_value=object()), patch(
        "src.pipeline_executor.execute_pipeline", return_value=result
    ), patch("socket.create_connection", side_effect=AssertionError("network disabled")), patch.dict(
        os.environ, {"DEEPSEEK_API_KEY": "test-deepseek-key"}
    ):
        at = AppTest.from_file("app.py").run(timeout=30)
        at.selectbox(key="normal_universe").select("Tolkien / Elfique")
        at.text_area(key="main_input").input("Who is the Intendant?")
        at.button[0].click().run(timeout=30)

    rendered = "\n".join(item.value for item in at.markdown)
    captions = "\n".join(item.value for item in at.caption)
    assert "Pertinence de recherche : 73/100" in rendered
    assert "Star Trek: Deep Space Nine — Crossover — S02E23" in captions
    assert "pertinence relative" in captions.lower()
    assert "score 0.734" not in rendered


def test_direct_terran_sources_render_integer_relevance_and_episode_refs():
    st.cache_resource.clear()
    hit = {
        "source_path": "data/key_figures.txt",
        "text": "The Intendant is mirror Kira.",
        "relevance_score": 0.81,
        "score": 0.81,
        "episode_refs": [{"series": "Star Trek: Deep Space Nine", "title": "Crossover"}],
    }
    retrieval = SimpleNamespace(
        status=RetrievalStatus.SUCCESS,
        hits=[hit],
        degraded=False,
        warnings=[],
        error=None,
    )
    with patch("src.embeddings.load_model", return_value=object()), patch(
        "src.universe_registry.load_semantic_handle", return_value=object()
    ), patch("src.retrieval_adapter.retrieve_evidence_result", return_value=retrieval), patch(
        "src.llm.answer", return_value="Kira [1]"
    ), patch("socket.create_connection", side_effect=AssertionError("network disabled")), patch.dict(
        os.environ, {"DEEPSEEK_API_KEY": "test-deepseek-key"}
    ):
        at = AppTest.from_file("app.py").run(timeout=30)
        at.text_area(key="te_input").input("Who is the Intendant?")
        at.button(key="te_submit").click().run(timeout=30)

    rendered = "\n".join(item.value for item in at.markdown)
    captions = "\n".join(item.value for item in at.caption)
    assert "Pertinence de recherche : 81/100" in rendered
    assert "Star Trek: Deep Space Nine — Crossover" in captions
    assert "pertinence relative" in captions.lower()


def test_deepseek_is_the_default_lore_provider():
    with patch("src.embeddings.load_model", return_value=object()), patch(
        "src.universe_registry.load_semantic_handle", return_value=object()
    ), patch("socket.create_connection", side_effect=AssertionError("network disabled")):
        at = AppTest.from_file("app.py").run(timeout=30)

    selector = at.selectbox(key="lore_provider")
    assert "DeepSeek" in selector.options
    assert selector.value == "DeepSeek"


def test_normal_qa_missing_key_names_deepseek_key():
    st.cache_resource.clear()
    classify = lambda *_args, **_kwargs: {
        "route": "qa",
        "label": "Q&A",
        "method": "rules",
        "reason": "test",
    }
    with patch("src.router.classify_request", classify), patch(
        "src.embeddings.load_model", return_value=object()
    ), patch("src.universe_registry.load_semantic_handle", return_value=object()), patch(
        "socket.create_connection", side_effect=AssertionError("network disabled")
    ), patch.dict(
        os.environ,
        {
            "DEEPSEEK_API_KEY": "",
            "GROQ_API_KEY": "",
            "ANTHROPIC_API_KEY": "",
            "OPENAI_API_KEY": "",
        },
    ):
        at = AppTest.from_file("app.py").run(timeout=30)
        at.selectbox(key="normal_universe").select("Tolkien / Elfique")
        at.text_area(key="main_input").input("Who are the Noldor?")
        at.button[0].click().run(timeout=30)

    assert any("DEEPSEEK_API_KEY manquante" in error.value for error in at.error)
    assert not at.exception


def test_normal_lore_passes_deepseek_provider_explicitly():
    st.cache_resource.clear()
    captured = {}
    classify = lambda *_args, **_kwargs: {
        "route": "lore",
        "label": "Lore",
        "method": "rules",
        "reason": "test",
    }

    def execute(_layers, _input, resources):
        captured.update(resources)
        return {"error": "test stop", "outputs": {}, "trace": [], "final_output": None}

    with patch("src.router.classify_request", classify), patch(
        "src.embeddings.load_model", return_value=object()
    ), patch("src.universe_registry.load_semantic_handle", return_value=object()), patch(
        "src.pipeline_executor.execute_pipeline", side_effect=execute
    ), patch("socket.create_connection", side_effect=AssertionError("network disabled")), patch.dict(
        os.environ, {"DEEPSEEK_API_KEY": "test-deepseek-key"}
    ):
        at = AppTest.from_file("app.py").run(timeout=30)
        at.selectbox(key="normal_universe").select("Tolkien / Elfique")
        at.text_area(key="main_input").input("Invent an elf settlement")
        at.button[0].click().run(timeout=30)

    assert captured["lore_provider"] == "deepseek"
    assert not at.exception


def test_terran_lore_passes_deepseek_provider_explicitly():
    st.cache_resource.clear()
    captured = {}

    def generate(**kwargs):
        captured.update(kwargs)
        return {"success": False, "error": "test stop", "story": None, "chunks_used": 0}

    with patch("src.embeddings.load_model", return_value=object()), patch(
        "src.universe_registry.load_semantic_handle", return_value=object()
    ), patch("src.lore_generator_generic.generate_lore_for_universe", side_effect=generate), patch(
        "socket.create_connection", side_effect=AssertionError("network disabled")
    ), patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-deepseek-key"}):
        at = AppTest.from_file("app.py").run(timeout=30)
        at.text_area(key="te_lore_input").input("Invent a Terran officer")
        at.button(key="te_lore_submit").click().run(timeout=30)

    assert captured["provider"] == "deepseek"
    assert captured["api_key"] == "test-deepseek-key"
    assert not at.exception


def test_manual_lore_passes_deepseek_provider_explicitly():
    st.cache_resource.clear()
    captured = {}

    def generate(**kwargs):
        captured.update(kwargs)
        return {"success": False, "error": "test stop", "story": None, "chunks_used": 0}

    with patch("src.embeddings.load_model", return_value=object()), patch(
        "src.universe_registry.load_semantic_handle", return_value=object()
    ), patch("src.lore_generator_generic.generate_lore_for_universe", side_effect=generate), patch(
        "socket.create_connection", side_effect=AssertionError("network disabled")
    ), patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-deepseek-key"}):
        at = AppTest.from_file("app.py").run(timeout=30)
        at.text_area(key="manual_lore").input("Invent a hidden city")
        at.button(key="manual_lore_btn").click().run(timeout=30)

    assert captured["provider"] == "deepseek"
    assert captured["api_key"] == "test-deepseek-key"
    assert not at.exception


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
    ) as answer, patch("socket.create_connection", side_effect=AssertionError("network disabled")), patch.dict(
        os.environ, {"DEEPSEEK_API_KEY": "test-deepseek-key"}
    ):
        at = AppTest.from_file("app.py").run(timeout=30)
        at.text_area(key="te_input").input("Who is Mirror Spock?")
        at.button(key="te_submit").click().run(timeout=30)

    assert captured["universe_id"] == "terran_empire"
    assert captured["model"] is model
    assert captured["semantic_handle"] is handle
    answer.assert_called_once()


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
        os.environ, {"DEEPSEEK_API_KEY": "test-deepseek-key"}
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
        at.selectbox(key="lore_provider").select("Anthropic")
        at.selectbox(key="normal_universe").select("Tolkien / Elfique")
        at.text_area(key="main_input").input("Invent an elf settlement")
        at.button[0].click().run(timeout=30)

    assert any("crédit Anthropic" in error.value for error in at.error)
    assert not any("Lore généré" in markdown.value for markdown in at.markdown)
    assert not at.exception
