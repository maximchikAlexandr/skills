# Choosing and reindexing project categories

Read this reference before registering a project and when Vidra returns
`project_category_reindex_required`. A leaf may contain at most 15 projects.

## Place a new project

Inspect `vidra project category-tree` and relevant `vidra project list
--category CATEGORY --json` results, then choose in this order:

1. Use the most specific existing leaf that naturally describes the project's
   primary responsibility.
2. If none fits, inspect related leaves below the same parent with fewer than
   15 projects. A leaf may be renamed to a broader durable subject only when
   the new name stays within the parent's meaning and naturally describes every
   existing project plus the new one. Move the existing reports with `vidra
   project move`, then register the new project there.
3. Create a new leaf only when neither reuse nor safe broadening works.

Fewer directories is not sufficient justification. Reject vague buckets such
as `misc` or `other`, and do not group by owner, language, popularity, date,
report format, or a secondary implementation detail. Prefer the project's
maintainer-stated primary purpose. Ask the user only when two materially
different placements remain equally defensible.

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
