#!/usr/bin/env python3
"""R-LAAER CLI — python -m rlaaer <subcommand> <args>"""

import argparse
import json
import os
import sys
from typing import Any

import yaml

from rlaaer.registry import ExperimentRegistry

_REGISTRY: ExperimentRegistry | None = None
_SCHEDULER = None


def _registry() -> ExperimentRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ExperimentRegistry()
    return _REGISTRY


def main():
    parser = argparse.ArgumentParser(
        description="R-LAAER — Research Lab Adversarial Agentic Experiment Runner"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # pipeline subcommands
    pipeline_parser = subparsers.add_parser("pipeline", help="Pipeline operations")
    pipeline_sub = pipeline_parser.add_subparsers(dest="pipeline_command")

    # pipeline new
    new_parser = pipeline_sub.add_parser("new", help="Create new experiment")
    new_parser.add_argument("title", help="Experiment title")
    new_parser.add_argument("--hypothesis", "-H", help="Hypothesis statement (optional)")

    # pipeline submit
    submit_parser = pipeline_sub.add_parser("submit", help="Submit to Council")
    submit_parser.add_argument("id", help="Experiment ID")

    # pipeline execute
    exec_parser = pipeline_sub.add_parser("execute", help="Run experiment")
    exec_parser.add_argument("id", help="Experiment ID")
    exec_parser.add_argument("--dry-run", action="store_true", help="Validate without running")

    # pipeline review
    review_parser = pipeline_sub.add_parser("review", help="Run review")
    review_parser.add_argument("id", help="Experiment ID")

    # pipeline publish
    publish_parser = pipeline_sub.add_parser("publish", help="Publish results")
    publish_parser.add_argument("id", help="Experiment ID")

    # pipeline status
    status_parser = pipeline_sub.add_parser("status", help="Show experiment status")
    status_parser.add_argument("id", nargs="?", help="Experiment ID (optional — show all if omitted)")

    # pipeline queue
    queue_parser = pipeline_sub.add_parser("queue", help="Queue an experiment for execution")
    queue_parser.add_argument("id", help="Experiment ID")
    queue_parser.add_argument("--priority", type=int, default=2, choices=[0, 1, 2, 3],
                              help="0=critical, 1=high, 2=normal, 3=low")
    queue_parser.add_argument("--max-retries", type=int, default=3)
    queue_parser.add_argument("--timeout", type=float, default=60.0, help="Timeout in minutes")

    # pipeline queue-status
    qstatus_parser = pipeline_sub.add_parser("queue-status", help="Show queue status")
    qstatus_parser.add_argument("id", nargs="?", help="Job ID (optional — show all if omitted)")
    qstatus_parser.add_argument("--status", help="Filter by status")

    # pipeline queue-cancel
    qcancel_parser = pipeline_sub.add_parser("queue-cancel", help="Cancel a queued job")
    qcancel_parser.add_argument("id", help="Job ID")

    # pipeline queue-priority
    qprio_parser = pipeline_sub.add_parser("queue-priority", help="Change job priority")
    qprio_parser.add_argument("id", help="Job ID")
    qprio_parser.add_argument("priority", type=int, choices=[0, 1, 2, 3],
                              help="0=critical, 1=high, 2=normal, 3=low")

    # pipeline queue-clear
    pipeline_sub.add_parser("queue-clear", help="Remove completed/failed/cancelled jobs")

    # pipeline queue-drain
    qdrain_parser = pipeline_sub.add_parser("queue-drain", help="Run all queued jobs synchronously")
    qdrain_parser.add_argument("--timeout", type=float, default=300.0, help="Max wait in seconds")

    # pipeline stream (adaptive execution)
    stream_parser = pipeline_sub.add_parser("stream", help="Run experiment with adaptive streaming")
    stream_parser.add_argument("id", help="Experiment ID")
    stream_parser.add_argument("--alpha", type=float, default=0.05, help="Significance threshold")
    stream_parser.add_argument("--min-effect", type=float, default=0.3, help="Minimum effect size")
    stream_parser.add_argument("--min-trials", type=int, default=10, help="Minimum trials before early stop")
    stream_parser.add_argument("--max-trials", type=int, default=10000, help="Maximum trials")
    stream_parser.add_argument("--quiet", action="store_true", help="Suppress live per-trial output")

    # pipeline dashboard
    dash_parser = pipeline_sub.add_parser("dashboard", help="Show accumulated streaming statistics")
    dash_parser.add_argument("id", help="Experiment ID")

    # pipeline graph
    graph_parser = pipeline_sub.add_parser("graph", help="DAG workflow operations")
    graph_sub = graph_parser.add_subparsers(dest="graph_command")

    graph_validate = graph_sub.add_parser("validate", help="Validate a DAG for an experiment")
    graph_validate.add_argument("id", help="Root experiment ID")
    graph_validate.add_argument("--deep", action="store_true", help="Resolve transitive dependencies")

    graph_run = graph_sub.add_parser("run", help="Execute a DAG")
    graph_run.add_argument("id", help="Root experiment ID")
    graph_run.add_argument("--dry-run", action="store_true", help="Validate without executing")
    graph_run.add_argument("--partial", action="store_true", help="Skip unchanged experiments")
    graph_run.add_argument("--workers", type=int, default=2, help="Max parallel workers")

    graph_status = graph_sub.add_parser("status", help="Show DAG execution status")
    graph_status.add_argument("id", help="Root experiment ID")

    graph_render = graph_sub.add_parser("render", help="ASCII visualization of the DAG")
    graph_render.add_argument("id", help="Root experiment ID")
    graph_render.add_argument("--compact", action="store_true", help="Compact one-line-per-node view")

    # pipeline list
    pipeline_sub.add_parser("list", help="List all experiments")

    # pipeline search
    search_parser = pipeline_sub.add_parser("search", help="Search experiments")
    search_parser.add_argument("--pillar", help="Search by pillar tag")
    search_parser.add_argument("--tag", help="Search by tag")
    search_parser.add_argument("--data-source", help="Search by data source")
    search_parser.add_argument("--author", help="Search by author")
    search_parser.add_argument("--status", help="Search by status")
    search_parser.add_argument("--outcome", help="Search by outcome")
    search_parser.add_argument("--hypothesis", help="Search hypothesis text")

    # pipeline history
    history_parser = pipeline_sub.add_parser("history", help="Show lifecycle history")
    history_parser.add_argument("id", help="Experiment ID")

    # pipeline stats
    pipeline_sub.add_parser("stats", help="Registry statistics")

    # validate
    validate_parser = subparsers.add_parser("validate", help="Validate a spec.yaml")
    validate_parser.add_argument("file", help="Path to spec.yaml")

    # agent
    agent_parser = subparsers.add_parser("agent", help="Agent operations")
    agent_sub = agent_parser.add_subparsers(dest="agent_command")
    agent_sub.add_parser("run", help="Run a single agent")
    agent_sub.add_parser("test", help="Test agent")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "validate":
        from rlaaer.validation import validate_file
        errors = validate_file(args.file)
        if errors:
            print(f"VALIDATION FAILED — {len(errors)} error(s):")
            for e in errors:
                print(f"  - {e}")
            sys.exit(1)
        print("VALIDATION PASSED")
        sys.exit(0)

    elif args.command == "pipeline":
        _handle_pipeline(args)

    elif args.command == "agent":
        print(f"Agent command: {args.agent_command} (not yet implemented)")
        sys.exit(0)

    else:
        parser.print_help()
        sys.exit(1)


def _handle_pipeline(args):
    if args.pipeline_command == "new":
        _cmd_new(args)
    elif args.pipeline_command == "list":
        _cmd_list()
    elif args.pipeline_command == "status":
        _cmd_status(args.id)
    elif args.pipeline_command == "search":
        _cmd_search(args)
    elif args.pipeline_command == "history":
        _cmd_history(args.id)
    elif args.pipeline_command == "stats":
        _cmd_stats()
    elif args.pipeline_command == "submit":
        _cmd_submit(args.id)
    elif args.pipeline_command == "execute":
        _cmd_execute(args.id, args.dry_run)
    elif args.pipeline_command == "review":
        _cmd_review(args.id)
    elif args.pipeline_command == "publish":
        _cmd_publish(args.id)
    elif args.pipeline_command == "queue":
        _cmd_queue(args.id, args.priority, args.max_retries, args.timeout)
    elif args.pipeline_command == "queue-status":
        _cmd_queue_status(args.id, args.status)
    elif args.pipeline_command == "queue-cancel":
        _cmd_queue_cancel(args.id)
    elif args.pipeline_command == "queue-priority":
        _cmd_queue_priority(args.id, args.priority)
    elif args.pipeline_command == "queue-clear":
        _cmd_queue_clear()
    elif args.pipeline_command == "queue-drain":
        _cmd_queue_drain(args.timeout)
    elif args.pipeline_command == "stream":
        _cmd_stream(args.id, args.alpha, args.min_effect, args.min_trials, args.max_trials, args.quiet)
    elif args.pipeline_command == "dashboard":
        _cmd_dashboard(args.id)
    elif args.pipeline_command == "graph":
        _cmd_graph(args)
    else:
        print("Unknown pipeline command. Use: new, list, status, search, history, stats, submit, execute, review, publish, queue, queue-status, queue-cancel, queue-priority, queue-clear, queue-drain, stream, dashboard, graph")


def _cmd_new(args):
    from rlaaer.design.designer import Designer
    from rlaaer.config import REPO_ROOT

    designer = Designer()
    next_id = f"{(len(_list_experiments()) + 1):03d}"
    spec = designer._template.copy()
    spec["experiment"]["id"] = next_id
    spec["experiment"]["title"] = args.title
    if args.hypothesis:
        spec["experiment"]["hypothesis"] = args.hypothesis

    output_dir = f"{REPO_ROOT}/experiments/{next_id}_{args.title.replace(' ', '_')}"
    path = designer.write(spec, output_dir)
    _registry().register(spec, path)
    print(f"Created experiment {next_id} at {path}")
    print(f"Status: draft")


def _cmd_list():
    reg = _registry()
    experiments = reg.list_all()
    if not experiments:
        print("No experiments found.")
        return
    print(f"{'ID':<8} {'Title':<40} {'Status':<15} {'Outcome':<12} {'Created':<12}")
    print("-" * 90)
    for e in experiments:
        outcome = e.get("outcome") or ""
        print(f"{e['id']:<8} {e['title'][:40]:<40} {e['status']:<15} {outcome:<12} {(e.get('created') or '')[:10]:<12}")


def _cmd_status(experiment_id=None):
    reg = _registry()
    if experiment_id:
        exp = reg.get(experiment_id)
        if not exp:
            print(f"Experiment {experiment_id} not found")
            return
        print(json.dumps(exp, indent=2, default=str))
    else:
        print(json.dumps(reg.list_all(), indent=2, default=str))


def _cmd_search(args):
    reg = _registry()
    kwargs = {}
    for attr in ("pillar", "tag", "data_source", "author", "status", "outcome", "hypothesis"):
        val = getattr(args, attr.replace("-", "_"), None)
        if val:
            key = attr if attr != "pillar" else "tag"
            kwargs[key] = val
    results = reg.search(**kwargs)
    if not results:
        print("No matches.")
        return
    print(f"{'ID':<8} {'Title':<40} {'Status':<15} {'Outcome':<12}")
    print("-" * 75)
    for e in results:
        outcome = e.get("outcome") or ""
        print(f"{e['id']:<8} {e['title'][:40]:<40} {e['status']:<15} {outcome:<12}")


def _cmd_history(experiment_id):
    reg = _registry()
    events = reg.history(experiment_id)
    if not events:
        print(f"No history for experiment {experiment_id}")
        return
    print(f"Lifecycle history for {experiment_id}:")
    for ev in events:
        print(f"  {ev['timestamp'][:19]}  {ev['from_status']} → {ev['to_status']}")


def _cmd_stats():
    reg = _registry()
    s = reg.stats()
    print(f"Total experiments: {s['total']}")
    print(f"By status: {json.dumps(s['by_status'])}")


def _cmd_submit(experiment_id):
    from rlaaer.design.pre_registration import PreRegistration

    prereg = PreRegistration()
    spec = _load_spec(experiment_id)
    if not spec:
        print(f"Experiment {experiment_id} not found or missing spec.yaml")
        return

    _registry().update_status(experiment_id, "submitted")
    submission = prereg.submit(spec)
    print(f"Submitted experiment {experiment_id} for pre-registration:")
    print(json.dumps(submission, indent=2))


def _cmd_execute(experiment_id, dry_run):
    from rlaaer.execution.runner import Runner

    if not dry_run:
        _registry().update_status(experiment_id, "executing")

    runner = Runner()
    result = runner.run(experiment_id, dry_run=dry_run)

    if not dry_run:
        status = result.get("status", "unknown")
        _registry().update_status(experiment_id, status, detail=result)

    if dry_run:
        print(f"Dry run: {experiment_id} — validation passed")
    else:
        print(f"Execution complete for {experiment_id}:")
        print(f"  Trials: {result.get('trials_completed', 0)}/{result.get('status', 'unknown')}")
        print(f"  Duration: {result.get('duration_seconds', 0):.1f}s")


def _cmd_review(experiment_id):
    from rlaaer.review.council_wrapper import CouncilWrapper
    from rlaaer.review.meta_reviewer import MetaReviewer

    spec = _load_spec(experiment_id)
    if not spec:
        print(f"Experiment {experiment_id} not found")
        return

    council = CouncilWrapper()
    prereg_check = council.check_pre_registration(spec)
    print(f"Pre-registration check: {'PASSED' if prereg_check['passed'] else 'FAILED'}")
    if not prereg_check["passed"]:
        for i in prereg_check["issues"]:
            print(f"  - {i}")

    if not prereg_check["passed"]:
        print("Fix pre-registration issues before submitting for review.")
        return

    review = council.submit_for_review(experiment_id, spec, {})
    meta = MetaReviewer()
    decision = meta.decide(review, spec)

    _registry().update_status(experiment_id, f"review:{decision['decision']}", detail=decision)

    print(f"\nReview results for {experiment_id}:")
    print(f"  Accepts: {review.get('accepts', 0)}/{len(review.get('reviews', {}))}")
    print(f"  Decision: {decision.get('decision')}")
    if decision.get('reason'):
        print(f"  Reason: {decision['reason']}")


def _cmd_publish(experiment_id):
    from rlaaer.publication.manuscript import ManuscriptGenerator
    from rlaaer.publication.latex_renderer import LatexRenderer
    from rlaaer.publication.citation_manager import CitationManager

    spec = _load_spec(experiment_id)
    if not spec:
        print(f"Experiment {experiment_id} not found")
        return

    exp_dir = _find_exp_dir(experiment_id)
    results = {}
    results_path = f"{exp_dir}/results/summary.json"
    try:
        with open(results_path) as f:
            results = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    reviews_dir = os.path.join(exp_dir, "reviews")
    transcripts = {}
    if os.path.isdir(reviews_dir):
        for fname in os.listdir(reviews_dir):
            if fname.endswith(".json"):
                try:
                    with open(os.path.join(reviews_dir, fname)) as f:
                        transcripts[fname.replace(".json", "")] = json.load(f)
                except (json.JSONDecodeError, OSError):
                    pass

    mg = ManuscriptGenerator()
    md = mg.generate(spec, results, {}, {}, transcripts)
    md_path = f"{exp_dir}/manuscript.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Manuscript written to {md_path}")

    pub_fmt = spec.get("publication", {}).get("format", "markdown")
    if pub_fmt in ("latex", "both"):
        lr = LatexRenderer()
        tex_path = f"{exp_dir}/manuscript.tex"
        lr.render_to_file(md, spec, tex_path)
        print(f"LaTeX written to {tex_path}")

    # Record outcome in registry
    analysis = results.get("statistical_analysis", {})
    _registry().update_outcome(
        experiment_id,
        outcome="published",
        significance=analysis.get("p_value"),
        effect_size=analysis.get("effect_size"),
    )
    _registry().update_status(experiment_id, "published")


def _scheduler():
    global _SCHEDULER
    if _SCHEDULER is None:
        from rlaaer.execution.scheduler import Scheduler
        _SCHEDULER = Scheduler()
    return _SCHEDULER


def _cmd_queue(experiment_id, priority, max_retries, timeout):
    from rlaaer.execution.scheduler import Scheduler
    sched = _scheduler()
    try:
        job = sched.enqueue(experiment_id, priority=priority, max_retries=max_retries, timeout_minutes=timeout)
        print(f"Queued experiment {experiment_id} (priority={priority}, retries={max_retries}, timeout={timeout}m)")
        print(f"  Status: {job.status}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def _cmd_queue_status(experiment_id, status_filter):
    sched = _scheduler()
    if experiment_id:
        job = sched.job_status(experiment_id)
        if not job:
            print(f"Job {experiment_id} not found")
            return
        import json
        print(json.dumps({
            "experiment_id": job.experiment_id,
            "status": job.status,
            "priority": job.priority,
            "retry_count": job.retry_count,
            "max_retries": job.max_retries,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "error": job.error,
        }, indent=2, default=str))
    else:
        jobs = sched.list_jobs(status=status_filter)
        if not jobs:
            print("No jobs in queue.")
            return
        print(f"{'ID':<10} {'Status':<12} {'Priority':<10} {'Retries':<8} {'Created':<22}")
        print("-" * 62)
        for j in jobs:
            print(f"{j.experiment_id:<10} {j.status:<12} {j.priority:<10} {j.retry_count}/{j.max_retries:<4} {(j.created_at or '')[:19]:<22}")


def _cmd_queue_cancel(experiment_id):
    sched = _scheduler()
    job = sched.cancel(experiment_id)
    if job:
        print(f"Cancelled job {experiment_id}")
    else:
        print(f"Job {experiment_id} not found or already running")


def _cmd_queue_priority(experiment_id, priority):
    sched = _scheduler()
    try:
        job = sched.set_priority(experiment_id, priority)
        print(f"Updated {experiment_id} priority to {priority}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def _cmd_queue_clear():
    sched = _scheduler()
    sched.clear_completed()
    print("Cleared completed/failed/cancelled jobs")


def _cmd_queue_drain(timeout):
    sched = _scheduler()
    print(f"Draining queue (max {timeout}s)...")
    jobs = sched.run_until_complete(timeout_sec=timeout)
    for j in jobs:
        print(f"  {j.experiment_id}: {j.status}" + (f" — {j.error}" if j.error else ""))


def _cmd_stream(experiment_id, alpha, min_effect, min_trials, max_trials, quiet):
    from rlaaer.execution.streaming import AdaptiveRunner, StreamEvent

    ar = AdaptiveRunner(alpha=alpha, min_effect_size=min_effect,
                        min_trials=min_trials, max_trials=max_trials)

    if not quiet:
        def print_event(e: StreamEvent):
            if e.type == "metric_update":
                print(f"  trial {e.trial:>5} | {e.metric}={e.value:.4f} ({e.detail.get('group', ''):>9})")
            elif e.type == "trial_complete":
                metrics = ", ".join(f"{k}={v:.4f}" for k, v in ar.dashboard.current_metrics.items())
                print(f"  Trial {e.trial:>5} done | {metrics}")
            elif e.type == "status_change":
                print(f"  Status: {e.detail}")
        callback = print_event
    else:
        callback = None

    print(f"Running experiment {experiment_id} with adaptive streaming...")
    result = ar.run_adaptive(experiment_id, event_callback=callback)

    print(f"\n{'='*60}")
    print(f"Experiment {experiment_id} complete")
    print(f"  Trials: {result.get('total_trials', 0)}")
    print(f"  Streaming events: {result.get('streaming_events', 0)}")
    print(f"  Stopped early: {result.get('stopped_early', False)}")
    print(f"\n  Decisions:")
    for d in result.get("decisions", [])[-5:]:  # last 5
        print(f"    {d.get('action')}: {d.get('reason')}")
    print(f"\n  Final statistics:")
    for metric, stats in result.get("final_statistics", {}).items():
        sig = " (significant)" if stats.get("significant") else ""
        print(f"    {metric}: mean={stats.get('mean', 0):.4f}, d={stats.get('cohens_d', 0):.2f}, p={stats.get('p_value', 1):.4f}{sig}")


def _cmd_dashboard(experiment_id):
    from rlaaer.execution.streaming import AdaptiveRunner

    ar = AdaptiveRunner()
    result = ar.run_adaptive(experiment_id, event_callback=None)
    print(f"Dashboard for {experiment_id}:")
    print(result.get("dashboard", "No data"))


def _cmd_graph(args):
    from rlaaer.graph.dag import DepGraph
    from rlaaer.graph.executor import DAGExecutor

    eid = args.id
    spec = _load_spec(eid)
    if not spec:
        print(f"Experiment {eid} not found")
        return

    root_dag = DepGraph().from_spec(spec)

    if args.graph_command == "validate":
        errors = root_dag.validate()
        if errors:
            print(f"DAG validation FAILED for experiment {eid}:")
            for err in errors:
                print(f"  - {err}")
        else:
            print(f"DAG validation PASSED for experiment {eid}")
            order = root_dag.topological_sort()
            print(f"  Execution order: {' → '.join(order)}")
            levels = root_dag.independent_branches()
            for i, level in enumerate(levels):
                print(f"  Level {i}: {', '.join(level)}")

    elif args.graph_command == "run":
        executor = DAGExecutor(max_workers=args.workers)
        print(f"Executing DAG for {eid} (workers={args.workers}, partial={args.partial}, dry={args.dry_run})...")
        try:
            results = executor.execute(root_dag, dry_run=args.dry_run, partial=args.partial)
            for e, r in results.items():
                status = r.get("status", "unknown")
                print(f"  [{e}] {status}" + (f" — {r.get('error', '')}" if r.get('error') else ""))
        except Exception as e:
            print(f"DAG execution failed: {e}")

    elif args.graph_command == "status":
        executor = DAGExecutor()
        statuses = executor.status(root_dag)
        print(f"DAG status for {eid}:")
        for e, s in statuses.items():
            print(f"  [{e}] registry={s['registry_status']}, result={s['result_status']}")

    elif args.graph_command == "render":
        if args.compact:
            print(root_dag.render_compact())
        else:
            print(root_dag.render())


def _list_experiments() -> list[dict]:
    import glob, os
    from rlaaer.config import REPO_ROOT, SPEC_FILENAME

    experiments = []
    for spec_file in glob.glob(f"{REPO_ROOT}/experiments/*/{SPEC_FILENAME}"):
        try:
            with open(spec_file) as f:
                spec = yaml.safe_load(f)
            exp = spec.get("experiment", {})
            experiments.append({
                "id": exp.get("id", "???"),
                "title": exp.get("title", "Untitled"),
                "status": exp.get("status", "unknown"),
                "created": exp.get("created", ""),
                "path": os.path.dirname(spec_file),
            })
        except Exception:
            continue
    return experiments


def _load_spec(experiment_id: str) -> dict | None:
    import glob, os
    from rlaaer.config import REPO_ROOT, SPEC_FILENAME

    for spec_file in glob.glob(f"{REPO_ROOT}/experiments/*/{SPEC_FILENAME}"):
        try:
            with open(spec_file) as f:
                spec = yaml.safe_load(f)
            if spec.get("experiment", {}).get("id") == experiment_id:
                return spec
        except Exception:
            continue
    return None


def _find_exp_dir(experiment_id: str) -> str | None:
    import glob, os
    from rlaaer.config import REPO_ROOT, SPEC_FILENAME

    for spec_file in glob.glob(f"{REPO_ROOT}/experiments/*/{SPEC_FILENAME}"):
        try:
            with open(spec_file) as f:
                spec = yaml.safe_load(f)
            if spec.get("experiment", {}).get("id") == experiment_id:
                return os.path.dirname(spec_file)
        except Exception:
            continue
    return None


if __name__ == "__main__":
    main()
