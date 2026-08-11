# Evaluation harness

`questions.json` contains 30 research prompts spanning current events, software, fact checking, comparisons, science, legal/regulatory research, products, general research, and social-signal research.

The dataset is intentionally **answer-independent**: many questions are time-sensitive, so a static answer key would become stale. Each run stores its own evidence artifacts and can optionally receive external judge scores in `report_manifest.json`:

```json
{
  "evaluation": {
    "factual_precision": 0.95,
    "citation_precision": 0.98,
    "completeness": 0.88
  }
}
```

## Suggested experiment

Run the same question IDs with:

- baseline Hermes without the skill;
- upstream/v4 behavior if available;
- v6 `moderate`;
- v6 `exhaustive`;
- v6 `maximum` only for stress testing.

Store completed run directories under a local path such as `eval-runs/<system>/<question-id>/` and aggregate them:

```bash
python3 scripts/benchmark.py eval-runs/v6-moderate/* --json
```

The built-in metrics are deterministic:

- validated-run rate;
- semantic/structural pass rate;
- citation coverage across prose, lists, steps, blockquotes, and table rows;
- hidden claim-marker coverage;
- primary-source ratio;
- current source-access health;
- peak budget utilization;
- unresolved critical claims.

Factual precision and completeness require an external human/model judge or a task-specific gold set; the benchmark does not pretend those semantic metrics can be derived reliably from structure alone.
