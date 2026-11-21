# Complete scorer and rubric catalog

Agentic Evals has two scoring interfaces: the small `Eval()` helper consumes simple score functions, while structured suites use registered evaluators receiving `EvaluationContext`. They have different inputs and are not interchangeable. Current names are exported from the package root; exact signatures are included in the robust reference.

## Lightweight Eval scorers

Pass these functions in `Eval(..., scores=[...])`:

| Helper | Inputs and behavior |
| --- | --- |
| `equals` | String equality after converting and stripping surrounding whitespace |
| `contains` | Case-sensitive containment after string conversion; lists/tuples require every item |
| `icontains` | Case-folded containment; lists/tuples require every item |
| `levenshtein` | Character edit similarity in [0, 1] |
| `matches` | Regex search, with expected supplying the pattern |
| `numeric_close` | Numeric closeness using 1% relative tolerance and a small absolute tolerance |

Custom functions receive the named `input`, `output` and/or `expected` parameters they declare. Supported results include bool/number, `Score`, and a `{"score": value, "name": label}` dictionary. An Eval case passes when every returned score reaches its threshold. `EvalResult` retains case results, timing and overall pass state; `agentic-evals run` uses that state for its exit code.

## Case expectations and named scorers

`TestCase` fields enable implicit checks before configured evaluators: exact output, every required substring, JSON Schema/required fields, tool presence/absence/arguments/order, latency, cost and turn limits. Adding a named evaluator does not disable unrelated checks. `EvaluatorConfig.required=False` makes ordinary evaluator failure optional; containment has stricter required semantics.

For `levenshtein_similarity`, `embedding_similarity`, `json_diff`, `numeric_diff`, `starts_with` or `ends_with`, omitting evaluator `config.reference` lets that scorer grade `case.expected_output`; the runner then omits its implicit exact-match check. Supplying an explicit reference leaves any separate `expected_output` check active. Rubric references always use `config.reference`.

`contains_any` reads `case.expected_contains`, but the runner still performs an implicit check for **every** entry in that list. Adding `contains_any` therefore does not change a suite case into any-match semantics. For any-match-only behavior, register a custom evaluator with its own configured alternatives and leave `case.expected_contains` empty.

Named scorer results run through their evaluator wrapper, which applies `EvaluatorConfig.threshold` to the returned value. The default is 1.0. Thus a graded `numeric_diff` value outside its configured tolerance can pass with a lowered threshold; choose 1.0 when the tolerance itself must be strict. Unavailable judge scores never pass regardless of threshold. See [core data model](core-concepts.md) for skipped, required and aggregate semantics.

## Deterministic scorers

`default_registry()` includes the following twelve names. Pure comparison logic makes no provider call; `embedding_similarity` explicitly invokes a caller-supplied callback.

| Registry name | Required inputs/config | Comparison and score |
| --- | --- | --- |
| `exact_match` | `case.expected_output` | Strips both strings, then compares exactly; 0/1 |
| `contains_all` | Nonempty `case.expected_contains` | Case-folded containment of every entry; 0/1 |
| `contains_any` | Nonempty `case.expected_contains` | Case-folded containment of any entry; 0/1; implicit-all caveat above |
| `levenshtein_similarity` | `config.reference` or `case.expected_output` | Stripped character edit similarity; `1 - distance / max(lengths, 1)` |
| `embedding_similarity` | Reference plus callable `config.embed_fn(text) -> vector` | Equal-length vector cosine rescaled from [-1, 1] to [0, 1]; raw cosine kept in metadata |
| `valid_json` | Sample output | JSON parsing success; 0/1 |
| `json_diff` | Reference JSON text | Parsed structural equality, ignoring object key order; 0/1 with first-difference explanation |
| `numeric_diff` | Numeric reference; optional `rel_tol` (1e-6), `abs_tol` (1e-9) | 1 inside tolerance, otherwise bounded relative closeness; threshold interaction above |
| `regex_match` | `config.pattern`; optional `case_insensitive`, `full_match` | Regex search by default, fullmatch when requested; 0/1 |
| `starts_with` | Reference | Case-folded prefix check, without stripping; 0/1 |
| `ends_with` | Reference | Case-folded suffix check, without stripping; 0/1 |
| `numeric_range` | At least one of `config.min`, `config.max` | Parse output as float and check inclusive bounds; 0/1 |

Invalid/missing scorer configuration raises rather than inventing a pass. JSON parsing, similarity and numeric checks are narrower than semantic correctness; use the case's explicit JSON Schema field for a structural output contract.

```python
from agentic_evals import (
    EvaluationSample, EvaluatorConfig, EvalTrace, TestCase, TestSuite,
    default_registry, evaluate_suite,
)

suite = TestSuite(name="prefix", version="1", cases=[
    TestCase(id="one", name="Prefix", evaluators=[
        EvaluatorConfig(name="starts_with", config={"reference": "Answer:"}),
    ]),
])
report = evaluate_suite(
    suite, [EvaluationSample(case_id="one", output="Answer: 42", trace=EvalTrace())],
    registry=default_registry(),
)
assert report.summary.pass_rate == 1.0
```

For embedding comparisons, provide `embed_fn` in Python or build a trusted registry wrapper that injects it. An executable function cannot be represented by an ordinary JSON/YAML value; no provider/embedding client is created from a string.

## Trajectory scorers

These four additional default registry names use normalized trace evidence:

| Registry name | Inputs/config | Behavior |
| --- | --- | --- |
| `tool_call_precision` | `config.allowed_tools` or `case.required_tools` | Share of recorded tool calls in the allowed set; no tool calls scores 0 |
| `tool_call_recall` | Nonempty `case.required_tools` | Share of required tool names present in spans |
| `no_redundant_tool_calls` | Tool spans and their `attributes` | Share not duplicating an earlier tool-name/serialized-attributes pair; no calls scores 1 |
| `trajectory_efficiency` | Positive `baseline_latency_ms` and/or `baseline_cost_usd` | Mean of available `min(1, baseline/observed)` ratios; unavailable cost is omitted; no usable component raises |

The suite's implicit required-tool checks still apply. To use precision without requiring every allowed tool, put the allowed set in `config.allowed_tools`. Repetition uses all serialized attributes, so the host must normalize them consistently. Baselines are caller-supplied observations, not estimates inferred from tool names.

```yaml
# An evaluator fragment inside a TestCase (supply the case id/name and samples).
evaluators:
  - name: tool_call_precision
    threshold: 0.9
    config: {allowed_tools: [search, read_order]}
  - name: trajectory_efficiency
    threshold: 0.8
    config: {baseline_latency_ms: 1000, baseline_cost_usd: 0.02}
```

## Rubric templates and custom criteria

All ten templates require an explicitly registered `LLMRubricEvaluator` and a host-supplied sync/async `complete_fn`. None is registered by default because the core provides no model client. Case input supplies source/context where applicable; reference-based rubrics read evaluator `config.reference`.

| Template | Intended criterion and inputs | Verdict scores |
| --- | --- | --- |
| `FACTUALITY` (`factuality`) | Consistency and coverage against an expert reference; uses `config.reference`. | `A`=1, `B`=0.85, `C`=0.6, `D`=0, `E`=0.3 |
| `CLOSED_QA` (`closed_qa`) | Correctness/completeness of an answer given source context in case input. | `A`=1, `B`=0.5, `C`=0 |
| `SUMMARY_QUALITY` (`summary_quality`) | Accuracy, key-point coverage and concision relative to source input. | `A`=1, `B`=0.7, `C`=0.3, `D`=0 |
| `BATTLE` (`battle`) | Pairwise preference: sample output is candidate A; `config.reference` is candidate B. | `WIN_A`=1, `TIE`=0.5, `WIN_B`=0 |
| `TRANSLATION` (`translation`) | Meaning preservation and fluency relative to source input. | `A`=1, `B`=0.7, `C`=0.3, `D`=0 |
| `SECURITY` (`security`) | Model judgment of vulnerabilities in supplied code/output; not an enforcement layer. | `A`=1, `B`=0.7, `C`=0.3, `D`=0 |
| `SQL_CORRECTNESS` (`sql_correctness`) | Model judgment of SQL equivalence against `config.reference`; never executes SQL. | `A`=1, `B`=0.5, `C`=0 |
| `POSSIBLE` (`possible`) | Whether the response answers when possible or acknowledges insufficient information. | `A`=1, `B`=0.4, `C`=0 |
| `PII_LEAKAGE` (`pii_leakage`) | Model judgment of unwarranted sensitive-data disclosure relative to input context. | `A`=1, `B`=0.5, `C`=0 |
| `MODERATION` (`moderation`) | Model judgment of harmful content under the template policy; not a moderation service. | `A`=1, `B`=0.5, `C`=0 |

The score reaches `EvaluatorConfig.threshold` to pass. Verdict parsing accepts supported explicit/bare forms; unparseable or ambiguous completions are not guessed. They count as failed attempts under `RetryPolicy`; exhaustion yields an unavailable judgment. Full prompt templates are maintained in `src/agentic_evals/scorers/rubric.py`.

`make_rubric(name, criteria, *, levels=None, with_reference=False)` assigns A/B/... to 2–26 caller-defined `(description, score)` levels, each in [0, 1]. With no levels, it uses pass/fail. Set `with_reference=True` and configure `reference` to show one alongside the output. `RubricTemplate.render()` also accepts configured `extra` placeholders for custom templates.

This complete offline example uses a fixed verdict to demonstrate the integration contract, not actual model judgment:

```python
from agentic_evals import (
    EvaluationSample, EvaluatorConfig, EvalTrace, JudgeResponse, LLMRubricEvaluator,
    TestCase, TestSuite, default_registry, evaluate_suite, make_rubric,
)

concise = make_rubric("concise", "At most two sentences, with no preamble.")


def fixed_completion(prompt):
    return JudgeResponse(text="A", cost_usd=0.0, cost_source="measured", model="offline-fixture")


registry = default_registry()
registry.register(LLMRubricEvaluator("concise", concise, complete_fn=fixed_completion, version="1"))
suite = TestSuite(name="rubric-demo", version="1", cases=[
    TestCase(id="one", name="Concise", evaluators=[EvaluatorConfig(name="concise")]),
])
report = evaluate_suite(
    suite, [EvaluationSample(case_id="one", output="The answer is 42.", trace=EvalTrace())],
    registry=registry,
)
assert report.summary.pass_rate == 1.0
```

Return `JudgeResponse` rather than plain text when token/cost/model/provider usage is available. Unknown usage stays unknown; there are no built-in provider prices. See [retries, repeated samples, agreement and unavailable gates](judge-reliability.md).

## Default registry and packs

`builtin_scorer_names()` returns 17 names: the twelve text/numeric scorers, four trajectory scorers and `containment`. Default containment has no trusted verifier and fails closed; replace it through a host registry when using authenticated observations. See [containment setup](containment.md).

The six lightweight `Eval()` helpers and ten rubric templates are separate from those 17 default registry entries. `load_pack()` validates that a supplied/default registry contains each required scorer name. A present name does not establish configured provider credentials or verifier trust. See [all four packs and custom bundle format](advanced.md#eval-packs).
