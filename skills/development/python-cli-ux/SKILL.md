---
name: python-cli-ux
description: Audit or improve a Python command-line application for human usability, automation contracts, startup performance, distribution, and terminal feedback. Use for CLI UX reviews, CLI design, or focused CLI refactors; do not use for ordinary Python libraries without a command-line surface.
---

# Python CLI UX

Improve the existing CLI without assuming it needs a new framework.

## Audit before proposing changes

Inspect the installed command help, entry point, current framework and dependencies, representative human output, machine-readable output, exit codes, prompts, and startup imports. Trace the real command path before recommending a migration or dependency.

Check these contracts:

- installable console entry point and documented isolated installation;
- discoverable subcommands, useful help, consistent option names, typed validation, and safe defaults;
- explicit precedence when the same value can come from a flag, environment, config, or default;
- feedback for slow work: a transient status when total work is unknown, progress only when a real total exists;
- readable human output and a stable structured mode for pipes and agents;
- one machine document on stdout, diagnostics on stderr, meaningful exit codes, no ANSI or prompts in machine mode;
- an explicit non-interactive path for automation, especially for confirmation prompts;
- fast `--help` and `--version`, without loading operation-only dependencies;
- platform-correct config, data, state, and cache directories.

Separate confirmed gaps from ideas. Do not recommend work already provided by the current framework or codebase.

## Choose the smallest rung that fits

1. Keep the existing CLI framework when it already supports the required behavior.
2. Use `argparse` for a small, stable script with modest validation needs.
3. For a new or growing type-driven CLI, consider Typer; do not migrate a working Click or argparse CLI only for prettier syntax.
4. Use Rich directly for human tables, panels, status, and honest progress. Keep machine output independent of Rich.
5. Use Textual only when the product truly needs a persistent, keyboard-driven terminal application or live exploration. A loop plus Rich Live is usually enough for one updating view.

Prefer standard-library and framework features before another dependency. Avoid renderer DSLs, command buses, factories, and speculative configuration layers.

## Keep automation first-class

Treat the CLI as an API for shells, CI, and agents:

- preserve stable command names, option semantics, output schema, and exit codes;
- provide JSON when commands return structured results;
- make destructive automation explicit with flags such as `--yes` or `--no-input`;
- never force agents through a TUI or an interactive prompt;
- keep passthrough and streaming commands native when buffering them would break their contract.

## Make compact output recoverable

Apply only where output is demonstrably noisy; reuse existing verbosity and output options.

- Lead with the outcome and actionable failures. Collapse repetitive successes into counts, retaining useful IDs/locations and distinctions between failed, skipped, and no work found.
- Label omitted details and link to existing full-output artifacts. If details cannot be recovered without repeating a state-changing operation, leave them inline; do not add an output archive by default.
- Provide a full-output option for lossy summaries. Unknown output formats must retain original diagnostics and exit status, never become success or an empty result.

## Measure startup before optimizing

Measure the installed console script, not only a function call. Use `python -X importtime` to identify eager imports. First try callback-local imports, `TYPE_CHECKING`, or module-level `__getattr__` from PEP 562 while preserving public exports. Add a lazy-loading dependency only if those options are inadequate.

Do not claim an improvement from one noisy wall-clock sample. Retain one deterministic regression check for the expensive import boundary and report timings as supporting evidence.

## Deliver a focused result

Return:

- confirmed existing strengths;
- the smallest evidenced improvements, ordered by value;
- ideas deliberately skipped and the condition that would justify them;
- a minimal verification set covering help, validation, human output, machine output, non-interactive behavior, exit codes, and startup imports as applicable.

For changed output filters, use a small parametrized check covering success, failure, empty/unknown output, and retrieval of omitted details where applicable. Assert retained diagnostics and exit status, not just shorter text.

When implementing, change the fewest files that solve the root cause and leave one runnable check for non-trivial behavior.
