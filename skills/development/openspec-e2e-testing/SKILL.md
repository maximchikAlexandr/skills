---
name: openspec-e2e-testing
description: Execute OpenSpec-based E2E tests and independent agent checks, capture before/after output images, preserve reproducible evidence and verify delivered CI coverage. Use for a tester's verification task, not planning or PR management.
---

# OpenSpec E2E Testing

Execute the supplied E2E plan against an exact product revision. Read OpenSpec as the source of expected behavior; do not author planning artifacts, change production code or manage the product PR. Work only within the assigned test scope and execution permissions.

## 1. Read the specification and assigned cases

Require an identifiable OpenSpec change/revision and the assigned E2E plan. Resolve actual project/store and active or archived paths. Without OpenSpec, request the missing specification and stop.

Read proposal, design, tasks, delta specs and affected main specs. Resolve added/modified/removed/renamed requirements: unchanged parts still apply, superseded scenarios do not, and renamed requirements retain their behavior unless changed. A completed checkbox is not proof of execution.

Inspect the relevant product diff, public entrypoints, existing fixtures/tests, visible output and actual CI jobs. Use them for feasibility and risk; do not invent requirements. Report contradictions or missing material decisions for clarification instead of rewriting the spec.

Consume the plan's case matrix, local script paths, manual steps, image/artifact requirements and planned CI coverage. Verify each case maps to an OpenSpec scenario and, where applicable, the affected OpenAPI operation/schema. Check expected results against those contracts. Do not redesign coverage or add unassigned cases; report missing material decisions to the requester. A case already covered or excluded by the plan needs no ceremonial duplicate E2E. Record observed results against the assigned matrix.

## 2. Implement and run local tests

Read toolchain, workspace/resource ownership, test-code destination and publication parameters from the assigned environment or task. Verify them before execution; do not assume a particular CLI, host or issue tracker. Keep private values out of public surfaces.

Use isolated test-owned state and the installed product from a recorded SHA. Reuse existing runners and fixtures; write reproducible test scripts, necessary setup and failure-safe cleanup at the task-assigned test-code location, whether in the product repository or a separate workspace. Avoid a parallel runner/validator framework. Verify commands, expected exit codes and meaningful assertions through public CLI/SDK/API/UI boundaries.

Separate runner preparation from live execution. Before consuming a live attempt, use one resolved binding map for command arguments and every case phase; check required resources, restore/readiness steps, captures and assertions against recorded actual responses. In managed E2E work, offline self-tests of the runner's parsing, substitution and assertions are allowed without Odoo, PostgreSQL or Docker, even when local product tests are disallowed. This narrow permission does not authorize other local tests or change the live attempt budget. Fix preparation errors before starting or repeating live cases; preserve the existing attempt ledger and evidence.

Run the tests freshly; distinguish pass, fail, blocked and not run. Missing prerequisites are blockers, not successful skips. Clean up only resources owned by the run, including on failure; preserve committed evidence. Do not change production behavior to make a test pass.

## 3. Perform independent agent checks and capture images

Walk through each relevant user path independently of its automated test. Execute public actions and inspect actual outputs, generated files or system state. Running the same test twice is not a manual check. Record steps and expected/actual observations separately; explain any case without a useful independent check.

Follow the plan's image cases. Before/after images are mandatory for changed CLI tables/read-command output, logs, progress states and final summaries. For changed browser UI, capture actual browser screenshots when the environment supports it. Do not create decorative images for unchanged output.

Run baseline and candidate versions against equivalent fixtures, terminal width, locale and output mode; record both SHAs and commands. Reset mutable state between versions. Never invent baseline output. Report unavailable baseline/capture as a concrete evidence gap rather than a complete comparison.

Use the capture tool provided by the environment. Preserve the actual command, tested revision and exit status; validate that status against the case's expectation. Apply identical labelled redactions without hiding changed behavior, inspect resulting images and avoid silent cropping.

Label text renders as renders of captured output, not terminal-window screenshots. Capture actual supported progress states; if only the final summary is available, report that limit. Do not claim unsupported ANSI/TTY or interactive behavior was observed. Never synthesize output or redraw it to imply success.

Optional tool: on macOS with Swift/AppKit, the bundled [render_terminal.swift](scripts/render_terminal.swift) can render reviewed, sanitized plain UTF-8 text to PNG: `swift "$SKILL_DIR/scripts/render_terminal.swift" "Output title" captured-output.txt output.png`. SKILL_DIR is this skill's installed directory. This helper rejects ANSI and carriage-return controls; it does not emulate a terminal. Use it only when suitable for the assigned environment; other capture tools are equally valid and require no Swift installation.

## 4. Preserve and publish evidence

Store scripts, reusable fixtures and actual generated files at the assigned destinations, keeping authored tests distinguishable from generated evidence. Follow the environment's repository/review/commit and publication contract rather than imposing a hosting service or fixed commit structure. If no generated files are applicable, explain why instead of manufacturing them.

Select only files or state projections that prove the requirements. Preserve genuine generated content; avoid environment dumps, build binaries and unrelated logs. Record compact scenario/revision/command/exit-status provenance, separating the product revision actually tested from test-code/evidence revisions. Resolve revisions at execution time and record them; no manual hardcoding in command templates is required.

Keep evidence accessible after routine teardown. Publish concise per-case automated and independent-check verdicts, findings, tested revisions and evidence references through the assigned channel. Include required image pairs labelled by scenario and baseline/candidate revision; verify delivery and accessibility using that channel's read-back mechanism. Before capture/publication, redact private values and sensitive data from text, pixels, filenames and metadata. Report missing required evidence explicitly.

## 5. Verify delivered CI coverage

Follow the plan's CI dispositions and inspect delivered tests, fixtures and results against the specified assertions and product revision. Respect the environment's CI implementation ownership; do not add or modify CI tests, fixtures or workflows unless the assigned role explicitly owns that work. Report missing or incorrect coverage through the prescribed finding/fix route. Local evidence must not become an undeclared private dependency of CI.

Record actual local and CI results separately; neither substitutes for the other. Pending CI is not green. Report unavailable CI evidence or infeasible prerequisites rather than expanding scope. Do not manually trigger external jobs without execution authorization.

## Completion

Agent-authored test code and explanatory text are in English. Preserve the original language and tested locale of generated files, exported translations, captured output and images, subject to the required privacy redactions; do not translate evidence to satisfy the English rule. Do not transfer discussion history, approval policies, routing or review ledgers into Git. Return the verified evidence references, observed results and remaining gaps. Report automated checks, independent checks and evidence completeness separately. Overall PASS requires fresh successful execution, completed required independent checks, and every required artifact/image published and accessible. If required evidence is missing, mark overall verification incomplete or blocked even when automated checks pass; identify the missing item. Status updates, delegation and external publication follow the agent environment's permissions and workflow. Return evidence to the requester; this skill grants no additional authority.
