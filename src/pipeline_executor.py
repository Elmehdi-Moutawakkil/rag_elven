"""Pipeline Executor — exécute une séquence de layers dans l'ordre.

Usage :
    from src.pipeline_executor import execute_pipeline

    result = execute_pipeline(
        layer_sequence=["L01", "L02", "L03", "L13"],
        user_input="Who are the Noldor?",
        resources={"model": model, "index": index, "meta": metadata},
    )

    result["final_output"]   → sortie de la dernière layer
    result["trace"]          → liste de dicts {layer_id, name, label, output_type, duration_ms}
    result["outputs"]        → dict {layer_id: LayerResult} pour chaque layer exécutée
    result["error"]          → message d'erreur si une layer a planté (None sinon)
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

from src.layer_registry import LAYER_META, MODULE_REGISTRY, LayerResult
from src.universe_registry import get_universe_registry, resolve_universe


def _preflight_error(message: str) -> dict:
    return {"final_output": None, "final_type": "error", "trace": [], "outputs": {}, "error": message}


def _preflight_resources(layer_sequence: list[str], resources: dict[str, Any]) -> str | None:
    """Validate universe capabilities and manifested overrides before runners."""
    active = [layer_id for layer_id in layer_sequence if layer_id in MODULE_REGISTRY and MODULE_REGISTRY[layer_id].available]
    if not active:
        return None
    resolution = resolve_universe(resources.get("universe_id"))
    if not resolution.ok:
        return f"{resolution.status}: {resolution.error}"
    config = get_universe_registry().require(resolution.universe_id or "")
    if any(layer_id in {"L03", "L04", "L05", "L06"} for layer_id in active) and config.universe_id != "tolkien":
        return "CAPABILITY_UNSUPPORTED: Elvish dictionary and translation layers require Tolkien"
    if "L03" in active and (config.dictionary_path is None or not config.dictionary_path.exists()):
        return "INDEX_MISSING: Tolkien dictionary is unavailable"
    if "L09" in active:
        if config.knowledge_graph_path is None or not config.knowledge_graph_path.exists():
            return "INDEX_MISSING: Knowledge graph is unavailable"
        requested = resources.get("kg_db_path")
        if requested is not None and Path(requested).resolve() != config.knowledge_graph_path:
            return "ERROR: Knowledge graph path does not match manifest"
    requested_dictionary = resources.get("dictionary_db_path")
    if requested_dictionary is not None and Path(requested_dictionary).resolve() != config.dictionary_path:
        return "ERROR: Dictionary path does not match manifest"
    return None


def execute_pipeline(
    layer_sequence: list[str],
    user_input: str,
    resources: Optional[dict] = None,
) -> dict:
    """Exécute une séquence ordonnée de layers.

    Args:
        layer_sequence : liste d'IDs de layers, ex: ["L01", "L02", "L13"]
        user_input     : requête brute de l'utilisateur
        resources      : dict avec model, index, meta (optionnel si layers free)

    Returns:
        dict avec :
            final_output  — sortie de la dernière layer (Any)
            final_type    — output_type de la dernière layer (str)
            trace         — liste de dicts décrivant chaque étape
            outputs       — dict {layer_id: LayerResult}
            error         — str si erreur, None sinon
    """
    resource_values = dict(resources or {})
    resolution = resolve_universe(resource_values.get("universe_id"))
    resource_values["allow_dictionary_fallback"] = bool(
        resolution.ok
        and resolution.universe_id == "tolkien"
        and {"L02", "L03", "L13"}.issubset(layer_sequence)
    )
    preflight_error = _preflight_resources(layer_sequence, resource_values)
    if preflight_error:
        return _preflight_error(preflight_error)

    context: dict[str, Any] = {
        "user_input": user_input,
        "outputs": {},
        "resources": resource_values,
    }

    trace = []
    current_output: Any = user_input
    current_type: str = "text"

    for layer_id in layer_sequence:
        if layer_id not in MODULE_REGISTRY:
            return {
                "final_output": None,
                "final_type": "error",
                "trace": trace,
                "outputs": context["outputs"],
                "error": f"Module inconnu : {layer_id}",
            }

        module = MODULE_REGISTRY[layer_id]
        if not module.available:
            return {
                "final_output": None,
                "final_type": "error",
                "trace": trace,
                "outputs": context["outputs"],
                "error": f"Module indisponible : {layer_id} ({module.status})",
            }

        meta   = LAYER_META[layer_id]
        runner = module.run
        if runner is None:
            return {
                "final_output": None,
                "final_type": "error",
                "trace": trace,
                "outputs": context["outputs"],
                "error": f"Module sans runner : {layer_id}",
            }

        t0 = time.perf_counter()
        try:
            result: LayerResult = runner(current_output, context)
        except Exception as exc:
            error_msg = f"{layer_id} ({meta.name}) a échoué : {exc}"
            trace.append({
                "layer_id": layer_id,
                "module_status": module.status,
                "name": meta.name,
                "emoji": meta.emoji,
                "label": f"❌ {exc}",
                "output_type": "error",
                "duration_ms": round((time.perf_counter() - t0) * 1000),
            })
            return {
                "final_output": None,
                "final_type": "error",
                "trace": trace,
                "outputs": context["outputs"],
                "error": error_msg,
            }

        duration_ms = round((time.perf_counter() - t0) * 1000)

        if result.error:
            trace.append({
                "layer_id": layer_id,
                "module_status": module.status,
                "name": meta.name,
                "emoji": meta.emoji,
                "label": f"❌ {result.label}",
                "output_type": result.output_type,
                "duration_ms": duration_ms,
                "retrieval_status": result.metadata.get("retrieval_status"),
            })
            context["outputs"][layer_id] = result
            return {
                "final_output": result.output,
                "final_type": "error",
                "trace": trace,
                "outputs": context["outputs"],
                "error": result.error,
            }

        context["outputs"][layer_id] = result
        current_output = result.output
        current_type   = result.output_type

        trace.append({
            "layer_id": layer_id,
            "module_status": module.status,
            "name": meta.name,
            "emoji": meta.emoji,
            "label": result.label,
            "output_type": result.output_type,
            "duration_ms": duration_ms,
        })

    return {
        "final_output": current_output,
        "final_type":   current_type,
        "trace":        trace,
        "outputs":      context["outputs"],
        "error":        None,
    }


def format_final_output(result: dict) -> str:
    """Convertit le final_output d'un pipeline en texte lisible."""
    output = result["final_output"]
    otype  = result["final_type"]

    if result["error"]:
        return f"Erreur : {result['error']}"

    if otype == "text":
        return str(output)

    if otype == "json_story":
        story = output.get("story", "") if isinstance(output, dict) else str(output)
        warnings = output.get("warnings", []) if isinstance(output, dict) else []
        text = story
        if warnings:
            text += "\n\n⚠️ Avertissements : " + " · ".join(str(w) for w in warnings)
        return text

    if otype == "syntax_result":
        if hasattr(output, "quenya_sentence"):
            return output.quenya_sentence
        return str(output)

    if otype == "json_chunks":
        if not output:
            return "Aucun chunk trouvé."
        lines = [f"[{c.get('score', 0):.3f}] {c.get('text', '')[:200]}" for c in output[:3]]
        return "\n\n".join(lines)

    if otype == "json_dict":
        if not output:
            return "Aucune entrée trouvée."
        lines = [f"**{e.get('word')}** ({e.get('language')}) → {e.get('translation')}" for e in output[:5]]
        return "\n".join(lines)

    if otype == "json_rewrite":
        if isinstance(output, dict):
            return f"keyword: {output.get('keyword')} · type: {output.get('type')}"
        return str(output)

    if otype == "semantic_ir":
        if hasattr(output, "predicate"):
            pred = output.predicate.lemma if output.predicate else "?"
            args = [a.lemma for a in output.arguments] if output.arguments else []
            return f"Prédicat : {pred} · Arguments : {', '.join(args)}"
        return str(output)

    if otype == "morph_forms":
        if isinstance(output, list):
            lines = [f"{f.english_lemma} → {f.quenya_form} ({f.feature})" for f in output[:5]]
            return "\n".join(lines)
        return str(output)

    if otype == "text_constraints":
        return str(output)

    return str(output)
