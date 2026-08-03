---
name: python-testing
description: Test Python behavior with pytest through public APIs, focused unit tests, parametrization, fixtures, snapshots, mocks, recorded integrations, async tests, and coverage analysis. Use when adding or changing Python behavior, reproducing a bug, designing or reviewing a test suite, or improving test infrastructure.
---

# Python Testing

Build the smallest test suite that convincingly protects user-visible behavior and important internal invariants.

## 1. Discover the local contract

Read the repository's contributor instructions, test configuration, nearby tests, and dependency files before writing tests. Identify:

- the supported Python versions and test runner;
- existing fixtures, helpers, markers, plugins, and naming conventions;
- the public API or observable boundary affected by the change;
- the narrowest commands that exercise the relevant tests;
- project-specific coverage, network, snapshot, and recording policies.

Do not introduce pytest, plugins, directory layouts, markers, or fixed coverage thresholds that the repository does not use. Finish when the planned tests and commands follow the local suite's conventions.

## 2. Select the execution branch

- **Implement or fix behavior:** follow the full workflow, including red-green-refactor and progressively wider verification.
- **Design tests:** identify boundaries, cases, fixtures, and commands, but do not change files or claim red/green results.
- **Review tests or infrastructure:** evaluate the existing suite against the boundary rules and review checklist, report evidence-backed findings, and do not mutate the repository unless the user also asks for fixes.
- **Improve test infrastructure:** apply only the discovery, isolation, selection, and verification rules relevant to the requested infrastructure change; do not require a behavior-level red test when the change has a different observable failure criterion.

Finish when the requested branch is explicit and later steps that require mutations or executed evidence are excluded from non-implementation work.

## 3. Choose the strongest useful boundary

Default to testing through the public API as a user would. Prefer, in order:

1. a public-API or integration test for user-visible behavior;
2. a focused unit test for an important internal invariant, defensive branch, or condition that cannot be reached reliably through the public API;
3. an end-to-end test only when lower layers cannot establish the behavior with enough confidence.

When an external service defines correctness, prefer a real interaction in an isolated test environment or a reviewed recording over a deep mock. Use a unit test when a recording or integration matcher cannot detect the internal request shape that matters. Every test below the public boundary must have a concrete reason to exist.

Finish when each required behavior is assigned to the lowest-cost boundary that would actually catch its regression.

## 4. Make the change red

For implementation work on new behavior or a bug fix, write or adjust the test first and run the narrowest relevant command. Confirm that it fails for the intended reason, not because of setup, imports, stale snapshots, missing credentials, or unrelated failures.

If the existing implementation already passes, strengthen the assertion until it distinguishes the required behavior from the current one. If a red test is impossible or inappropriate, state why before changing production code.

Finish only when the failure demonstrates the missing behavior or reproduced bug.

## 5. Design behavior-focused tests

- Assert outcomes, externally visible side effects, warnings, exceptions, and important outbound data; avoid private methods and incidental call sequences.
- Make the test name, docstring, setup, and assertions describe the same behavior.
- Keep load-bearing facts in assertions, never only in recordings, logs, or fixtures. A reviewed snapshot is an assertion when its structure demonstrates the behavior; use explicit assertions or matchers for critical or volatile facts that the snapshot cannot express safely.
- Cover the meaningful positive, negative, boundary, and absent-capability cases.
- For every changed boolean or capability branch, exercise both sides when reachable; line coverage alone does not prove branch combinations.
- Keep tests independent. Use `tmp_path`, isolated databases, temporary environment helpers, and cleanup-capable fixtures instead of shared mutable state.
- Place a fixture or helper near its test until reuse is real; move genuinely shared fixtures to the nearest appropriate `conftest.py`.
- Patch where a dependency is looked up, use `autospec=True` or a real interface when practical, and assert only interactions that are part of the contract.
- Use `pytest.raises(..., match=...)` and `pytest.warns(..., match=...)` when the message or migration guidance is part of the contract.
- Remove or update stale test docstrings, comments, and historical bug notes whenever behavior changes.
- Never cite mutable source line numbers in test names, comments, or docstrings.

Finish when every assertion protects a behavior or invariant that matters and no assertion merely freezes implementation detail.

## 6. Parametrize without hiding intent

Use `@pytest.mark.parametrize` when cases share the same arrange-act-assert flow.

- For a pure Cartesian matrix, keep expectations in a mapping keyed by the parameter tuple.
- For heterogeneous cases, define a small frozen dataclass with sensible defaults and per-case inputs, expected values, marks, and stable IDs.
- Keep each case's expected value beside that case so reviewers can verify it directly.
- Split cases into separate tests when parametrization needs branches or conditionals in the test body.

```python
from dataclasses import dataclass

import pytest


@dataclass(frozen=True)
class Case:
    id: str
    value: str
    expected: str


CASES = [
    Case(id="normal", value="  Alice ", expected="Alice"),
    Case(id="already-normalized", value="Bob", expected="Bob"),
    Case(id="unicode", value="  Renée ", expected="Renée"),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.id) for case in CASES])
def test_normalize_name(case: Case) -> None:
    assert normalize_name(case.value) == case.expected
```

Use a separate parametrized test for invalid values and expected exceptions. Finish when adding a case requires data rather than new control flow.

## 7. Handle structured, async, and external behavior

### Structured outputs

Use snapshots for complex stable structures only when the project already supports them. When writing or reviewing a snapshot test, read [references/snapshots.md](references/snapshots.md) for selection rules, volatile-value handling, and an example.

### Async code

Use the repository's async plugin and marker. When testing async behavior or lifecycle-managed async resources, read [references/async-tests.md](references/async-tests.md) for plugin selection, fixtures, mocks, and an example.

### Recorded HTTP or service interactions

When correctness depends on an external service and the repository records interactions, read [references/recorded-interactions.md](references/recorded-interactions.md) for the record/playback workflow, matcher integrity, credential isolation, and an example.

Do not make ordinary test runs depend on live credentials or unrestricted network access. Finish when the test is deterministic offline, or is explicitly marked and documented as requiring an external environment.

## 8. Go green, then refactor

For implementation work, make the minimum production change that passes the focused test. Run the narrow test until green, then refactor production and test code without weakening assertions.

Run progressively wider checks:

1. the affected test or node;
2. the containing test file or feature group;
3. the repository's relevant test suite, lint, and type-check commands;
4. coverage or branch reports only when required by the repository or useful for finding a concrete gap.

Coverage is evidence, not the goal. Investigate uncovered changed behavior and missing branch combinations instead of chasing an arbitrary percentage or testing third-party code.

Finish when all relevant checks pass, every required behavior is asserted, recordings and snapshots have been reviewed, and any skipped or environment-blocked verification is reported exactly.

## Review checklist

- For new behavior or a bug fix, the test was observed failing for the intended reason before the implementation change; for review-only work, do not infer historical red evidence.
- Public behavior is tested through a public boundary wherever practical.
- Unit tests pin only invariants that broader tests cannot protect reliably.
- Names, docstrings, parameters, and assertions agree.
- Positive, negative, boundary, and capability-branch cases are accounted for.
- Fixtures isolate state and have the narrowest useful scope.
- Mocks replace boundaries, not the behavior under test.
- Recorded fields asserted by the test also participate in matching.
- Snapshots contain reviewed, meaningful structure and tolerate only truly variable values.
- Narrow and relevant wider commands pass, or limitations are stated without claiming success.
