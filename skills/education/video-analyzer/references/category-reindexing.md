# Choosing and reindexing video report categories

Read this reference before registering a report and when Vidra returns
`category_reindex_required`. A leaf may contain at most 10 reports.

## Place a new report

Inspect `vidra category tree` and relevant `vidra report list --category
CATEGORY --json` results, then choose in this order:

1. Put the report in the most specific existing leaf where its primary subject
   naturally belongs.
2. Otherwise inspect related leaves below the same parent that contain fewer
   than 10 reports. If one can be renamed to a broader durable subject without
   leaving that parent, and every existing report plus the new report remains a
   natural member, move those reports to the broader name and use it.
3. Otherwise create one new leaf for the report.

Do not broaden a category merely to save a directory. The new name must express
one useful subject shared by every member; `misc`, `other`, formats, speakers,
dates, and accidental technology overlap are not subjects. Never move a report
outside the meaning of its parent. When more than one placement remains
plausible, choose by the report's primary viewer outcome; ask the user only if
that still leaves a material ambiguity.

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
