# Reindexing an overcrowded report category

Read this reference when Vidra returns `category_reindex_required`. The warning
appears as soon as a directory reaches 10 reports, before the library becomes
hard to scan.

## Decide the split from evidence

1. Run `vidra report list --category CATEGORY --json` and inspect every report
   title, concept, source list, and hash in that directory.
2. Propose two to five sibling subtopics that describe the reports already
   present. Prefer stable subject areas (`ai/code-review`, `ai/harness`,
   `ai/llm`) over speakers, dates, formats, or one-off labels.
3. Every report must have exactly one destination. Do not create a subdirectory
   for a single report unless it is clearly the beginning of a durable topic.
4. Show the proposed mapping to the user when the taxonomy is ambiguous or
   would materially change navigation.

## Apply and verify

Move each report with `vidra report move REPORT_HASH NEW/CATEGORY`. This moves
the real HTML file and updates all SQLite records for every video covered by
that report. Never use raw `mv`: it leaves the registry pointing at the old
path.

Then run:

```text
vidra category tree
vidra doctor
```

Confirm that no leaf directory has more than 10 reports and that each report
opens from the web library. Keep useful parent directories: selecting a parent
in the React interface includes all descendant reports.
