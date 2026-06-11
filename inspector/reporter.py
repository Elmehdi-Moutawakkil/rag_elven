"""
Report generator — daily and weekly reports from inspector run history.

Daily report  : stats for the last 24h (or since last report)
Weekly report : trend analysis over the last 7 days
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from inspector.config import CORRECTNESS_THRESHOLD, HALLUCINATION_THRESHOLD
from inspector.db import get_runs_since, get_runs_since_days, save_report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pct(n: int, total: int) -> str:
    if total == 0:
        return "N/A"
    return f"{n / total * 100:.1f}%"


def _verdict_emoji(verdict: str) -> str:
    return {
        "CORRECT":       "✅",
        "PARTIAL":       "🟡",
        "HALLUCINATION": "🚨",
        "IRRELEVANT":    "❓",
        "ERROR":         "💥",
    }.get(verdict, "❓")


def _health_badge(correct_rate: float, hallucination_rate: float) -> str:
    if hallucination_rate > HALLUCINATION_THRESHOLD:
        return "🔴 DÉGRADÉ"
    if correct_rate < CORRECTNESS_THRESHOLD:
        return "🟠 ATTENTION"
    return "🟢 OK"


# ---------------------------------------------------------------------------
# Daily report
# ---------------------------------------------------------------------------

def build_daily_report(run_id: str | None = None) -> str:
    rows = get_runs_since(hours=24)
    now  = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if not rows:
        return f"# Rapport Journalier — {now}\n\nAucun test exécuté dans les dernières 24h.\n"

    total       = len(rows)
    by_feature: dict[str, list] = defaultdict(list)
    for r in rows:
        by_feature[r["feature_id"]].append(r)

    verdicts = defaultdict(int)
    for r in rows:
        verdicts[r["verdict"]] += 1

    correct_total      = verdicts["CORRECT"]
    hallucination_total = verdicts["HALLUCINATION"]
    correct_rate       = correct_total / total
    hallucination_rate = hallucination_total / total
    avg_score          = sum(r["score"] for r in rows if r["score"] is not None) / total

    badge = _health_badge(correct_rate, hallucination_rate)

    lines = [
        f"# 📊 Rapport Journalier — Elmehdi Fiction Inspector",
        f"**Date :** {now}",
        f"**Statut global :** {badge}",
        "",
        "---",
        "",
        "## Résumé global",
        "",
        f"| Métrique | Valeur |",
        f"|----------|--------|",
        f"| Tests exécutés | {total} |",
        f"| ✅ Corrects | {correct_total} ({_pct(correct_total, total)}) |",
        f"| 🟡 Partiels | {verdicts['PARTIAL']} ({_pct(verdicts['PARTIAL'], total)}) |",
        f"| 🚨 Hallucinations | {hallucination_total} ({_pct(hallucination_total, total)}) |",
        f"| ❓ Hors-sujet | {verdicts['IRRELEVANT']} ({_pct(verdicts['IRRELEVANT'], total)}) |",
        f"| 💥 Erreurs | {verdicts['ERROR']} ({_pct(verdicts['ERROR'], total)}) |",
        f"| Score moyen | {avg_score:.2f} / 1.0 |",
        "",
        "---",
        "",
        "## Résultats par fonctionnalité",
        "",
    ]

    issues: list[str] = []

    for fid, runs in sorted(by_feature.items()):
        n = len(runs)
        fverdicts = defaultdict(int)
        for r in runs:
            fverdicts[r["verdict"]] += 1

        f_correct  = fverdicts["CORRECT"]
        f_halluc   = fverdicts["HALLUCINATION"]
        f_rate     = f_correct / n
        f_hallrate = f_halluc / n
        f_score    = sum(r["score"] for r in runs if r["score"] is not None) / n
        f_badge    = _health_badge(f_rate, f_hallrate)

        universe = runs[0]["universe"]
        feature  = runs[0]["feature"]

        lines += [
            f"### {f_badge} {universe} — {feature}",
            "",
            f"| | |",
            f"|---|---|",
            f"| Tests | {n} |",
            f"| ✅ Corrects | {f_correct} ({_pct(f_correct, n)}) |",
            f"| 🚨 Hallucinations | {f_halluc} ({_pct(f_halluc, n)}) |",
            f"| Score moyen | {f_score:.2f} |",
            "",
            "**Détail des tests :**",
            "",
        ]

        for r in runs:
            emoji = _verdict_emoji(r["verdict"])
            q_short = r["question"][:80] + ("…" if len(r["question"]) > 80 else "")
            lines.append(f"- {emoji} `{r['verdict']}` (score: {r['score']:.2f}) — *{q_short}*")
            if r["judge_notes"]:
                lines.append(f"  > {r['judge_notes']}")
        lines.append("")

        if f_hallrate > HALLUCINATION_THRESHOLD:
            issues.append(f"🚨 **{universe} / {feature}** : taux d'hallucination élevé ({_pct(f_halluc, n)})")
        if f_rate < CORRECTNESS_THRESHOLD:
            issues.append(f"⚠️ **{universe} / {feature}** : taux de correction faible ({_pct(f_correct, n)})")
        errors = [r for r in runs if r["verdict"] == "ERROR"]
        if errors:
            issues.append(f"💥 **{universe} / {feature}** : {len(errors)} erreur(s) technique(s)")

    lines += ["---", "", "## Points à régler"]
    if issues:
        lines += [""] + [f"- {i}" for i in issues]
    else:
        lines += ["", "✅ Aucun problème détecté — tous les seuils sont respectés."]

    lines += [
        "",
        "---",
        "",
        f"*Généré par Elmehdi Fiction Inspector — {now}*",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Weekly trend report
# ---------------------------------------------------------------------------

def build_weekly_report() -> str:
    rows = get_runs_since_days(days=7)
    now  = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if not rows:
        return f"# Rapport Hebdomadaire — {now}\n\nPas assez de données pour une analyse de tendance.\n"

    # Group by day × feature
    from collections import OrderedDict
    daily: dict[str, dict[str, list]] = OrderedDict()
    for r in rows:
        day = r["ts"][:10]
        if day not in daily:
            daily[day] = defaultdict(list)
        daily[day][r["feature_id"]].append(r)

    # Compute per-day global stats
    day_stats = []
    for day, features in sorted(daily.items()):
        all_runs = [r for runs in features.values() for r in runs]
        n = len(all_runs)
        correct = sum(1 for r in all_runs if r["verdict"] == "CORRECT")
        halluc  = sum(1 for r in all_runs if r["verdict"] == "HALLUCINATION")
        score   = sum(r["score"] for r in all_runs if r["score"] is not None) / n
        day_stats.append({
            "day": day, "n": n,
            "correct_rate": correct / n,
            "hallucination_rate": halluc / n,
            "avg_score": score,
        })

    lines = [
        "# 📈 Rapport Hebdomadaire — Elmehdi Fiction Inspector",
        f"**Période :** 7 derniers jours",
        f"**Date :** {now}",
        "",
        "---",
        "",
        "## Tendance journalière",
        "",
        "| Date | Tests | ✅ Corrects | 🚨 Hallucinations | Score moyen |",
        "|------|-------|------------|-------------------|-------------|",
    ]

    for d in day_stats:
        badge = _health_badge(d["correct_rate"], d["hallucination_rate"])
        lines.append(
            f"| {d['day']} {badge} | {d['n']} "
            f"| {_pct(int(d['correct_rate'] * d['n']), d['n'])} "
            f"| {_pct(int(d['hallucination_rate'] * d['n']), d['n'])} "
            f"| {d['avg_score']:.2f} |"
        )

    # Trend analysis
    if len(day_stats) >= 3:
        first_half  = day_stats[: len(day_stats) // 2]
        second_half = day_stats[len(day_stats) // 2 :]
        avg_first   = sum(d["avg_score"] for d in first_half)  / len(first_half)
        avg_second  = sum(d["avg_score"] for d in second_half) / len(second_half)
        delta       = avg_second - avg_first

        if delta > 0.05:
            trend = "📈 **Amélioration** détectée sur la semaine."
        elif delta < -0.05:
            trend = "📉 **Dégradation** détectée — vérifier les modèles et les index."
        else:
            trend = "➡️ **Stable** — pas de dérive significative détectée."
    else:
        trend = "📊 Pas encore assez de données pour une tendance fiable (min 3 jours)."

    lines += [
        "",
        "---",
        "",
        "## Analyse de tendance",
        "",
        trend,
        "",
        "---",
        "",
        "## Fonctionnalités les plus instables cette semaine",
        "",
    ]

    # Per-feature weekly stats
    feature_stats: dict[str, dict] = defaultdict(lambda: {"n": 0, "correct": 0, "halluc": 0, "score_sum": 0.0})
    for r in rows:
        fs = feature_stats[r["feature_id"]]
        fs["n"] += 1
        fs["universe"] = r["universe"]
        fs["feature"]  = r["feature"]
        if r["verdict"] == "CORRECT":
            fs["correct"] += 1
        if r["verdict"] == "HALLUCINATION":
            fs["halluc"] += 1
        if r["score"] is not None:
            fs["score_sum"] += r["score"]

    ranked = sorted(feature_stats.items(), key=lambda x: x[1]["correct"] / x[1]["n"])
    for fid, fs in ranked:
        n  = fs["n"]
        cr = fs["correct"] / n
        hr = fs["halluc"]  / n
        sc = fs["score_sum"] / n
        badge = _health_badge(cr, hr)
        lines.append(f"- {badge} **{fs['universe']} / {fs['feature']}** — {_pct(fs['correct'], n)} corrects, {_pct(fs['halluc'], n)} hallucinations, score {sc:.2f}")

    lines += [
        "",
        "---",
        "",
        f"*Généré par Elmehdi Fiction Inspector — {now}*",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def generate_and_save_daily_report(run_id: str | None = None) -> str:
    content = build_daily_report(run_id)
    save_report("daily", content)

    report_path = PROJECT_ROOT / "inspector" / "reports" / f"daily_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.md"
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(content, encoding="utf-8")
    print(f"[reporter] Daily report saved → {report_path}")
    return content


def generate_and_save_weekly_report() -> str:
    content = build_weekly_report()
    save_report("weekly", content)

    report_path = PROJECT_ROOT / "inspector" / "reports" / f"weekly_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.md"
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(content, encoding="utf-8")
    print(f"[reporter] Weekly report saved → {report_path}")
    return content
