# Choosing and reindexing project categories

Read this reference before every project registration and when Vidra returns
`project_category_reindex_required`. A leaf may contain at most 15 projects.

## Place a new project

Inspect `vidra project category-tree` and the candidate leaf plus its relevant
siblings with `vidra project list --category CATEGORY --json`. This is a hard
pre-registration gate: do not derive a new path only from the new project's
wording. First establish whether an existing subject already covers its primary
responsibility, then choose in this order:

1. Use the most specific existing leaf that naturally describes the project's
   primary responsibility.
2. If none fits, inspect related leaves below the same parent with fewer than
   15 projects. A leaf may be renamed to a broader durable subject only when
   the new name stays within the parent's meaning and naturally describes every
   existing project plus the new one. Move the existing reports with `vidra
   project move`, then register the new project there.
3. Create a new leaf only when neither reuse nor safe broadening works. Before
   doing so, explicitly reject every related existing sibling on semantic
   grounds. A synonym, a narrower wording, or an extra qualifier such as
   `developer-`, `agent-`, or `tool-` does not justify a second leaf when the
   reports have the same primary responsibility.

Fewer directories is not sufficient justification. Reject vague buckets such
as `misc` or `other`, and do not group by owner, language, popularity, date,
report format, or a secondary implementation detail. Prefer the project's
maintainer-stated primary purpose. Ask the user only when two materially
different placements remain equally defensible.

## Merge semantic duplicate leaves

Placement and reindexing include consolidation, not only splitting. Treat
sibling leaves as merge candidates when their names are synonyms, one is merely
a narrower label for the other, or inspection shows that their reports share
the same primary responsibility.

Merge only when all of these hold:

1. One canonical, durable subject naturally describes every report in the
   candidate leaves. Prefer an existing broader name over inventing a new one.
2. The combined leaf will contain at most 15 projects.
3. The merge does not hide a meaningful difference in user intent or product
   responsibility. Shared language, owner, implementation, or report format is
   not enough.
4. Every report has been inspected from registry metadata, and ambiguous cases
   from the report itself.

Choose the canonical destination, assign every report exactly once, and move
each non-canonical report with `vidra project move REPORT_HASH CATEGORY`. Never
move files directly. If no existing name covers the union, a broader rename is
allowed only when it remains within the parent's meaning and accurately covers
all members. If two destinations remain materially plausible, ask the user.

Run this merge audit both before creating a new leaf and while handling a
reindex warning. A warning still requires splitting an overfull leaf, but the
audit may first remove neighboring semantic duplicates and produce a cleaner
taxonomy.

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
selection in React includes all descendant project categories. Also confirm
that no sibling leaves remain semantic duplicates and obsolete empty leaves no
longer appear in the category tree.
