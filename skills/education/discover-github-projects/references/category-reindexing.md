# Reindexing an overcrowded project category

Read this reference when Vidra returns `project_category_reindex_required`.
The warning is emitted when a leaf directory contains more than 15 project
reports; it is a taxonomy maintenance signal, not a failed registration.

## Decide the split from evidence

1. Run `vidra project list --category CATEGORY --json` and inspect every
   repository, title, summary, revision, and report hash in the leaf.
2. Read reports when titles and summaries are insufficient to distinguish each
   project's primary responsibility.
3. Propose two to five durable child subjects. Classify by what the software
   primarily does (`ai/code-review`, `ai/agents`, `developer-tools/voice`), not
   by owner, programming language, popularity, date, or report format.
4. Give every report exactly one destination. Avoid a one-project directory
   unless it is a credible seed of a durable subject.
5. Ask the user only when two classifications remain materially plausible.

## Apply and verify

Move each report with:

```text
vidra project move REPORT_HASH NEW/CATEGORY
```

This moves the real HTML report and cached repository preview together, updates
SQLite, and repairs the relative `Все проекты` link. Never use raw `mv`, because
the catalog would retain stale paths.

Then run:

```text
vidra project category-tree
vidra doctor
```

Confirm that every leaf contains at most 15 projects, every card image loads,
every report opens, and its back button returns to the project catalog. Parent
selection in React includes all descendant project categories.
