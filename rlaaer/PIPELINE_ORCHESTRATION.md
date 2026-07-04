# Pipeline Orchestration

## How spec.yaml flows through the system

```
                  ┌──────────────────────────────────────────────────┐
                  │                 rlaaer pipeline                  │
                  │                                                  │
  ┌───────────┐   │   ┌──────────┐    ┌──────────────┐              │
  │  Agent    │───┼──▶│ design/  │───▶│ pre-register │              │
  │ Profiles  │   │   │          │    │ (Council)    │              │
  └───────────┘   │   └──────────┘    └──────┬───────┘              │
                  │                          │ locked spec.yaml     │
                  │                          ▼                      │
                  │                      ┌──────────┐              │
                  │                      │  data/   │              │
                  │                      │ scrape + │              │
                  │                      │ transform│              │
                  │                      └────┬─────┘              │
                  │                           │ cached datasets    │
                  │                           ▼                    │
                  │                      ┌──────────┐              │
                  │                      │execution/│              │
                  │                      │  runner  │──────────┐   │
                  │                      └────┬─────┘          │   │
                  │                           │ CSV metrics    │   │
                  │                           ▼                │   │
                  │                      ┌──────────┐          │   │
                  │                      │ review/  │◀─────────┘   │
                  │                      │ council  │              │
                  │                      │ + stat   │              │
                  │                      └────┬─────┘              │
                  │                           │ verdict            │
                  │                           ▼                    │
                  │                      ┌──────────┐              │
                  │                      │publication│             │
                  │                      │ .md + .tex│             │
                  │                      └──────────┘              │
                  └──────────────────────────────────────────────────┘
```

## Lifecycle State Machine

```
              ┌──────────┐
              │  draft   │  spec.yaml created by Designer agents
              └────┬─────┘
                   │ submit() → Pillar Council votes
                   ▼
              ┌──────────┐
              │registered│  spec.yaml locked (pre-registered)
              └────┬─────┘
                   │ execute()
                   ▼
              ┌──────────┐
              │executing │  runner launches, checkpoints written
              └────┬─────┘
                   │ complete() → results ready
                   ▼
              ┌──────────┐
              │  review  │  Adversarial Council + Statistician
              └────┬─────┘
               ┌───┴───┐
               ▼       ▼
          ┌────────┐ ┌────────┐
          │published│ │rejected│
          └────────┘ └────────┘
```

### Transitions

| From | To | Trigger | Guard |
|------|----|---------|-------|
| draft | registered | `pipeline.submit(id)` | ≥12/16 Council approve |
| registered | executing | `pipeline.execute(id)` | Data cached, pre-reg locked |
| executing | review | `pipeline.complete(id)` | All trials done or max_duration |
| review | published | `pipeline.publish(id)` | Meta-Reviewer Accept |
| review | rejected | `pipeline.reject(id)` | Meta-Reviewer Reject or veto |
| draft | draft | `pipeline.revise(id)` | Re-submit revision |
| review | registered | `pipeline.revise(id)` | Major revise → re-execute |
| any | draft | `pipeline.reset(id)` | Manual reset |

## Entry Point

```python
# usage: python -m rlaaer <subcommand> <args>

# Subcommands:
#   pipeline new     <title> [--hypothesis] -- create new experiment
#   pipeline submit  <id>                 -- submit to Council
#   pipeline execute <id>                 -- run experiment
#   pipeline review  <id>                 -- run review
#   pipeline publish  <id>                -- publish results
#   pipeline status  [<id>]              -- show status
#   pipeline list                         -- list all experiments
#
#   agent run        <role> <spec.yaml>   -- run a single agent
#   agent test       <role>               -- run agent's test suite
#
#   council register <experiment_id>      -- submit to Pillar Council
#   council review   <experiment_id>      -- Adversarial Council review
#
#   data scrape      <source> <query>     -- scrape data source
#   data transform   <dataset> <config>   -- transform dataset
```

## File Ownership

| File | Owned By | Purpose |
|------|----------|---------|
| `experiments/<id>/spec.yaml` | Designer agents | Canonical spec (locked after registration) |
| `experiments/<id>/run.py` | Experiment Synthesizer | Executable entrypoint |
| `experiments/<id>/metrics/` | Metric Designer + Metric extractors | Metric output CSVs |
| `experiments/<id>/README.md` | Editor | Human-readable experiment docs |
| `experiments/<id>/manuscript.md` | Editor | Full publication manuscript |
| `experiments/<id>/manuscript.tex` | Editor | LaTeX publication |
| `rlaaer/data/cache/<hash>` | Domain Scraper | Raw downloaded data |
| `rlaaer/data/transformed/<id>_<source>.csv` | Data Scientist | Transformed data |
| `rlaaer/data/sourced_datasets.json` | Domain Scraper | Dataset registry |

## CI Integration

CI lives at `.github/workflows/ci.yml` and runs the regression suite at the commit SHA.

R-LAAER tests are not yet in CI. To add them, extend `.github/workflows/ci.yml` with:

```yaml
      - name: Run R-LAAER tests
        run: |
          python -m pytest rlaaer/tests/ -v
      - name: Validate all spec.yamls
        run: |
          python -c "from rlaaer.validation import validate_spec; import glob
          for f in glob.glob('experiments/*/spec.yaml'):
              validate_spec(f)"
      - name: Run regression suite
        run: |
          python regressions/regression_suite.py
```

Note: R-LAAER tests depend on `requests` and `pytest` which are not in `requirements.txt`.
They are currently excluded from CI to keep the workflow lightweight.
