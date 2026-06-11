"""
Inspector test runner.

Usage:
  python -m inspector.run_tests                     # run TESTS_PER_FEATURE per enabled feature
  python -m inspector.run_tests --n 24              # run exactly 24 tests total (spread across features)
  python -m inspector.run_tests --feature qa_elvish # run only one feature
  python -m inspector.run_tests --report            # generate daily report from existing data
  python -m inspector.run_tests --weekly            # generate weekly trend report
"""

import argparse
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.chdir(PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from inspector.config   import FEATURES, TESTS_PER_FEATURE
from inspector.db       import init_db, get_recent_questions, save_run
from inspector.question_bank import get_questions
from inspector.app_bridge    import call_feature
from inspector.evaluator     import evaluate_response
from inspector.reporter      import generate_and_save_daily_report, generate_and_save_weekly_report


def run_tests(n_total: int | None = None, feature_filter: str | None = None) -> str:
    init_db()
    run_id = str(uuid.uuid4())[:8]

    enabled_features = [f for f in FEATURES if f["enabled"]]
    if feature_filter:
        enabled_features = [f for f in enabled_features if f["id"] == feature_filter]
        if not enabled_features:
            print(f"[runner] Unknown feature_id: {feature_filter}")
            sys.exit(1)

    # Distribute n_total across features
    if n_total is not None:
        per_feature = max(1, n_total // len(enabled_features))
    else:
        per_feature = TESTS_PER_FEATURE

    total_run = 0
    total_correct = 0
    total_halluc  = 0

    for feat in enabled_features:
        fid      = feat["id"]
        universe = feat["universe"]
        feature  = feat["feature"]

        recent   = get_recent_questions(fid, days=30)
        questions = get_questions(fid, per_feature, exclude_questions=recent)

        print(f"\n{'='*60}")
        print(f"[{fid}] {universe} — {feature} ({len(questions)} tests)")
        print(f"{'='*60}")

        for qi, q_entry in enumerate(questions, 1):
            question = q_entry["q"]
            facts    = q_entry["facts"]
            anti     = q_entry["anti"]

            print(f"\n  [{qi}/{len(questions)}] {question[:80]}")

            # Call the app
            result = call_feature(fid, question)

            if not result["success"]:
                print(f"  💥 App error: {result['error']}")
                save_run(
                    run_id=run_id, feature_id=fid, universe=universe, feature=feature,
                    question=question, app_response=None,
                    verdict="ERROR", score=0.0,
                    judge_notes=result["error"] or "App error",
                    duration_ms=result["duration_ms"],
                    error=result["error"],
                )
                total_run += 1
                continue

            app_response = result["response"]
            print(f"  → Response ({len(app_response)} chars): {app_response[:120]}…")

            # Evaluate
            eval_result = evaluate_response(fid, question, app_response, facts, anti)
            verdict     = eval_result["verdict"]
            score       = eval_result["score"]
            notes       = eval_result["judge_notes"]

            emoji_map = {"CORRECT": "✅", "PARTIAL": "🟡", "HALLUCINATION": "🚨", "IRRELEVANT": "❓", "ERROR": "💥"}
            print(f"  {emoji_map.get(verdict, '?')} {verdict} (score: {score:.2f}) — {notes}")

            save_run(
                run_id=run_id, feature_id=fid, universe=universe, feature=feature,
                question=question, app_response=app_response,
                verdict=verdict, score=score, judge_notes=notes,
                duration_ms=result["duration_ms"],
            )

            total_run += 1
            if verdict == "CORRECT":
                total_correct += 1
            if verdict == "HALLUCINATION":
                total_halluc += 1

    print(f"\n{'='*60}")
    print(f"[runner] Run {run_id} complete — {total_run} tests")
    print(f"  ✅ Correct:       {total_correct}/{total_run} ({total_correct/total_run*100:.0f}%)")
    print(f"  🚨 Hallucination: {total_halluc}/{total_run} ({total_halluc/total_run*100:.0f}%)")
    print(f"{'='*60}")

    return run_id


def main():
    parser = argparse.ArgumentParser(description="Elmehdi Fiction Inspector")
    parser.add_argument("--n",       type=int,  default=None, help="Total number of tests to run (spread across features)")
    parser.add_argument("--feature", type=str,  default=None, help="Run only this feature_id")
    parser.add_argument("--report",  action="store_true",     help="Generate daily report from existing data (no new tests)")
    parser.add_argument("--weekly",  action="store_true",     help="Generate weekly trend report")
    args = parser.parse_args()

    init_db()

    if args.report:
        print("[inspector] Generating daily report...")
        content = generate_and_save_daily_report()
        print("\n" + content)
        return

    if args.weekly:
        print("[inspector] Generating weekly trend report...")
        content = generate_and_save_weekly_report()
        print("\n" + content)
        return

    # Run tests
    run_id = run_tests(n_total=args.n, feature_filter=args.feature)

    # Always generate daily report after a run
    print("\n[inspector] Generating daily report...")
    content = generate_and_save_daily_report(run_id)
    print("\n" + content)


if __name__ == "__main__":
    main()
