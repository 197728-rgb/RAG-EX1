---
name: safe-word-template-filler
description: Safely fills approved value cells in structured Word templates using local RAG evidence extraction and raw OOXML patching.
---

# Purpose

Use this skill to safely fill structured `.docx` Word templates from scanned evidence PDFs or extracted evidence data.

The skill has two layers:

1. Local RAG extraction layer
   - Converts PDFs to text or Markdown.
   - Retrieves evidence locally.
   - Extracts structured field values.
   - Produces review reports.
   - Produces flat `evidence.json`.

2. Safe DOCX patching layer
   - Uses an exact per-form/version approval map.
   - Verifies form markers.
   - Resolves merged-cell visual table positions.
   - Patches only approved OOXML text locations.
   - Produces fill and structure guard reports.

DocuPipe is not part of the default workflow. Use local extraction first.

# When to use

Use this skill when:

- Evidence arrives as scanned PDFs, text PDFs, or already-extracted JSON.
- The target output is a structured Word `.docx` form.
- The Word form contains complex tables, merged cells, repeated labels, or fragile formatting.
- Only explicitly approved value cells may be written.
- The approval map is exact for the form and version.
- A reviewable audit trail is required.

Do not use this skill when:

- The Word document can be freely rewritten.
- No exact per-form/version approval map exists.
- The user wants layout redesign, table edits, row creation, or section editing.
- The task is only general document editing.
- The runner cannot produce or verify `structure_guard_report.json`.

# Default pipeline

The default pipeline is local-first:

    inbox/*.pdf
    -> local OCR or PDF text extraction
    -> Markdown/text with source page metadata
    -> parent/child chunk indexing
    -> local RAG retrieval
    -> schema-guided evidence extraction
    -> conflict/missing/low-confidence review
    -> flat evidence.json
    -> exact approval_map.json
    -> rag_selection_report.json
    -> raw OOXML patcher
    -> filled.docx
    -> fill_report.json
    -> fill_report.csv
    -> label_debug_dump.json
    -> structure_guard_report.json
    -> review JSON
    -> review Markdown
    -> run_manifest.json

# Local RAG extraction layer

The runner/orchestrator should use local RAG before invoking the patcher.

Recommended local components:

- OCR or PDF text extraction:
  - Tesseract
  - OCRmyPDF
  - PyMuPDF
  - pymupdf4llm
  - another project-approved local extractor

- Local model runner:
  - Ollama
  - LM Studio
  - LocalAI
  - GPT4All

- RAG framework:
  - LangGraph
  - LlamaIndex
  - Haystack
  - AnythingLLM
  - PrivateGPT

- Vector database:
  - Qdrant
  - Chroma
  - FAISS
  - PGVector

# RAG responsibilities

RAG may:

- Find relevant evidence in local PDFs or text.
- Retrieve source passages.
- Identify source PDF names and page numbers.
- Extract candidate values for mapped fields.
- Detect missing values.
- Detect conflicting values.
- Detect low-confidence values.
- Help select the exact form/version approval map from project references.
- Create `rag_selection_report.json`.

RAG must not:

- Invent field values.
- Invent writable DOCX cells.
- Guess `row_offset` or `col_offset`.
- Guess repeated-label occurrence numbers.
- Enable fuzzy matching unless the approval map explicitly enables it.
- Enable `create_text_node` unless the approval map explicitly enables it.
- Use a generic, similar, nearest, or latest approval map.
- Bypass the raw OOXML patcher.
- Bypass `structure_guard_report.json`.

# Recommended RAG workflow

1. Convert each input PDF to text or Markdown.
2. Preserve source metadata:
   - source PDF filename
   - page number
   - extraction method
   - OCR confidence when available
3. Split text into parent and child chunks.
4. Index child chunks in a local vector database.
5. Store parent chunks for retrieval.
6. For each expected evidence field:
   - search child chunks
   - retrieve parent chunks
   - extract candidate value
   - cite source file and page
   - assign confidence
7. Normalize values into flat `evidence.json`.
8. Write detailed review metadata separately.
9. Detect conflicts, missing fields, and low-confidence values.
10. Select the exact per-form/version approval map.
11. Create `rag_selection_report.json`.
12. Invoke the patcher only after review checks are complete.

# Evidence output contract

The patcher accepts a flat JSON object only.

Example `evidence.json`:

    {
      "client_name": "Example Corp",
      "inspection_date": "2026-05-07",
      "observed_voltage": "230 V",
      "status": "Approved"
    }

Do not pass nested review metadata to the patcher.

Keep richer evidence review data in a separate review file.

# Approval map contract

The approval map must be exact for the current form and version.

It must include:

- `form_id`
- `form_version`
- `form_markers`
- `fields`

# Final handoff rule

Do not hand over `filled.docx` unless all are true:

- local OCR/text extraction completed or valid flat evidence was provided
- review JSON was written
- review Markdown was written
- run manifest was written
- exact per-form/version approval map was selected
- `rag_selection_report.json` exists
- no unreviewed conflicts exist
- no unreviewed low-confidence values exist
- no patcher conflicts exist
- no patcher errors exist
- `structure_guard_report.json` has `"pass": true`

# Legacy DocuPipe adapter

DocuPipe is not part of the default workflow.

A project may provide a legacy DocuPipe adapter only when explicitly required.
