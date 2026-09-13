---
name: instrument-a-trace
description: Build EvalTrace/EvalSpan correctly from your own agent's data, including how to normalize legacy or differently-shaped trace payloads with a trace_adapter.
---

# Instrument a trace

## Trigger

Use this when you're producing the `trace` field of an `EvaluationSample`
for the first time, or when a `TestCase`'s latency/cost/tool checks are
silently passing or failing in a way that doesn't match reality.

## Do

1. Populate `EvalTrace.total_latency_ms` and `.estimated_cost_usd`
   directly as plain numbers — this is not a computed property here (it
   is on some richer trace schemas). If you're deriving it from
   timestamps or per-call costs, do that arithmetic yourself before
   constructing the `EvalTrace`.
2. Give every tool-calling `EvalSpan` a `tool_name` — `required_tools`,
   `forbidden_tools`, `tool_call_precision`, and `tool_call_recall` all
   filter on `span.tool_name is not None`; a span with `tool_name=None`
   is invisible to every tool-based check.
3. Put arguments a `required_tool_arguments` check needs under
   `span.attributes["tool_args"]` — that's the exact key the built-in
   check reads.
4. If your traces come from a system with a different native shape (e.g.
   timestamp-derived latency, per-span rather than trace-level cost), use
   the `trace_adapter` parameter on `load_samples()`/`run_live_suite()`:
   write one small function that maps your raw trace dict into
   `EvalTrace`'s shape, and pass it once at the call site rather than
   converting ad hoc everywhere you build a sample.
5. Set `estimated_cost_usd=None` (the default) when cost genuinely isn't
   known for a sample — every cost check in this package treats `None` as
   "unavailable," never as `$0.00`. Never pass `0.0` to mean "unknown."

## Avoid

- Don't leave `total_latency_ms` at its default `0.0` for a real sample —
  every `max_latency_ms` check will trivially pass, which looks like a
  release gate working when it's actually blind.
- Don't put tool arguments somewhere other than
  `attributes["tool_args"]` and expect `required_tool_arguments` to find
  them — it looks at that exact key, not the whole `attributes` dict.
- Don't silently drop a trace field your source system provides just
  because `EvalSpan`/`EvalTrace` doesn't ask for it — pydantic ignores
  unknown fields by default, so a payload shaped for a different schema
  validates "successfully" while quietly losing the data you needed.

## Check

- Build one `EvalTrace` by hand from a real sample and print it — confirm
  `total_latency_ms`, `estimated_cost_usd`, and every span's `tool_name`
  match what you know actually happened, not just that validation passed.
- If you wrote a `trace_adapter`, unit test it directly against a raw
  payload sample, independent of `evaluate_suite` — a normalization bug
  there fails silently (defaults to 0/None) rather than raising.

## Risk

A trace payload that predates `EvalTrace`'s shape (timestamps instead of
`total_latency_ms`, per-span cost instead of trace-level) validates fine
and produces a *plausible-looking* report with latency/cost silently
defaulted to 0/None — this doesn't error, so it can pass code review and
still gate a release on wrong numbers. Always adapt at the boundary
(a `trace_adapter`), not by hoping downstream fields line up.
