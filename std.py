# WORKING LOGIC AND FINAL ONE FOR QC

import os
import json
from pathlib import Path
from math import ceil
from datetime import datetime

import pandas as pd
import fitz  # PyMuPDF
from PIL import Image

from vertexai import init as vertex_init
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
import google.auth


PROJECT_ID = "prj-ltts-com-genai-cad"
LOCATION = "us-central1"
GEMINI_MODEL = "gemini-2.5-flash"
BATCH_SIZE = 20  # <= Change this if you want a different batch size


def ensure_adc_in_use():
    pass  # Auth handled via Vertex AI project/location init; no key file needed


def init_vertex():
    print(f"[INFO] Initializing Vertex AI (project='{PROJECT_ID}', location='{LOCATION}')...")
    # Explicitly unset key file env var so it uses gcloud ADC, not any leftover service account key
    os.environ.pop('GOOGLE_APPLICATION_CREDENTIALS', None)
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    vertex_init(project=PROJECT_ID, location=LOCATION, credentials=credentials)
    print("[INFO] Vertex AI initialized.")


def load_drawing_as_bytes(pdf_path: str, prefix: str):
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"Drawing not found: {pdf_path}")

    print(f"[INFO] Opening PDF: {pdf_path}")
    doc = fitz.open(pdf_path)
    results = []

    print(f"[INFO] Rendering {len(doc)} page(s) at 300 DPI...")
    for page_number in range(len(doc)):
        page = doc[page_number]
        pix = page.get_pixmap(dpi=300)

        output_filename = f"{prefix}_page_{page_number + 1}.png"
        pix.save(output_filename)

        img_bytes = pix.tobytes("png")
        results.append({"filename": output_filename, "bytes": img_bytes})
        print(f"[INFO] Saved: {output_filename} (page {page_number + 1})")

    doc.close()
    if not results:
        raise ValueError("No pages were rendered from the PDF.")
    print(f"[INFO] Completed rendering. Total pages: {len(results)}")
    return results


def check_rules_batch_with_gemini(model: GenerativeModel, image_parts, rules_batch):
    """
    Send a batch of rules (<= BATCH_SIZE) and all image parts to Gemini.
    Expect a JSON array with objects aligned to the order of rules in the batch:
    [
      {"status": "Correct|Incorrect|Error", "remarks": "short reason"},
      ...
    ]
    """
    # Construct the batch prompt
    numbered_rules = "\n".join([f"{i+1}. {r}" for i, r in enumerate(rules_batch)])
    prompt = f"""
You are an expert engineering drawing quality inspector.

Evaluate the attached engineering drawing (all pages provided as images) against the following QC rules.
Return STRICT JSON ONLY — a top-level array with one object per rule in the SAME ORDER.

Rules to evaluate:
{numbered_rules}

JSON response format (array, length must equal the number of rules above):
[
  {{
    "status": "Correct or Incorrect",
    "remarks": "Very short reason"
  }},
  ...
]
""".strip()

    gen_config = GenerationConfig()

    try:
        response = model.generate_content([prompt] + image_parts, generation_config=gen_config)
        return response.text
    except Exception as e:
        msg = str(e)
        if ('Could not automatically determine credentials' in msg
            or '403' in msg
            or 'permission' in msg.lower()
            or 'PERMISSION_DENIED' in msg.upper()):
            raise RuntimeError(
                "Vertex AI call failed. Ensure the account running this script has access to "
                "project 'gemini-gdandt-01' and the Vertex AI API is enabled.\n"
                f"Original error: {msg}"
            )
        raise


def _pick_rules_column(df: pd.DataFrame) -> str:
    """
    Try to find the column that contains the QC rules.
    Priority:
      1) exact 'QC Point'
      2) case-insensitive/fuzzy alternatives
      3) first non-empty text-like column
    """
    print("[INFO] Detecting rules column...")
    cols = list(df.columns)
    norm = {c: c.strip().lower() for c in cols}

    if 'QC Point' in df.columns:
        print("[INFO] Found 'QC Point' column exactly.")
        return 'QC Point'

    candidates = [
        'qc point', 'qc points', 'qc rule', 'qc rules',
        'rule', 'rules', 'check', 'check point', 'checklist',
        'qc', 'requirement', 'criteria'
    ]
    for c in cols:
        if norm[c] in candidates:
            print(f"[INFO] Using column '{c}' (matched '{norm[c]}').")
            return c

    # Fallback: first non-empty text-like column
    for c in cols:
        series = df[c]
        has_text = series.astype(str).str.strip().replace({'nan': ''}).str.len().gt(0).any()
        if has_text:
            print(f"[WARN] Falling back to column '{c}' (first non-empty). "
                  f"Please rename your header to 'QC Point' to avoid ambiguity.")
            return c

    raise ValueError("No suitable rules column found. Available columns: " + ", ".join(cols))


def chunked(seq, size):
    """Yield consecutive chunks of size `size` from `seq`."""
    for i in range(0, len(seq), size):
        yield seq[i:i + size], i  # return chunk and start index


def run_qc(drawing_path: str, rules_xlsx: str, output_path: str):
    print("=== QC Process Started ===")
    print(f"[INFO] PDF Path: {drawing_path}")
    print(f"[INFO] Rules Excel Path: {rules_xlsx}")
    print(f"[INFO] Output Path: {output_path}")

    # Render PDF pages and prepare image parts
    base_name = os.path.splitext(os.path.basename(drawing_path))[0]
    prefix = f"{base_name}"
    pages = load_drawing_as_bytes(drawing_path, prefix)
    image_parts = [Part.from_data(mime_type='image/png', data=p["bytes"]) for p in pages]
    print(f"[INFO] Prepared {len(image_parts)} image part(s) for Gemini.")

    # Load rules
    if not os.path.isfile(rules_xlsx):
        raise FileNotFoundError(f"Rules Excel not found: {rules_xlsx}")

    print(f"[INFO] Loading rules from Excel: {rules_xlsx}")
    try:
        df = pd.read_excel(rules_xlsx, engine='openpyxl')
    except Exception:
        df = pd.read_excel(rules_xlsx)

    print(f"[INFO] Excel columns: {list(df.columns)}")
    rules_col = _pick_rules_column(df)

    # Prepare rules list (cleaned)
    rules_series = df[rules_col]
    rules_list = []
    index_map = []  # map from rules_list index to original df row index
    for row_idx, val in enumerate(rules_series):
        s = "" if pd.isna(val) else str(val).strip()
        if s:
            rules_list.append(s)
            index_map.append(row_idx)
        else:
            # We'll mark blank ones as error later
            pass

    total_rules = len(df)
    non_blank_rules = len(rules_list)
    print(f"[INFO] Total rows: {total_rules}; Non-blank rules to evaluate: {non_blank_rules}")

    # Initialize Vertex and model
    init_vertex()
    model = GenerativeModel(GEMINI_MODEL)
    print("[INFO] Model 'gemini-2.5-flash' ready.")

    # Prepare output arrays aligned to df rows
    statuses = [""] * total_rules
    remarks = [""] * total_rules

    # Fill blanks now
    for row_idx, val in enumerate(rules_series):
        if (pd.isna(val)) or (not str(val).strip()):
            statuses[row_idx] = "Error"
            remarks[row_idx] = "Blank rule text"

    # Batch processing
    num_calls_expected = ceil(non_blank_rules / BATCH_SIZE) if non_blank_rules else 0
    print(f"[INFO] Batching {non_blank_rules} rules with batch size {BATCH_SIZE} -> expected {num_calls_expected} Gemini call(s).")

    processed = 0
    batch_num = 0
    for chunk, start_idx in chunked(rules_list, BATCH_SIZE):
        batch_num += 1
        print(f"[INFO] Calling Gemini for batch {batch_num}/{num_calls_expected} (rules {start_idx+1}..{start_idx+len(chunk)})...")
        try:
            resp_text = check_rules_batch_with_gemini(model, image_parts, chunk)
            try:
                parsed = json.loads(resp_text)

                # Validate shape: list of same length
                if not isinstance(parsed, list) or len(parsed) != len(chunk):
                    raise ValueError(f"Expected array of length {len(chunk)}; got {type(parsed)} with length {len(parsed) if isinstance(parsed, list) else 'N/A'}")

                # Map batch results back to original df row indices
                for i, item in enumerate(parsed):
                    row_idx = index_map[start_idx + i]
                    statuses[row_idx] = item.get('status', 'Error')
                    remarks[row_idx] = item.get('remarks', '')
                print(f"[INFO] Batch {batch_num}: processed {len(chunk)} rule(s).")

            except json.JSONDecodeError:
                # If JSON parsing fails, mark all rules in this batch as error
                print(f"[ERROR] Batch {batch_num}: Non-JSON response. Marking batch as Error.")
                for i in range(len(chunk)):
                    row_idx = index_map[start_idx + i]
                    statuses[row_idx] = 'Error'
                    remarks[row_idx] = 'Non-JSON response from model'
            except Exception as parse_e:
                print(f"[ERROR] Batch {batch_num}: {parse_e}. Marking batch as Error.")
                for i in range(len(chunk)):
                    row_idx = index_map[start_idx + i]
                    statuses[row_idx] = 'Error'
                    remarks[row_idx] = f'Batch parse error: {parse_e}'

        except Exception as call_e:
            print(f"[ERROR] Batch {batch_num}: {call_e}. Marking batch as Error.")
            for i in range(len(chunk)):
                row_idx = index_map[start_idx + i]
                statuses[row_idx] = 'Error'
                remarks[row_idx] = f'Gemini call error: {call_e}'

        processed += len(chunk)

    out_df = df.copy()
    out_df['Status'] = statuses
    out_df['Remarks'] = remarks

    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)

    out_df.to_excel(output_path, index=False)
    print('Saved:', output_path)
    print(f"[INFO] Processed {processed} non-blank rule(s) across {num_calls_expected} call(s) against {len(pages)} page(s).")
    print("=== QC Process Completed ===")


if __name__ == '__main__':
    try:
        ensure_adc_in_use()

        pdf = input("Enter PDF path: ").strip()
        rules = input("Enter rules Excel path: ").strip()

        out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
        os.makedirs(out_dir, exist_ok=True)

        out_file = os.path.join(out_dir, f'qc_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx')

        print("=== Launch Parameters ===")
        print(f"[INFO] PDF Path: {pdf}")
        print(f"[INFO] Rules Excel Path: {rules}")
        print(f"[INFO] Output Path: {out_file}")

        run_qc(pdf, rules, out_file)

    except Exception as main_e:
        print("### FATAL ERROR ###")
        print(str(main_e))
        print("### END ERROR ###")
