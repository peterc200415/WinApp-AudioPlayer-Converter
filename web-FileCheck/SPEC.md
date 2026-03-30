# web-FileCheck v1 Specification

## Product goal

Provide a simple browser-based tool that accepts two files, normalizes their content, and highlights meaningful differences across structured and document-oriented formats.

## Deployment target

- Host: `10.10.10.30`
- Port: `4000`
- Process model: single Node.js service in v1

## Planned format support

### Phase 1

- `xls`
- `xlsx`
- `txt`
- `md`

### Phase 2

- `docx`
- text-based `pdf`

### Later

- scanned `pdf` with OCR
- legacy `.doc`

## Comparison modes

### Spreadsheet mode

Use row and column semantics for:

- BOM-like spreadsheets
- flat comparison tables
- future CSV and TSV if needed

Key outputs:

- total rows
- added rows
- removed rows
- changed rows
- duplicate keys
- missing keys

### Document mode

Use section, paragraph, and table semantics for:

- text files
- markdown files
- Word documents
- PDF text extracts

Key outputs:

- extracted sections
- paragraph-level additions and removals
- changed blocks
- parser warnings

## Storage plan

- uploads: original files
- parsed: normalized JSON representations
- results: comparison summaries and details
- reports: exported PDF/JSON reports

Recommended production layout:

- `/data/web-FileCheck/uploads`
- `/data/web-FileCheck/parsed`
- `/data/web-FileCheck/results`
- `/data/web-FileCheck/reports`

## Implementation roadmap

1. Build upload endpoint and storage manager
2. Implement format detection and parser registry
3. Add `txt/md/xls/xlsx` parsers
4. Add spreadsheet and document comparison engines
5. Add `docx/pdf` parsers
6. Add report export and persistent history
