# Engineering Drawing QC

AI-powered quality control for engineering drawings using Google Gemini. Upload a drawing PDF and a rules Excel — the system checks every rule against the drawing and produces a pass/fail Excel report.

---

## What you need before running

- Python 3.10 or higher
- Node.js 16 or higher
- A Google Gemini API key — get one free at [Google AI Studio](https://aistudio.google.com/app/apikey)

---

## One-time setup

### 1. Add your API key

Create a file named `.env` in the project root folder (`D:\qc_checklist\.env`) with the following content:

```
GEMINI_API_KEY=your_api_key_here
```

Replace `your_api_key_here` with your actual key.

### 2. Install Python dependencies

Open a terminal in the project root and run:

```bash
pip install -r requirements.txt
```

### 3. Install frontend dependencies

```bash
cd frontend
npm install
```

---

## How to run

You can use the tool either through the web UI or directly from the terminal.

### Option A — Web UI (recommended)

**Step 1: Start the backend**

Open a terminal in the project root and run:

```bash
uvicorn backend.main:app --reload --port 8001
```

Keep this terminal open.

**Step 2: Start the frontend**

Open a second terminal, navigate to the frontend folder, and run:

```bash
cd frontend
npm run dev
```

**Step 3: Open the app**

Go to `http://localhost:5173` in your browser.

---

### Option B — Terminal (no UI)

```bash
python checklist_main.py
```

You will be prompted to enter:
1. Full path to the engineering drawing PDF
2. Full path to the drawing-specific rules Excel file

Example:
```
Enter drawing PDF path: D:\qc_checklist\image1\LT0825003C_BALL.pdf
Enter drawing-specific rules Excel path: D:\qc_checklist\image1\Engineering_Drawing_QC_Checklist.xlsx
```

---

## What to upload

| Input | Format | Description |
|---|---|---|
| Engineering Drawing | `.pdf` | The drawing to be checked. Multi-page PDFs are supported. |
| Drawing-Specific Rules | `.xlsx` or `.xls` | Rules specific to this drawing. Must have a column named `QC Point` (or similar — see note below). |

> **Note on the rules Excel column name:** The system looks for a column named `QC Point`. If your file uses a different name like `Rule`, `Check`, `Criteria`, etc., it will still be detected automatically. Renaming the column to `QC Point` avoids any ambiguity.

**You do not need to upload the common Y14.5 rules.** The file `files/Y14.5_4.1_Fundamental_Rules_Conditional_Checklist.xlsx` is always loaded automatically.

---

## What output to expect

The output is a single Excel file saved to the `output/` folder:

```
output/qc_results_YYYYMMDD_HHMMSS.xlsx
```

The file has three columns:

| Column | Description |
|---|---|
| Rule | The rule text that was evaluated |
| Status | `Correct` or `Incorrect` |
| Remarks | Short explanation from Gemini |

The file is split into two sections with a styled header row separating them:

```
--- Common Rules ---          ← Y14.5 rules, always checked
  rule 1 ...
  rule 2 ...
--- Drawing-Specific Rules --- ← rules from your uploaded Excel
  rule 1 ...
  rule 2 ...
```

Section headers are bold, font size 15, with a blue background so they are easy to spot.

When using the web UI, a **Download Report** button appears once the check is complete.

---

## How long does it take?

- Each page of the PDF is rendered at 300 DPI and sent to Gemini along with every batch of rules.
- Rules are processed in batches of 20 with a 2-second pause between calls to avoid overloading the API.
- As a rough guide: 100 rules across a 2-page drawing takes around 2–3 minutes.

---

## Project structure

```
checklist_main.py     ← main QC logic (entry point for terminal use)
backend/
  main.py             ← FastAPI backend (serves the web UI)
frontend/             ← React + Vite web UI
files/
  Y14.5_4.1_Fundamental_Rules_Conditional_Checklist.xlsx  ← common rules (do not move or rename)
output/               ← generated QC reports land here
.env                  ← your API key goes here (never commit this file)
requirements.txt      ← Python dependencies
```

---

## Common issues

**`GEMINI_API_KEY was not found`** — Check that your `.env` file exists in the project root and the key name is exactly `GEMINI_API_KEY`.

**`ModuleNotFoundError`** — Run `pip install -r requirements.txt` again to make sure all dependencies are installed.

**Backend port already in use** — If port 8001 is taken, start the backend on a different port:
```bash
uvicorn backend.main:app --reload --port 8002
```
Then update the fetch URL in `frontend/src/App.jsx` to match.

**Rules column not found** — Make sure your rules Excel has a column with the rule text. Rename it to `QC Point` if the system can't detect it automatically.

---

Built by [meekio](https://github.com/meekio)
