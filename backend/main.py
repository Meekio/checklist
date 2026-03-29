import os
import sys
import tempfile
import shutil
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Allow importing std.py from the project root regardless of where uvicorn is launched
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from std import run_qc

app = FastAPI(title="Engineering Drawing QC API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# Thread pool for blocking QC work (PDF rendering + Gemini calls)
_executor = ThreadPoolExecutor(max_workers=2)


def _run_qc_sync(pdf_path: str, xlsx_path: str, out_path: str):
    """Runs the blocking QC pipeline in a thread."""
    run_qc(pdf_path, xlsx_path, out_path)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/run-qc")
async def run_qc_endpoint(
    drawing: UploadFile = File(..., description="Engineering drawing PDF"),
    rules: UploadFile = File(..., description="QC rules Excel file (.xlsx)"),
):
    # Validate file types
    if not drawing.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Drawing must be a PDF file.")
    if not rules.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Rules must be an Excel file (.xlsx or .xls).")

    tmp_dir = tempfile.mkdtemp()
    try:
        pdf_path = os.path.join(tmp_dir, drawing.filename)
        xlsx_path = os.path.join(tmp_dir, rules.filename)
        out_path = os.path.join(
            tmp_dir, f"qc_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )

        # Save uploaded files
        with open(pdf_path, "wb") as f:
            f.write(await drawing.read())
        with open(xlsx_path, "wb") as f:
            f.write(await rules.read())

        # Run blocking QC in thread pool so we don't block the event loop
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, _run_qc_sync, pdf_path, xlsx_path, out_path)

        # Read results
        if not os.path.isfile(out_path):
            raise HTTPException(status_code=500, detail="QC output file was not produced.")

        df = pd.read_excel(out_path, engine="openpyxl")

        # Find the rules column (anything that isn't Status or Remarks)
        skip = {"Status", "Remarks"}
        rule_col = next((c for c in df.columns if c not in skip), df.columns[0])

        results = [
            {
                "rule": str(row.get(rule_col, "")),
                "status": str(row.get("Status", "Error")),
                "remarks": str(row.get("Remarks", "")),
            }
            for row in df.to_dict(orient="records")
        ]

        return JSONResponse({"results": results})

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
