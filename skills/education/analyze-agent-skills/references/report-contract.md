# Report contract

Every report covers one skill and has exactly four primary sections.

## 1. Краткое summary

One dense paragraph containing trigger, decision procedure, cross-turn state, tools/permissions, observable outcome, safety boundary, and principal limitation. Do not repeat frontmatter.

## 2. Анатомия skill

Show a filesystem snapshot. Explain selection metadata, reasoning kernel, progressive disclosure, executable assets, platform assumptions, permissions, and supply-chain boundary.

## 3. Behavior contract

Model ordered phases from trigger through cleanup. For each phase identify precondition, action, observable evidence, failure behavior, and cleanup. Separate normative claims from tested behavior.

## 4. Scenario matrix

Cover happy paths, negative triggers, missing dependencies, malformed/adversarial input, permission denial, interruption, cleanup, concurrency/handoff where relevant, and conflicts with explicit user/project rules. Columns: scenario, expected action, observable outcome, evidence strength/gap.

End with pinned primary sources and static-analysis limitations. Never compare another skill inside the report.

