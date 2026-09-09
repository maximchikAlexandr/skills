+# Vidra category placement contract

Apply this contract before every registration and during taxonomy reindexing. A
leaf may contain at most 15 catalog records.

## Pre-registration gate

Inspect `vidra project category-tree`, then inspect the candidate leaf and its
relevant siblings with `vidra project list --category CATEGORY --json`. Do not
derive a new path only from the new report's wording.

Choose in this order:

1. Reuse the most specific existing leaf that naturally describes the report's
   primary responsibility.
2. If none fits, safely broaden a related non-full leaf only when the new name
   stays within the parent's meaning and accurately describes every member.
3. Create a new leaf only when neither reuse nor safe broadening works. First
   reject every related sibling on semantic grounds.

A synonym, narrower wording, or cosmetic qualifier such as `developer-`,
`agent-`, or `tool-` is not a distinct subject. Do not classify by owner,
language, popularity, date, source type, or report format. Ask the user only
when two materially different placements remain equally defensible.

## Merge semantic duplicates

Treat sibling leaves as merge candidates when their names are synonyms, one is
merely narrower than another, or their records share the same primary
responsibility. Merge only when:

- one canonical durable subject accurately covers every record;
- the combined leaf stays within the 15-record limit;
- the merge preserves meaningful differences in user intent and responsibility;
- every record was inspected from registry metadata, with ambiguous cases read
  from the report itself.

Prefer an existing broader destination. Assign every record exactly once and
move it only with `vidra project move REPORT_HASH CATEGORY`; never move catalog
files directly. If no existing name covers the union, broaden a name only under
the same parent and only when it remains accurate for all members.

## Verify

After placement or merging, run:

```text
vidra project category-tree
vidra doctor
```

Confirm every leaf is within the limit, no sibling leaves remain semantic
duplicates, obsolete empty leaves are absent, and catalog records and reports
still resolve.

