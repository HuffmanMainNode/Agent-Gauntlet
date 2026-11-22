# Contributing

Contributions are welcome through forks and pull requests.

## Challenge contributions
Include a stable challenge ID and version, clear task description and permissions, fixtures without secrets/private data, deterministic scoring where feasible, expected evidence, limitations, and tests for valid and invalid submissions.

## Adapter contributions
Do not add automatic execution of contributed adapter code to the core runner. Propose the adapter contract and threat model first. External execution must be opt-in and isolated.

## Evidence integrity
Do not submit fabricated results as real agent runs. Mark fixtures, simulations, human judgments, and independently observed executions accurately.

## Development
```sh
python -m pip install -e .
python -m pytest
```
