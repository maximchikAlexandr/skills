---
name: plan-openspec-e2e
description: Plan OpenSpec-based local E2E scripts, independent agent checks, before/after images, generated artifacts and extensions to existing CI tests. Use for a planning task; does not implement or execute tests.
---

# Plan OpenSpec E2E

Prepare the verification contract for the tester. Write it in the existing delivery-plan.md and keep related tasks/ownership coherent; do not create a parallel plan, test scripts or evidence during planning. Follow the normal planning publication and independent verification workflow.

## 1. Read the specification and affected contracts

Require an identifiable OpenSpec change and document revision. Resolve actual project/store and active or archived artifact paths. Without OpenSpec, request the missing specification and stop; do not substitute code or conversation for requirements.

Read proposal, design, tasks, delta specs and affected main specs. Resolve added/modified/removed/renamed requirements: retain unchanged parts, exclude superseded scenarios and preserve renamed behavior unless explicitly changed. Checked tasks are not evidence of a completed run.

Inspect the relevant implementation or proposed interfaces, existing tests/fixtures, visible CLI/UI output and actual CI workflows. Inspect affected OpenAPI operations, request/response schemas, status/error contracts and generated clients when applicable. Map those contracts back to OpenSpec requirements; OpenAPI describes the interface and does not replace the behavioral specification. If a required behavior is absent or contradictory, surface the specification gap rather than inventing it.

## 2. Select minimal cases and assign coverage

Translate affected WHEN/THEN scenarios into initial state, one meaningful public action and observable expected result. Group cases sharing a lifecycle; separate cases with different assertions or cleanup. Include specified negative cases and directly affected regressions, not a whole-CLI sweep.

Use one compact matrix:

`case ID | OpenSpec requirement/scenario | verification gap/local E2E decision | affected OpenAPI operation/schema, if any | local test script | independent agent steps | CI disposition/test/job | assertions | artifacts/images`

Every affected scenario/contract must map to a new case, existing coverage, a sufficient lower-level check or a reasoned exclusion. Select local E2E only when:

- A material expected result depends on a real interaction between components (processes, database/filesystem, external service or browser) that existing or planned unit/integration/contract/CI tests cannot adequately prove.
- The specification or delivery contract explicitly requires a live walkthrough or capture that those tests do not provide.

For each selected local case name the remaining verification gap, observable failure and why a cheaper check is insufficient. Choose the smallest setup and walkthrough that close that gap; justify costly prerequisites by the behavior they prove. Reuse adequate existing CI E2E instead of duplicating it locally. Missing coverage alone is not a reason for local E2E when adding a lower-level test suffices.

If no local gap or required live evidence remains, record `e2e_required=false`, the reason and concrete sufficient tests/assertions. Internal refactoring, documentation or build/configuration changes can qualify, but their label or patch size does not establish safety. A public API change alone does not require a live stand. Unavailable infrastructure is a blocker for a necessary check, not a reason to mark E2E unnecessary; preserve explicitly required checks.

For each selected case specify concrete CLI/SDK/API/UI calls, initial data, dependencies, expected outputs/exit codes, observable assertions and failure-safe cleanup. Reuse existing infrastructure and fixtures. Cover relevant OpenAPI request/result/error behavior at a real public boundary rather than merely checking that a schema file exists.

## 3. Specify local scripts and generated artifacts

Read environment, toolchain, test-code destination and evidence-publication parameters from the assigned task or agent environment. Identify missing material inputs; do not assume a hosting service, project-description format, commit count or publication channel. Public plans use parameter names instead of private values.

Specify test-script paths, entry commands, fixtures, setup/reset and failure-safe cleanup needed to repeat each scenario without the original agent session. Reuse the environment's language and runner; avoid parallel runner/validator layers. Require recording the product revision actually tested and distinguish it from test-code/evidence revisions. This does not require hardcoded hashes in command templates.

Choose generated files and state projections that demonstrate each requirement, with compact scenario/revision/command/exit-status provenance. Preserve actual generated content rather than manufacturing it with a model. Avoid environment dumps, build binaries and unrelated logs. Describe required delivery and accessibility checks using the supplied publication contract; preserve evidence through routine cleanup.

## 4. Plan independent agent checks and images

Specify a fresh agent-driven walkthrough for each relevant user path in addition to its automatic test: public actions and independent inspection of outputs, files or system state. A second invocation of the same test is not a manual check. Define expected observations and failure criteria; justify any case without a useful independent check.

Producing before/after images is a primary purpose of the walkthrough when visible output changes:

- Changed CLI tables/read-command output: mandatory before/after images.
- Changed logs, progress and final summaries: mandatory images of the affected states.
- Changed browser UI: actual before/after screenshots when supported by the available environment.
- Unchanged output/internal behavior: no decorative images.

Image requirements determine the minimum capture scope, not a whole-product E2E run. When capture is the only remaining gap, plan a focused CLI/UI walkthrough with only the resources needed to obtain genuine output. Reuse lower-level assertions rather than creating duplicate local test scripts; retain all required images and their observations.

Specify baseline/candidate revisions, equivalent fixtures, locale, width/output mode and reset between runs. Define which output/state each image must show and its artifact filename. Require real captures; unavailable baseline or capture is a concrete evidence gap, not permission to invent a comparison.

Select capture methods supported by the assigned environment. Renders of actual captured text must be labelled as renders, not screenshots of a terminal window. Redirection may alter TTY output; identify unsupported colors, interactive states or progress rather than claiming full visual coverage. Never invent a baseline or intermediate output.

Specify image/text filenames, scenario/revision labels, sanitization and publication requirements from the supplied delivery contract. Missing mandatory captures must prevent complete verification. Do not embed actual images, execution results, approval history or agent routing into a public planning artifact.

## 5. Plan extensions to existing CI tests

Read actual CI jobs, existing E2E tests and fixtures before assigning cases. Choose one disposition per case: extend existing CI E2E, already covered, local-only with reason, or lower-level check sufficient. Identify the existing test path/job, assertion, needed fixture and applicable command. CI feasibility cannot be inferred from a job name.

Prioritize public CLI/SDK/API paths reproducible with disposable CI data. Private-service credentials, personal identity or local services stay local unless CI already provides an appropriate safe fixture. Use the repository and artifact locations assigned by the task; CI tests, local scripts and evidence may share one repository or use separate destinations. Do not introduce undeclared private dependencies into CI.

Record required CI tests, fixtures and checks as explicit OpenSpec tasks with ownership supplied by the project's workflow. Keep CI implementation separate from local verification duties according to that contract; this skill assigns no named agent roles. No new CI framework by default. Keep automated, independent-agent and CI outcomes separate in the evidence contract.

## Completion

Persist a concise English technical plan: source mapping, scripts, manual steps, image requirements, artifacts, assertions, dependencies and cleanup. Keep discussion history, approvals, routing and review ledgers outside Git. Record concrete gaps before independent plan verification; do not label planned tests as passed or start the tester.
