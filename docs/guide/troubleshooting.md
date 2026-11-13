# Troubleshooting

Check the failing boundary before changing application behavior.

- Duplicate or unknown case IDs: reconcile the suite-to-sample mapping.
- Incomplete tool capture: do not claim forbidden-tool compliance from absent instrumentation.
- Missing latency: avoid performance gates until timing is available.
- Judge unavailable: distinguish a provider failure from a low-quality agent answer.

## Verify your environment

Run commands from the environment where you installed the package. Confirm the input file exists and matches the expected artifact contract. Keep the original evidence when diagnosing a failure.
