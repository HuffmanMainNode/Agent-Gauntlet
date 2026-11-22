# Results and Metrics

The Gauntlet reports a vector of measurements, not a universal intelligence ranking.

- **Task behavior:** required task contract satisfied or not.
- **Claim traceability:** claims reference supplied evidence records.
- **Unsupported claims:** claims without valid evidence references.
- **Abstention:** agent declines to answer when evidence is insufficient.
- **Conflict detection:** agent explicitly reports incompatible source records.
- **Robustness:** performance across multiple seeds and input variations.
- **Operational reliability:** timeouts, crashes, malformed output, and retries.
- **Repeatability:** variation across repeated runs with the same inputs.
- **Calibration:** future metric comparing stated confidence with observed correctness over a sufficiently large labeled sample.

Do not treat evidence references as semantic proof. Do not treat confidence numbers as calibrated probabilities without validation. Publish per-suite distributions and raw evidence so third parties can challenge the result.
