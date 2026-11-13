# Core concepts

| Concept | Meaning |
| --- | --- |
| TestCase | Defines input and expectations; it is not generated from the answer being scored. |
| EvaluationSample | Matches a case ID to observed output and an EvalTrace. |
| EvalTrace / EvalSpan | Minimal normalized evidence, including tool name, arguments, latency, cost and metadata. |
| Score | A named result with a numeric value, pass/fail outcome, explanation, and evaluator identity. |
| Report vs gate | A report records scores; a GateConfig decides whether that evidence meets release policy. |
| Skipped vs unavailable | Not-applicable scoring is different from a judge that failed to deliver a verdict. |
