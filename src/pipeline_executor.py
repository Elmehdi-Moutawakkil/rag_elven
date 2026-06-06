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
from typing import Any, Optional

from src.layer_registry import LAYER_META, LAYER_RUNNERS, LayerResult


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
    context: dict[str, Any] = {
        "user_input": user_input,
        "outputs": {},
        "resources": resources or {},
    }

    trace = []
    current_output: Any = user_input
    current_type: str = "text"

    for layer_id in layer_sequence:
        if layer_id not in LAYER_RUNNERS:
            return {
                "final_output": None,
                "final_type": "error",
                "trace": trace,
                "outputs": context["outputs"],
                "error": f"Layer inconnue : {layer_id}",
            }

        meta   = LAYER_META[layer_id]
        runner = LAYER_RUNNERS[layer_id]

        t0 = time.perf_counter()
        try:
            result: LayerResult = runner(current_output, context)
        except Exception as exc:
            error_msg = f"{layer_id} ({meta.name}) a échoué : {exc}"
            trace.append({
                "layer_id": layer_id,
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

        context["outputs"][layer_id] = result
        current_output = result.output
        current_type   = result.output_type

        trace.append({
            "layer_id": layer_id,
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
            args = [a.head_lemma for a in output.arguments] if output.arguments else []
            return f"Prédicat : {pred} · Arguments : {', '.join(args)}"
        return str(output)

    if otype == "morph_forms":
        if isinstance(output, list):
            lines = [f"{f.english_lemma} → {f.quenya_form} ({f.case or ''} {f.number or ''})" for f in output[:5]]
            return "\n".join(lines)
        return str(output)

    if otype == "text_constraints":
        return str(output)

    return str(output)
