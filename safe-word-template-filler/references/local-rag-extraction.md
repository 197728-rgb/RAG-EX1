# Local RAG Extraction

This reference describes the preferred replacement for DocuPipe.

The default extraction path is:

    local OCR / PDF text extraction
    + local RAG retrieval
    + schema-guided extraction
    + review checks
    + normalized evidence.json

## Why RAG alone is not enough

RAG retrieves text. It does not reliably read scanned images by itself.

For scanned PDFs, the runner must first perform OCR or another local extraction step.

## Safety boundary

RAG may locate evidence.

RAG may extract values.

RAG may select the exact approval map.

RAG must not authorize DOCX write locations.

Only `approval_map.json` authorizes write locations.
