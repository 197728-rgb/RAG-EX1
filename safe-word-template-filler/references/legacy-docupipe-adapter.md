# Legacy DocuPipe Adapter

DocuPipe is optional legacy infrastructure.

It is not part of the default workflow.

## When allowed

Use a DocuPipe adapter only when a project explicitly requires it.

## Rules

- Do not silently fall back from live mode to fixtures.
- Missing credentials must fail immediately.
- Raw DocuPipe JSON must be retained.
- Metadata JSON must be retained.
- Output must be normalized into flat `evidence.json`.
- Conflicts must be reviewed.
- Low-confidence values must be reviewed.
- The exact approval map is still required.
- The raw OOXML patcher is still required.
- `structure_guard_report.json` must still pass.

## Forbidden

Do not:

- make DocuPipe mandatory
- describe DocuPipe as the primary workflow
- use fixture data in live mode
- bypass RAG selection reports
- bypass approval maps
- bypass the patcher
- bypass structure guard review
