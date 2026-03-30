# web-FileCheck

`web-FileCheck` is a fresh rewrite of the BOM comparison tool into a multi-format file comparison web app.

## v1 scope

- Compare two files at a time
- Support planned formats: `xls`, `xlsx`, `txt`, `md`, `pdf`, `docx`
- Split comparison into:
  - `spreadsheet` mode for table-like files
  - `document` mode for text-like files
- Store uploads, results, and reports in dedicated directories
- Target deployment: `10.10.10.30:4000`

## Current status

This build now provides:

- A lightweight Node.js web server
- Static frontend upload page
- API endpoints for health, capabilities, comparison planning, and file comparison
- Real multipart upload handling
- Stored upload files and stored comparison result JSON
- Working document comparison for `txt` and `md`
- Working spreadsheet comparison for `xls` and `xlsx`
- Deployment notes and storage layout

Still planned next:

- `docx`
- `pdf`

## Local run

```bash
cp .env.example .env
node src/server.js
```

Open `http://localhost:4000`.

## API

- `GET /api/health`
- `GET /api/capabilities`
- `POST /api/compare-plan`
- `POST /api/compare`
- `GET /api/compare/:id`

## Storage

For deployment on `10.10.10.30`, the intended production directories are:

- `/data/web-FileCheck/uploads`
- `/data/web-FileCheck/results`
- `/data/web-FileCheck/reports`

During local development, the scaffold uses `./storage/*`.
