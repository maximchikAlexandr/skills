# Calibration and agent timing

Use supplied or already available local timing records. This skill does not collect
telemetry, instrument the project, run experiments, or write calibration history.

## Comparable evidence

For each usable record identify the executor, task class, accepted scope, estimate,
actual duration, timing definition, environment, and completion outcome. Prefer
similar Python work in the same repository with the same definition of done.

Do not mix active human effort, end-to-end agent run time, calendar lead time,
or token cost. Commit timestamps and closed issue dates do not measure effort.
Treat a failed/abandoned run as outcome evidence, not a successful completion time;
include observed retries and repairs when estimating time to an accepted result.

Distinguish CRUD/validation, migrations, external integrations, async/process work,
and difficult debugging when they exhibit different runtime behavior. Do not
invent a minimum dataset or claim validated probabilities from a few examples.

## Apply a correction once

With genuinely comparable paired records, a simple correction is:

`r_i = actual_i / original_estimate_i`

`k = median(r_i)`

Exclude zero denominators; use the same estimate field (for example, weighted E)
and the same units consistently. Explain exclusions rather than dropping slow runs
to improve apparent accuracy. Report sample count, record references, and the
observed spread. A small sample supports a provisional correction, not a guarantee.

Apply k once to comparable raw O/M/P estimates, then recompute E. Do not apply it
again to a total or to estimates already anchored directly in those actuals. Keep
unrelated work separate. If scope or tooling changed substantially, use the records
as qualitative analogues instead of blindly transferring the coefficient.

Do not convert human-hours to agent-hours with this correction. That conversion
would require paired comparable observations for the two executors, not merely a
human actual/estimate ratio. Do not pool model versions or harness settings without
examining whether the old observations still apply.

## Estimate one Codex run

Anchor elapsed working time in comparable accepted runs, when available. Count
repository/context exploration, implementation cycles, tool execution, test/build
waits on the critical sequence, and repair/review iterations needed for acceptance.
Do not derive agent speed from how quickly it emits code or its token throughput.

If historical tool cycles and measured durations are supplied, they may support a
breakdown. State the cycle definition and observed timing range; do not impose an
arbitrary fixed number of minutes per tool call. Avoid counting the same verification
time both inside a cycle and in a separate testing row.

Without such evidence, return an explicitly uncalibrated working-time estimate,
using the concrete work and environment as justification. Name the unknowns that
dominate the range. Keep required human review effort and external waiting visible
as separate measures; do not add them to the agent-only headline.
