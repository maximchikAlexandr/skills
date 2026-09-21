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

Use the inventory to find inconsistent siblings and to keep a new command from
escaping output, safety, or verification policy.

## Design a predictable command surface

- Use subcommands for distinct operations and group them by user domain, not by
  internal module. A bare multi-command root should normally show concise help;
  enter a REPL or perform work only when that is the product's deliberate,
  documented primary action.
- Reserve positional arguments for one obvious kind of value. When two values
  have different roles, prefer explicit flags such as `--from` and `--to`.
- Put options before arguments in documented automation examples. Support `--`
  when user input or child-process arguments could otherwise be parsed as CLI
  options. Do not rely on abbreviated long options in scripts.
- Prefer consistent positive and negative pairs such as `--color`/`--no-color`
  when users need to override a default or configuration value.
- Provide `-h`/`--help`, command-specific help, and `--version`. Help should state
  arguments, flags, defaults or configuration sources when relevant, and a few
  realistic examples. Offer shell completion when the framework can generate it
  without bespoke completion infrastructure.
- Treat help text and command names as public behavior. Snapshot or otherwise
  characterize them when accidental surface changes are likely.

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

## Treat terminal and redirected output as different interfaces

Decide behavior from stdin, stdout, and stderr independently; one stream being a
TTY does not imply the others are. Check interactive TTY, redirected output, and
CI behavior.

- Send primary results to stdout and diagnostics, warnings, and progress to
  stderr. Never hide child-process stderr unless the command explicitly captures
  it and provides an equally useful diagnostic.
- Enable color, Unicode decoration, live rendering, spinners, and pagers only
  when the relevant stream supports them. Respect `NO_COLOR`, `TERM=dumb`, the
  CLI's `--no-color` override, terminal width, and a plain-text fallback.
- Use a pager only for interactive output, never for pipes or machine formats,
  and provide a direct opt-out.
- Show transient status when total work is unknown and progress only when a real
  total exists. Avoid rendering terminal control sequences into files or logs.
- Keep default tables narrow and useful. Provide deliberate field selection,
  sorting, or full-detail options only when real use cases require them.

## Make automation a versioned API

Preserve stable command names, option semantics, output schemas, and exit meanings.
Human presentation may evolve; machine contracts must not change accidentally.

- A bounded structured command emits exactly one JSON document on stdout.
- A streaming structured command emits one JSON object per line. Give each event
  a `type`; include a schema version in the stream's first event or every record.
- Use a major/minor schema policy: additive minor changes require readers to
  ignore unknown fields; incompatible changes require a new major version.
- Keep diagnostics on stderr and exclude ANSI, prompts, progress, and incidental
  logs from machine stdout. Never force automation through a TUI or REPL.
- Do not pretend native passthrough is structured. Preserve the child's streams,
  exit status, and signal semantics when buffering or projection would break the
  command's contract.

Define exit semantics per command family rather than imposing one universal table.
Zero means success; distinguish usage errors, operation failures, intentional
negative results such as "no match" or "changes present," and interruption where
the domain benefits from that distinction. Keep codes stable and document them.
Preserve child signal exits for passthrough commands and handle Ctrl-C consistently.
Machine error documents should carry a stable error code aligned with the process
outcome.

## Make state changes inspectable and safe

- Give expensive, destructive, or difficult-to-reverse operations a meaningful
  `plan`, `preview`, or `--dry-run` path where the system can actually predict the
  action. Do not add a ceremonial dry-run that omits decisive work.
- If execution must match reviewed state, save or identify the plan and validate
  it again before apply. Otherwise prefer the simpler preview-then-execute flow.
- Prompt only on an interactive stdin. Require an explicit `--yes`, `--no-input`,
  or equivalent path for automation, and fail rather than hang when required
  input is missing.
- For high-risk deletion, consider confirming the target identity rather than a
  generic yes/no. Keep safe retries idempotent and use locking or conflict checks
  when concurrent mutation can corrupt state.
- Provide cheap `info`, `status`, `list`, or `doctor` inspection where a user or
  agent needs current state before mutating it.

## Make configuration explainable and secrets safe

Document the actual precedence when a value can come from a flag, environment,
project or user config, and a default. Command-line values should normally win.
For non-trivial configuration, provide a way to show the effective value and its
source, plus an escape hatch such as `--no-config` for reproducible runs.

Use platform-correct config, data, state, and cache directories. Do not put secrets
in argv, normal output, debug logs, or generated support bundles by default; argv
can be stored in shell history and exposed to other processes. Prefer stdin,
protected files, environment variables when appropriate, or an OS credential
store. Redact sensitive values and check permissions on credential-bearing files.

## Make failures actionable and diagnosable

Human-facing errors should identify what failed, retain the relevant target or
context, and state the next safe action. Add a documentation link only when it is
more useful than an inline remedy. Machine errors should use a stable code,
message, and bounded secret-free details.

Hide tracebacks for expected user errors, but offer an opt-in `--debug`, verbose
version information, `doctor`, or redacted support bundle when maintainers need
deeper evidence. Preserve timestamps in retained logs, avoid ANSI in them, and
define retention instead of letting debug artifacts grow forever.

## Make compact output recoverable

Apply compaction only where output is demonstrably noisy; reuse existing verbosity
and output options.

- Lead with the outcome and actionable failures. Group or deduplicate repetitive
  successes while retaining useful IDs, locations, counts, and the distinction
  between failed, skipped, partial success, and no work found.
- Label every omission and provide a raw/full-output path. Store full output only
  when the product has an explicit retention, privacy, and cleanup policy; if
  details cannot be recovered without repeating a state-changing operation, keep
  them inline.
- If parsing or filtering fails, fall back to raw passthrough with a diagnostic.
  Unknown formats must retain original diagnostics and exit status, never become
  success or an empty result.
- Verify semantic fidelity, not only shorter output: failures, exit status,
  signals, identifiers, and the recovery path must survive filtering.

## Design long-running operations for interruption

Use explicit timeouts and bounded retries only for failures known to be transient.
Choose retry and backoff policy by operation class rather than one global number.
Do not automatically retry a non-idempotent mutation unless an idempotency key,
checkpoint, or state check makes repetition safe.

On cancellation, stop or hand off child processes deliberately, restore terminal
state, clean up incomplete temporary artifacts, and retain any recovery identifier.
Report partial success explicitly. Add resume or checkpoint behavior only when the
operation is expensive enough and the underlying work can resume correctly.

## Preserve compatibility deliberately

Treat command names, flags, defaults, configuration precedence, schemas, and exit
semantics as compatibility surfaces. For intentional changes:

- prefer a temporary alias or compatibility mode when users plausibly automate
  the old form;
- write deprecation warnings to stderr with the replacement and removal condition;
- never silently reinterpret an existing flag;
- keep characterization tests for the supported old and new forms until removal;
- record breaking machine-contract changes in release notes and bump the relevant
  schema major version.

Do not carry compatibility code for a private or unused interface without evidence
that something depends on it.

## Measure startup before optimizing

Measure the installed console script, not only a function call. Include cold and
warm samples and define a project-specific budget for `--help` and `--version`
instead of treating one universal timing threshold as truth. Use
`python -X importtime` to identify eager imports.

First try callback-local imports, `TYPE_CHECKING`, or module-level `__getattr__`
from PEP 562 while preserving public exports. Add a lazy-loading dependency only
if those options are inadequate. Retain one deterministic regression check for
the expensive import boundary; timings are supporting evidence, not a stable unit
test on shared CI hardware.

## Verify the public contract

Run the installed executable in subprocess tests rather than testing only callback
functions. Select the applicable rows from this matrix:

- root and subcommand help, bare invocation, version, examples, and completion;
- valid input, invalid input, `--`, config precedence, `--no-config`, and redaction;
- interactive prompts through a PTY and non-interactive missing-input failure;
- TTY, redirected stdout/stderr, narrow terminal, `NO_COLOR`, and plain output;
- bounded JSON and streaming JSON Lines schema, stdout/stderr separation, and no
  ANSI or prompts in machine mode;
- documented success, negative-result, usage, failure, partial-success, child,
  SIGINT, and cancellation exit behavior;
- dry-run/plan parity, destructive confirmation, idempotent repeat, and concurrent
  mutation protection where applicable;
- passthrough fidelity and compact-output success, failure, empty, unknown-format,
  and full-output recovery cases;
- installed packaging from outside the repository, plus supported operating systems
  when path, quoting, signal, or terminal behavior differs.

Prefer a small parameterized contract suite and a few realistic end-to-end workflows
over one test per sentence. Verify produced files or external effects, not merely a
zero exit code.

## Deliver a focused result

Return:

- confirmed existing strengths;
- the smallest evidenced improvements, ordered by value;
- the resulting command, output, safety, and compatibility contracts;
- ideas deliberately skipped and the condition that would justify them;
- the minimal verification set that proves the changed behavior.

When implementing, change the fewest files that solve the root cause and leave one
runnable check for every non-trivial public behavior changed.
