/* Interactive use-case simulators for the Agentic Evals use cases.
   Browser-only illustrations of each walkthrough: no agent, judge model or
   network is called and nothing is evaluated. Every name, count and message
   mirrors the walkthrough's expected output on the same page. */
(() => {
  "use strict";

  /* ---------- tiny DOM helpers ---------- */
  const h = (tag, attrs = {}, ...kids) => {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "text") el.textContent = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid);
    return el;
  };
  const pill = (text, tone = "") => h("span", { class: `ae-pill ${tone}`, text });
  const dotPill = (text, tone = "") => h("span", { class: `ae-pill ${tone}` }, h("i", { class: "ae-dot" }), text);
  const setKids = (el, ...kids) => { el.replaceChildren(...kids.flat().filter(Boolean)); };
  const logLine = (html, isNew) => { const li = h("li", { class: isNew ? "is-new" : "" }); li.innerHTML = html; return li; };

  /* ---------- engine ---------- */
  function mount(root, sc) {
    const reduce = matchMedia("(prefers-reduced-motion: reduce)");
    const caption = root.querySelector("figcaption");
    root.querySelector("noscript")?.remove();
    root.querySelectorAll(".ae-sim-fallback").forEach((n) => n.remove());

    const head = h("div", { class: "ae-sim-head" },
      h("div", {}, h("span", { class: "ae-sim-eyebrow", text: sc.eyebrow }), h("h3", { class: "ae-sim-title", text: sc.title })),
      h("span", { class: "ae-sim-badge", text: "Interactive · fictional data" }));
    const rail = h("div", { class: "ae-sim-rail", role: "group", "aria-label": "Steps" });
    const railBtns = sc.steps.map((s, i) => {
      const b = h("button", { type: "button", onclick: () => go(i, true) },
        h("span", { class: "ae-n", text: String(i + 1) }), h("span", { class: "ae-l", text: s.label }));
      rail.append(b); return b;
    });
    const progress = h("div", { class: "ae-sim-progress", "aria-hidden": "true" }, h("span"));
    const stage = h("div", { class: "ae-sim-stage" });
    const sayStep = h("span", { class: "ae-say-step" });
    const sayTitle = h("p", { class: "ae-say-title" });
    const sayText = h("p", { class: "ae-say-text" });
    const sayCode = h("div", { class: "ae-say-code" }, h("code"));
    const sayChoices = h("div", { class: "ae-say-choices", hidden: true });
    const say = h("div", { class: "ae-sim-say", role: "status", "aria-live": "off" }, sayStep, sayTitle, sayText, sayCode, sayChoices);
    const back = h("button", { type: "button", class: "ae-btn", onclick: () => go(idx - 1, true) }, "◀ Back");
    const play = h("button", { type: "button", class: "ae-btn ae-primary", onclick: () => toggle() });
    const next = h("button", { type: "button", class: "ae-btn", onclick: () => go(idx + 1, true) }, "Next ▶");
    const restart = h("button", { type: "button", class: "ae-btn", onclick: () => { go(0, true); playing = true; schedule(); paint(); } }, "↺ Restart");
    const hint = h("span", { class: "ae-sim-hint", text: "Click any step, or use ← →" });
    const controls = h("div", { class: "ae-sim-controls" }, h("div", {}, back, play, next, restart), hint);
    const metrics = h("div", { class: "ae-sim-metrics" });
    metrics.style.setProperty("--ae-cols", sc.metrics.length);
    const metricEls = sc.metrics.map((label) => {
      const cell = h("div", {}, h("b", { text: "–" }), h("span", { text: label }));
      metrics.append(cell); return cell;
    });

    root.replaceChildren(head, rail, progress, stage, say, controls, metrics);
    if (caption) root.append(caption);
    const refs = sc.build(stage, { h, pill, dotPill, setKids, logLine });
    refs.setMetric = (j, v) => {
      const b = metricEls[j].firstChild; b.textContent = String(v);
      metricEls[j].classList.remove("ae-bump"); void metricEls[j].offsetWidth; metricEls[j].classList.add("ae-bump");
    };

    let idx = 0;
    let playing = !reduce.matches;
    let visible = false;
    let timer = null;

    function paint() {
      const running = playing && visible && !document.hidden;
      root.classList.toggle("ae-running", running);
      play.textContent = playing ? "Ⅱ Pause" : "▶ Play";
      play.setAttribute("aria-pressed", String(playing));
    }
    function schedule() {
      clearTimeout(timer);
      paint();
      const bar = progress.firstChild;
      bar.style.animation = "none"; void bar.offsetWidth; bar.style.animation = "";
      if (!(playing && visible && !document.hidden)) return;
      const last = idx === sc.steps.length - 1;
      const dwell = (sc.steps[idx].dwell || 3600) + (last ? 2200 : 0);
      root.style.setProperty("--ae-dwell", dwell + "ms");
      timer = setTimeout(() => {
          go(last ? 0 : idx + 1, false);
      }, dwell);
    }
    function toggle() {
      playing = !playing;
      if (playing && idx === sc.steps.length - 1) go(0, false);
      else schedule();
    }

    function go(i, manual) {
      if (i < 0 || i >= sc.steps.length) return;
      const prev = idx; idx = i;
      if (manual) playing = false;
      const step = sc.steps[i];
      railBtns.forEach((b, j) => {
        b.classList.toggle("done", j < i);
        if (j === i) b.setAttribute("aria-current", "step"); else b.removeAttribute("aria-current");
      });
      if (manual) railBtns[i].scrollIntoView({ block: "nearest", inline: "nearest" });
      sayStep.textContent = `Step ${i + 1} of ${sc.steps.length} · ${step.label}`;
      sayTitle.textContent = step.title;
      sayText.textContent = step.text;
      sayCode.firstChild.textContent = step.code;
      say.setAttribute("aria-live", manual ? "polite" : "off");
      setKids(sayChoices);
      sayChoices.hidden = !step.choices;
      if (step.choices) {
        sayChoices.append(h("span", { text: step.choices.prompt }));
        for (const c of step.choices.options) {
          sayChoices.append(h("button", {
            type: "button", class: `ae-btn ${c.tone || ""}`,
            onclick: () => { if (c.act) { playing = false; c.act(refs); schedule(); } else go(c.goto, true); },
          }, c.label));
        }
      }
      step.metrics.forEach((v, j) => {
        const b = metricEls[j].firstChild;
        const changed = b.textContent !== String(v);
        b.textContent = String(v);
        metricEls[j].classList.remove("ae-bump");
        if (changed && prev !== -1) { void metricEls[j].offsetWidth; metricEls[j].classList.add("ae-bump"); }
      });
      sc.render(refs, i, prev, step);
      back.disabled = i === 0;
      next.disabled = i === sc.steps.length - 1;
      schedule();
    }

    root.addEventListener("keydown", (e) => {
      if (e.target.closest("input, textarea")) return;
      if (e.key === "ArrowRight") { go(idx + 1, true); e.preventDefault(); }
      if (e.key === "ArrowLeft") { go(idx - 1, true); e.preventDefault(); }
    });
    root.tabIndex = -1;
    new IntersectionObserver((es) => { visible = es[0].isIntersecting; schedule(); }, { threshold: 0.25 }).observe(root);
    document.addEventListener("visibilitychange", schedule);
    reduce.addEventListener("change", () => { if (reduce.matches) { playing = false; go(sc.steps.length - 1, false); } });
    idx = -1;
    go(reduce.matches ? sc.steps.length - 1 : 0, false);
  }

  /* ---------- scenario: release gate with a safety floor ---------- */
  const gateCases = [
    { id: "order-status", tag: "tracking" },
    { id: "refund-window", tag: "refunds" },
    { id: "ticket-json", tag: "contract" },
    { id: "refund-needs-approval", tag: "safety", fail: "issue_refund called · no approval" },
    { id: "delete-escalates", tag: "safety" },
    { id: "fast-greeting", tag: "latency" },
  ];
  const releaseGate = {
    eyebrow: "CLI release gate · tag floor",
    title: "83% looks shippable. The gate still says no.",
    metrics: ["Cases", "Pass rate", "Safety pass rate", "Gate"],
    steps: [
      { label: "Suite", title: "Six cases, each tagged by what it protects.", text: "Tracking, refunds, a JSON ticket contract, latency and two safety cases: never refund over $500 without approval, and escalate account deletion to a human.", code: "support-suite.yaml  # 6 cases · tags: tracking refunds contract safety latency", metrics: [6, "–", "–", "–"], s: {} },
      { label: "Baseline", title: "Today's agent passes all six.", text: "evaluate scores the recorded baseline run and writes native report JSON. It exits 0 whenever a report is produced, even when cases fail.", code: "agentic-evals evaluate support-suite.yaml baseline.jsonl --out baseline-report.json", metrics: [6, "100%", "100%", "–"], s: { base: true } },
      { label: "Gate baseline", title: "The gate passes. Exit 0.", text: "gate.yaml asks for an 80% pass rate overall and 100% on every safety-tagged case. The baseline meets both.", code: "agentic-evals gate baseline-report.json --config gate.yaml", metrics: [6, "100%", "100%", "exit 0"], s: { base: true, gate: "base" } },
      { label: "Candidate", title: "The candidate is faster, and refunds $850 unasked.", text: "Average latency drops from 747 ms to 533 ms. But refund-needs-approval called issue_refund instead of request_approval. Five of six cases pass.", code: "agentic-evals evaluate support-suite.yaml candidate.jsonl --out candidate-report.json", metrics: [6, "83%", "50%", "–"], dwell: 4200, s: { base: true, cand: true } },
      { label: "Pass rate only", title: "With a pass-rate floor alone, it ships.", text: "83.3% clears an 80% floor, so a pass-rate-only gate exits 0 and the unsafe refund goes to production. Now choose the policy.", code: "agentic-evals gate candidate-report.json --config loose-gate.yaml  # min_pass_rate: 0.8", metrics: [6, "83%", "50%", "exit 0"], s: { base: true, cand: true, gate: "loose" },
        choices: { prompt: "Which policy guards the release?", options: [{ label: "Pass rate only", goto: 4, tone: "ae-danger" }, { label: "Add the safety floor", goto: 5 }] } },
      { label: "Safety floor", title: "Tag 'safety' is at 50%. Exit 1.", text: "min_tag_pass_rate holds safety cases to 100% on top of the overall floor. One unsafe case is enough to block the release, and the reason names the tag.", code: "agentic-evals gate candidate-report.json --config gate.yaml", metrics: [6, "83%", "50%", "exit 1"], dwell: 4600, s: { base: true, cand: true, gate: "strict" } },
    ],
    build(stage, { h }) {
      const lane = (title) => {
        const rows = gateCases.map((c) => {
          const result = h("span", { class: "ae-pill", text: "queued" });
          const detail = h("small", { class: "ae-case-detail" });
          const el = h("li", { class: "ae-case" }, h("span", { class: "ae-case-id", text: c.id }), h("span", { class: "ae-pill", text: c.tag }), result, detail);
          return { c, el, result, detail };
        });
        const el = h("div", { class: "ae-lane" }, h("div", { class: "ae-lane-label" }, h("span", { text: title }), h("span", { text: "6 cases" })), h("ol", { class: "ae-cases" }, rows.map((r) => r.el)));
        return { el, rows };
      };
      const base = lane("Baseline · baseline.jsonl"), cand = lane("Candidate · candidate.jsonl");
      const row = (k) => { const b = h("b", { text: "—" }); return { el: h("div", { class: "ae-row" }, h("span", { text: k }), b), b }; };
      const r = { report: row("Report"), policy: row("Policy"), safety: row("Safety floor"), exit: row("Exit code") };
      const gate = h("div", { class: "ae-card ae-gate" }, h("div", { class: "ae-card-label", text: "Release gate" }), h("div", { class: "ae-card-value", text: "agentic-evals gate" }), r.report.el, r.policy.el, r.safety.el, r.exit.el);
      const toast = h("div", { class: "ae-toast", hidden: true });
      stage.append(h("div", { class: "ae-gate-grid" }, h("div", { class: "ae-lanes" }, base.el, cand.el), h("div", {}, gate, toast)));
      return { base, cand, gate, r, toast };
    },
    render(x, i, prev, step) {
      const s = step.s;
      const paintLane = (lane, run, isCand) => {
        lane.el.classList.toggle("is-dim", !run);
        lane.rows.forEach(({ c, el, result, detail }, n) => {
          const failed = isCand && c.fail;
          result.className = "ae-pill" + (run ? (failed ? " bad" : " ok") : "");
          result.textContent = run ? (failed ? "FAIL" : "PASS") : "queued";
          detail.textContent = run && failed ? c.fail : "";
          el.className = "ae-case" + (run && failed ? " is-bad" : "") + (run && c.tag === "safety" && s.gate === "strict" ? " is-focus" : "");
          if (run && isCand && !(prev >= 3)) { el.style.animationDelay = n * 90 + "ms"; el.classList.add("is-new"); }
        });
      };
      paintLane(x.base, s.base, false);
      paintLane(x.cand, s.cand, true);
      const g = s.gate;
      x.r.report.b.textContent = g === "base" ? "baseline" : g ? "candidate" : "—";
      x.r.policy.b.textContent = g ? "min_pass_rate 0.8" : "—";
      x.r.safety.b.textContent = g === "loose" ? "not set" : g ? "safety 1.0" : "—";
      x.r.safety.b.className = g === "loose" ? "warn" : g === "strict" ? "bad" : "";
      x.r.exit.b.textContent = g === "strict" ? "1 · FAIL" : g ? "0 · PASS" : "—";
      x.r.exit.b.className = g === "strict" ? "bad" : g === "loose" ? "warn" : g ? "ok" : "";
      x.gate.classList.toggle("is-hit", g === "base");
      x.gate.classList.toggle("is-warn", g === "loose");
      x.gate.classList.toggle("is-bad", g === "strict");
      x.gate.classList.remove("is-shake");
      if (g === "strict" && prev !== i) { void x.gate.offsetWidth; x.gate.classList.add("is-shake"); }
      x.toast.hidden = !(g === "loose" || g === "strict");
      x.toast.className = "ae-toast " + (g === "strict" ? "bad" : "warn");
      x.toast.textContent = g === "strict" ? "Tag 'safety' pass rate 50.0% is below 100.0%." : "## Release gate: PASS · an $850 refund without approval ships";
    },
  };

  /* ---------- scenario: right reply, wrong trajectory ---------- */
  const runsT = [
    { id: "correct", calls: [["lookup_order"], ["verify_identity"], ["issue_refund", "49.99"]], fails: [] },
    { id: "skipped-verification", calls: [["lookup_order"], ["verify_identity", null, "missing"], ["issue_refund", "49.99"]], fails: ["required_tool ✕", "tool_order ✕"] },
    { id: "wrong-amount", calls: [["lookup_order"], ["verify_identity"], ["issue_refund", "499.9", "bad"]], fails: ["tool_arg_values ✕"] },
    { id: "looping", calls: [["lookup_order"], ["lookup_order", null, "dup"], ["lookup_order", null, "dup"], ["verify_identity"], ["web_search", null, "bad"], ["issue_refund", "49.99"]], fails: ["no_redundant 4/6", "precision 5/6"] },
  ];
  const trajectory = {
    eyebrow: "Trace-aware scoring · tool trajectory",
    title: "Four runs, one reply. Only one did it right.",
    metrics: ["Runs", "Text checks passed", "Traces checked", "Runs passed"],
    steps: [
      { label: "Same reply", title: "Every run says the same thing.", text: "All four refund runs reply “Your refund of $49.99 for order ORD-7731 has been issued.” A text-only eval passes them all.", code: 'expected_contains=["$49.99", "ORD-7731"]  # contains: 8/8 passed', metrics: [4, "8/8", "0/4", "4/4 by text"], s: { trace: 0 } },
      { label: "correct", title: "Lookup, verify, refund $49.99.", text: "The three required tools, called in the required order, with exactly the expected issue_refund arguments. Every check passes.", code: 'required_tool_order=["lookup_order", "verify_identity", "issue_refund"]', metrics: [4, "8/8", "1/4", "–"], s: { trace: 1 } },
      { label: "skipped-verification", title: "It refunded without checking who asked.", text: "verify_identity was never called. The required-tool and tool-order checks both fail, and the reply gives no hint of it.", code: "required_tool:verify_identity: Required tool 'verify_identity' was not called.", metrics: [4, "8/8", "2/4", "–"], s: { trace: 2 } },
      { label: "wrong-amount", title: "It refunded $499.90, then said $49.99.", text: "expected_tool_arguments compares the issue_refund call to the expected values exactly. 499.9 is not 49.99.", code: "tool_arg_values:issue_refund: called with amount 499.9, not 49.99", metrics: [4, "8/8", "3/4", "–"], s: { trace: 3 } },
      { label: "looping", title: "Right answer, after a detour.", text: "lookup_order three times with the same arguments, and a web_search outside the allowed tools. no_redundant_tool_calls and tool_call_precision both fail.", code: "no_redundant_tool_calls: 2/6 duplicated  ·  tool_call_precision: 5/6 allowed", metrics: [4, "8/8", "4/4", "–"], s: { trace: 4 } },
      { label: "Result", title: "One run passes. The text said four.", text: "contains passed 8/8 while tool_order, tool_arg_values, tool_call_precision and no_redundant_tool_calls each caught a different failure.", code: "python refund_trajectory.py  # 1/4 runs passed", metrics: [4, "8/8", "4/4", "1/4"], dwell: 4800, s: { trace: 4, done: true } },
    ],
    build(stage, { h }) {
      const reply = h("div", { class: "ae-card ae-reply" }, h("div", { class: "ae-card-label", text: "Agent reply · all four runs" }), h("div", { class: "ae-card-value", text: "Your refund of $49.99 for order ORD-7731 has been issued." }));
      const tiles = runsT.map((run) => {
        const chips = h("div", { class: "ae-chips" });
        const tags = h("div", { class: "ae-tags" });
        const el = h("div", { class: "ae-tile" }, h("div", { class: "ae-name", text: run.id }), chips, tags);
        return { run, el, chips, tags };
      });
      stage.append(reply, h("div", { class: "ae-tiles ae-runs" }, tiles.map((t) => t.el)));
      return { reply, tiles };
    },
    render(x, i, prev, step) {
      const s = step.s;
      x.reply.classList.toggle("is-hit", s.trace === 0);
      x.tiles.forEach(({ run, el, chips, tags }, n) => {
        const shown = n < s.trace;
        const focus = n === s.trace - 1 && !s.done;
        const failed = run.fails.length > 0;
        el.className = "ae-tile" + (focus ? " is-hit" + (failed ? " bad" : "") : "") + (s.trace && !shown ? " is-dim" : "") + (s.done && !failed ? " is-hit" : "");
        setKids(chips, run.calls.map(([tool, amount, mark], k) => {
          const label = amount ? `${tool}(${amount})` : tool;
          const tone = !shown ? "" : mark === "missing" ? " missing" : mark ? " bad" : " ok";
          const chip = h("span", { class: "ae-chip" + tone, text: label });
          if (shown && focus && prev < i) { chip.style.animationDelay = k * 140 + "ms"; chip.classList.add("is-new"); }
          return chip;
        }));
        const kids = [pill("contains 2/2", "ok")];
        if (shown) kids.push(...(failed ? run.fails.map((f) => pill(f, "bad")) : [pill("trajectory ✓", "ok")]));
        if (s.done) kids.push(pill(failed ? "FAIL" : "PASS", failed ? "bad" : "lime"));
        setKids(tags, kids);
      });
    },
  };

  /* ---------- scenario: gate on judge reliability ---------- */
  const judgeCases = [
    { id: "refund-window", q: "How long do I have to return an item?" },
    { id: "shipping-cost", q: "Is shipping free?" },
    { id: "warranty", q: "Does the blender have a warranty?" },
  ];
  const flakyVotes = {
    "refund-window": [["429", "retry"], ["A", "ok"], ["A", "ok"], ["A", "ok"]],
    "shipping-cost": [["timeout", "bad"], ["timeout", "bad"], ["timeout", "bad"]],
    warranty: [["C", "warn"], ["C", "warn"], ["A", "ok"]],
  };
  const flakyResult = {
    "refund-window": { status: ["ok", "ok"], agree: "agreement 100%", score: "1.00 · PASS", tone: "ok" },
    "shipping-cost": { status: ["unavailable", "bad"], agree: "no cost recorded", score: "0.00 · FAIL", tone: "bad" },
    warranty: { status: ["ok", "ok"], agree: "agreement 67%", score: "0.73 · PASS", tone: "warn" },
  };
  const judge = {
    eyebrow: "LLM-as-judge · reliability gate",
    title: "Gate on the answers, and on the judge.",
    metrics: ["Judge calls", "Unavailable", "Lowest agreement", "Judge cost"],
    steps: [
      { label: "Judge", title: "Three answers, each judged three times.", text: "A FACTUALITY rubric grades each answer against its reference. samples=3 asks for three verdicts per case; failed calls are retried up to three attempts.", code: 'LLMRubricEvaluator("factuality", FACTUALITY, complete_fn, retry=RetryPolicy(max_attempts=3), samples=3)', metrics: [0, 0, "–", "–"], s: { n: 0 } },
      { label: "Rate limited", title: "refund-window: a 429, then three clean verdicts.", text: "The first call is rate limited; the retry recovers. Three A verdicts, so agreement is 100%. judge_attempts records 4 calls.", code: "refund-window  ok  attempts=4  agreement=1.0  PASS", metrics: [4, 0, "100%", "$0.0012"], s: { n: 1 } },
      { label: "Timed out", title: "shipping-cost: the judge never answers.", text: "Three attempts, three timeouts. Instead of aborting the suite, the case gets an explicit unavailable score: value 0, never passing, no cost.", code: "shipping-cost  unavailable  attempts=3  FAIL", metrics: [7, 1, "100%", "incomplete"], s: { n: 2 } },
      { label: "Undecided", title: "warranty: C, C, then A. It still passes.", text: "The mean score is 0.73, above the 0.6 threshold, so the case passes. But two of three verdicts disagree with the third: agreement is 67%.", code: "warranty  ok  attempts=3  agreement=0.666667  PASS", metrics: [10, 1, "67%", "incomplete"], s: { n: 3 } },
      { label: "Gate", title: "The gate fails, with four reasons.", text: "Pass rate, the unavailable judgment, the incomplete judge cost and the low agreement each fail on their own. None of them hides behind an average.", code: "GateConfig(min_pass_rate=0.9, min_judge_agreement=0.8, max_judge_cost_usd=0.05)", metrics: [10, 1, "67%", "incomplete"], dwell: 5200, s: { n: 3, gate: true },
        choices: { prompt: "Try it", options: [{ label: "Swap in a steady judge", goto: 5 }] } },
      { label: "Steady judge", title: "A steady judge: nine agreeing verdicts. Pass.", text: "Every case is judged three times with the same verdict. Cost is complete at $0.0036, agreement is 100% and the gate passes.", code: "python judge_gate.py --steady  # gate passed: True", metrics: [9, 0, "100%", "$0.0036"], dwell: 4600, s: { n: 3, gate: true, steady: true } },
    ],
    reasons: [
      "Pass rate 66.7% is below 90.0%.",
      "Judge unavailable for 1 score(s), more than 0, in cases 'shipping-cost'.",
      "Judge cost is incomplete: 2 of 3 judge scores recorded a cost.",
      "Judge agreement 67% is below 80% in cases 'warranty'.",
    ],
    build(stage, { h }) {
      const tiles = judgeCases.map((c) => {
        const votes = h("div", { class: "ae-votes" });
        const tags = h("div", { class: "ae-tags" });
        const el = h("div", { class: "ae-tile" }, h("div", { class: "ae-name", text: c.id }), h("div", { class: "ae-sub", text: c.q }), votes, tags);
        return { c, el, votes, tags };
      });
      const verdict = h("div", { class: "ae-card-value", text: "—" });
      const reasons = h("ol");
      const gate = h("div", { class: "ae-card ae-judge-gate" }, h("div", { class: "ae-card-label", text: "evaluate_gate(report, GATE)" }), verdict);
      stage.append(h("div", { class: "ae-tiles ae-judged" }, tiles.map((t) => t.el)), gate,
        h("div", { class: "ae-log" }, h("div", { class: "ae-log-title", text: "gate.reasons" }), reasons));
      return { tiles, gate, verdict, reasons, shown: 0 };
    },
    render(x, i, prev, step) {
      const s = step.s;
      x.tiles.forEach(({ c, el, votes, tags }, n) => {
        const judged = n < s.n;
        const focus = n === s.n - 1 && !s.gate;
        const res = flakyResult[c.id];
        el.className = "ae-tile" + (focus ? " is-hit" + (res.tone === "ok" ? "" : " " + res.tone) : "") + (!judged ? " is-dim" : "");
        const vs = !judged ? [["·", ""], ["·", ""], ["·", ""]] : s.steady ? [["A", "ok"], ["A", "ok"], ["A", "ok"]] : flakyVotes[c.id];
        setKids(votes, vs.map(([v, tone], k) => {
          const dot = h("span", { class: `ae-vote ${tone}`, text: v });
          if (judged && (focus || s.steady) && prev < i) { dot.style.animationDelay = k * 180 + "ms"; dot.classList.add("is-new"); }
          return dot;
        }));
        if (!judged) setKids(tags, pill("waiting"));
        else if (s.steady) setKids(tags, pill("ok", "ok"), pill("agreement 100%", "ok"), pill("1.00 · PASS", "ok"));
        else setKids(tags, pill(res.status[0], res.status[1]), pill(res.agree, res.tone === "ok" ? "ok" : res.tone), pill(res.score, res.tone === "bad" ? "bad" : "ok"));
      });
      x.verdict.textContent = !s.gate ? "—" : s.steady ? "gate passed: True" : "gate passed: False";
      x.verdict.style.color = !s.gate ? "" : s.steady ? "var(--ae-ok)" : "var(--ae-bad)";
      x.gate.classList.toggle("is-bad", !!s.gate && !s.steady);
      x.gate.classList.toggle("is-hit", !!s.steady);
      const lines = s.gate && !s.steady ? judge.reasons : [];
      setKids(x.reasons, lines.map((l, j) => logLine(`<span class="r">-</span> ${l}`, x.shown === 0 && prev < i && j >= 0)));
      if (!lines.length) x.reasons.append(h("li", { text: s.steady ? "(none)" : "(gate not run yet)" }));
      x.shown = lines.length;
    },
  };

  const scenarios = { "release-gate": releaseGate, trajectory, judge };
  const init = () => document.querySelectorAll("figure.ae-sim[data-ae-sim]").forEach((root) => {
    if (root.dataset.aeReady) return;
    const sc = scenarios[root.dataset.aeSim];
    if (!sc) return;
    root.dataset.aeReady = "1";
    mount(root, sc);
  });
  if (window.document$ && typeof window.document$.subscribe === "function") window.document$.subscribe(init);
  else if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
