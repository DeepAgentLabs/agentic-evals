// Preserve bookmarks into the former single-page HTML guide.
(() => {
  const routes = {
    intro: 'getting-started/', install: 'getting-started/#installation',
    'first-eval': 'getting-started/#your-first-eval-in-60-seconds',
    'eval-trace': 'core-concepts/#evaltrace-and-evalspan',
    'test-suite': 'core-concepts/#testsuite-and-testcase',
    evaluators: 'core-concepts/#evaluators', scores: 'core-concepts/#scores-and-reports',
    'eval-api': 'api-reference/#eval-quickstart', 'suite-api': 'api-reference/#testsuite-api',
    'scorers-api': 'api-reference/#scorers-library', 'gates-api': 'api-reference/#release-gates',
    'live-targets': 'api-reference/#live-targets',
    'custom-evaluators': 'advanced/#custom-evaluators',
    'eval-packs': 'advanced/#eval-packs', registry: 'advanced/#evaluator-registry'
  };
  const path = window.location.pathname.replace(/index\.html$/, '');
  if (/\/agentic-evals\/docs\/$/.test(path)) {
    const target = routes[window.location.hash.slice(1)];
    if (target) window.location.replace(new URL(target, window.location.origin + path));
  }
})();
