---
name: python-cli-ux
description: Audit or improve a Python command-line application for human usability, automation contracts, startup performance, distribution, and terminal feedback. Use for CLI UX reviews, CLI design, or focused CLI refactors; do not use for ordinary Python libraries without a command-line surface.
---

# Python CLI UX

Improve the existing CLI without assuming it needs a new framework.

## Audit the installed interface first

Trace the installed console entry point and real command path before proposing a
migration, dependency, or abstraction. Inspect root and representative command
help, the current framework and dependencies, human and structured output,
stdin/stdout/stderr, prompts, exit codes, signals, configuration sources, and
startup imports. Separate confirmed gaps from ideas, and do not recommend work
already provided by the framework or codebase.

Inventory every public leaf command before changing shared behavior. Record:

| Contract | Questions |
| --- | --- |
| Side effects | Is it read-only, mutating, spawning, or destructive? |
| Input | Arguments, flags, stdin, config, environment, prompts, passthrough? |
| Output | Bounded document, event stream, live terminal view, or native passthrough? |
| Automation | Structured mode, non-interactive path, stable schema, recoverability? |
| Process | Exit meanings, child exit propagation, signals, cancellation, retries? |

Use the inventory to find inconsistent siblings and determine which detailed
contracts apply. Read only the matching sections of
[references/cli-contracts.md](references/cli-contracts.md):

- **Interface design:** command grammar, help, framework choice, and startup.
- **Output and automation:** TTY behavior, JSON or JSON Lines, exit semantics,
  passthrough, and compact output.
- **Operations:** mutation safety, configuration and secrets, diagnostics,
  retries, cancellation, and resume.

Whenever public behavior is changed or implemented, also read **Compatibility and
deprecation** and **Public contract verification**. These cross-cutting sections
apply in addition to the matching domain sections.

## Choose the smallest implementation rung that fits

1. Keep the existing CLI framework when it already supports the required behavior.
2. Use `argparse` for a small, stable script with modest validation needs.
3. For a new or growing type-driven CLI, consider Typer; do not migrate a working
   Click or argparse CLI only for prettier syntax.
4. Use Rich directly for human tables, panels, status, and honest progress. Keep
   machine output independent of Rich.
5. Use Textual only when the product truly needs a persistent, keyboard-driven
   terminal application or live exploration. A loop plus Rich Live is usually
   enough for one updating view.

Prefer standard-library and framework features before another dependency. Avoid
renderer DSLs, command buses, factories, and speculative configuration layers.

## Deliver a focused result

Return:

- confirmed existing strengths;
- the smallest evidenced improvements, ordered by value;
- the resulting command, output, safety, and compatibility contracts;
- ideas deliberately skipped and the condition that would justify them;
- the minimal verification set that proves the changed behavior.

When implementing, change the fewest files that solve the root cause and leave one
runnable check for every non-trivial public behavior changed.
