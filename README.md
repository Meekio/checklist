# Engineering Drawing QC

AI-powered quality control for engineering drawings using Google Vertex AI (Gemini). Upload a PDF drawing and an Excel rules file — the system evaluates each rule against the drawing and returns a pass/fail report.

## How it works

`std.py` is the core logic:

1. Renders every page of the PDF at 300 DPI using PyMuPDF
2. Loads QC rules from an Excel file (looks for a `QC Point` column, falls back gracefully)
3. Splits rules into batches of 20 and sends each batch to Gemini along with all rendered pages
4. Parses the JSON response and maps results back to the original rows
5. Outputs an Excel file with two new columns — `Status` (Correct / Incorrect / Error) and `Remarks`

Batching keeps API calls low — 100 rules = 5 Gemini calls instead of 100.

## Stack

- Python / FastAPI — backend API
- React + Vite — frontend UI
- Google Vertex AI (gemini-2.5-flash) — drawing evaluation
- PyMuPDF — PDF rendering
- pandas / openpyxl — Excel I/O

## Running locally

**Prerequisites:** Python 3.8+, Node.js 16+, a Google Cloud project with Vertex AI enabled.

```bash
# Authenticate with Google Cloud
gcloud auth application-default login
```

**Backend**
```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload
# runs on http://localhost:8000
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
# runs on http://localhost:5173
```

## Configuration

All tuneable values are at the top of `std.py`:

```python
PROJECT_ID  = "your-gcp-project-id"
LOCATION    = "us-central1"
GEMINI_MODEL = "gemini-2.5-flash"
BATCH_SIZE  = 20
```
