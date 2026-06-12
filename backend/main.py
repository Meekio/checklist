import os
import sys
import tempfile
import shutil
import asyncio
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# Allow importing checklist_main.py from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from checklist_main import run_quality_check_process

app = FastAPI(title="Engineering Drawing QC API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

_executor = ThreadPoolExecutor(max_workers=2)

# Persistent output dir so the file survives after the request
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/run-qc")
async def run_qc_endpoint(
    drawing: UploadFile = File(..., description="Engineering drawing PDF"),
    rules:   UploadFile = File(..., description="Drawing-specific QC rules Excel (.xlsx)"),
):
    if not drawing.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Drawing must be a PDF file.")
    if not rules.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Rules must be an Excel file (.xlsx or .xls).")

    tmp_dir = tempfile.mkdtemp()
    try:
        pdf_path  = os.path.join(tmp_dir, drawing.filename)
        xlsx_path = os.path.join(tmp_dir, rules.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path  = os.path.join(OUTPUT_DIR, f"qc_results_{timestamp}.xlsx")

        with open(pdf_path,  "wb") as f:
            f.write(await drawing.read())
        with open(xlsx_path, "wb") as f:
            f.write(await rules.read())

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            _executor,
            run_quality_check_process,
            pdf_path, xlsx_path, out_path
        )

        if not os.path.isfile(out_path):
            raise HTTPException(status_code=500, detail="QC output file was not produced.")

        # Read file into memory so it's fully buffered before sending
        with open(out_path, "rb") as f:
            file_bytes = f.read()

        from fastapi.responses import Response
        return Response(
            content=file_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="qc_results_{timestamp}.xlsx"',
                "X-Filename": f"qc_results_{timestamp}.xlsx",
                "Access-Control-Expose-Headers": "Content-Disposition, X-Filename",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
