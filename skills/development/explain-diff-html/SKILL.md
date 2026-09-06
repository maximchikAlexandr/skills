---
name: explain-diff-html
description: Create a deep, interactive HTML explanation of a code change, commit, branch, or PR.
---

# Explain Diff

Create one self-contained HTML page that teaches the specified change.

## Required structure

- **Background:** explore the surrounding system broadly, then narrow to the
  problem the change solves. Make the broad introduction explicitly skippable.
- **Intuition:** explain the mechanism with at least two concrete scenarios and
  representative data. Prefer examples that exercise different outcomes.
- **Code:** walk through causal chains across symbols and modules rather than
  restating the file list. Cover important invariants, failure paths, edge
  cases, trade-offs, and deliberate non-goals.
- **Quiz:** five medium-difficulty multiple-choice questions. A correct answer
  must require understanding behavior, not remembering a filename. Clicking an
  answer reveals whether it is correct and explains why.

Add a table of contents and responsive phone-friendly styling. Put the report
outside the repository and prefix its filename with the current YYYY-MM-DD date.

## Depth gate

Before writing, inspect the parent state, the diff, relevant callers and
callees, data types, and tests. Trace each major claim to concrete symbols or
tests. A report is not ready if it could have been produced from the commit
message and changed-file list alone.

Use code excerpts only when they clarify a mechanism. All code blocks use
HTML pre elements and CSS with white-space set to pre or pre-wrap.

## Visual explanation

Use the diagram-design skill with its standard style. Choose diagrams for the
behavior being taught, not decoration. Include at least two complementary
views when the change has enough structure, commonly:

- a data-flow or architecture view for ownership and boundaries;
- a sequence, state, or decision view for success and failure behavior.

Keep diagrams small enough to read without a legend hunt. Do not use ASCII
diagrams.

## Quality bar

Write in clear classic prose with smooth transitions. Include realistic
examples, explain why the design exists, and distinguish facts from inference.
Call out security or compatibility consequences only when supported by the
change. Verify the HTML, diagrams, quiz behavior, revision identifier, and
source facts before delivering it.

The output is one UTF-8 HTML file with inline CSS and any required JavaScript.
Do not add analytics, tracking, remote images, or secrets.
