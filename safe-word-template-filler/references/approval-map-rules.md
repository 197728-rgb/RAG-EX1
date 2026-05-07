# Approval Map Rules

Approval maps are the safety boundary for DOCX writing.

## Required fields

Each approval map must include:

- `form_id`
- `form_version`
- `form_markers`
- `fields`

## Repeated labels

Repeated labels must use explicit `occurrence`.

Do not guess occurrence numbers.

## Fuzzy matching

Fuzzy matching is off by default.

Only enable it when the exact form/version approval map explicitly enables it.
