import csv
import io
import re
import sys
from pathlib import Path
from tcms_api import TCMS

# =======================
# CONFIG
# =======================

USERNAME = "administrator"
PASSWORD = "QA_Bosn3t"
PRODUCT = 1                       # default product id
CATEGORY = 1                      # default category id

KIWI_XMLRPC_URL = "http://hub-stg.bosnetdis.com:8000/xml-rpc/"
INPUT_FILE = "input.csv"          # <-- your raw file from Google Sheets
DEFAULT_PRIORITY_ID = 1
CASE_STATUS_ID = 1                # 1 = CONFIRMED in Kiwi typically (depends on your setup)

DRY_RUN = False                   # True = do not create cases, only print preview
# =======================


def clean(s: str) -> str:
    """Trim + remove stray wrapping quotes only at the ends, normalize spaces (keep newlines)."""
    if s is None:
        return ""
    s = str(s)
    s = s.strip()
    s = s.strip('"')
    s = re.sub(r"[ \t]+", " ", s)
    return s


def parse_int(s: str) -> int:
    s = clean(s)
    try:
        return int(s)
    except Exception:
        return 0


def normalize_newlines_literal(s: str) -> str:
    """Convert literal backslash-n to real newline, and normalize CRLF."""
    if s is None:
        return ""
    s = str(s)
    s = s.replace("\\n", "\n")
    s = s.replace("\r\n", "\n")
    return s


def clean_text_for_kiwi(s: str) -> str:
    """
    Extra cleanup for text that will go into Kiwi 'text' field.
    Keeps newlines.
    """
    s = normalize_newlines_literal(s)
    # Convert doubled quotes artifact if it appears (rare when reading via csv module)
    s = s.replace('""', '"')
    # Remove accidental lone trailing quote at the very end
    s = re.sub(r'"\s*$', "", s)
    return s.strip()


def build_steps_text(step_rows):
    """
    step_rows: list of dicts with keys: no(int), steps(str), expectedresult(str)
    Output format:
      1. Do something
         → expected
    """
    lines = []

    for r in sorted(step_rows, key=lambda x: x["no"]):
        # Convert literal \n to real newlines in BOTH steps and expected
        action_raw = normalize_newlines_literal(r.get("steps") or "")
        expected_raw = normalize_newlines_literal(r.get("expectedresult") or "")

        action = clean(action_raw)
        expected = expected_raw.strip()

        if action:
            lines.append(f'{r["no"]}. {action}')
        else:
            lines.append(f'{r["no"]}.')

        # expected could be multiline or " - " separated
        exp_lines = []
        if "\n" in expected:
            exp_lines = [x.strip() for x in expected.split("\n") if x.strip()]
        else:
            if " - " in expected:
                exp_lines = [x.strip() for x in expected.split(" - ") if x.strip()]
            else:
                exp_lines = [expected] if expected else []

        for el in exp_lines:
            lines.append(f"   → {el}")

    return "\n".join(lines).strip()


def sniff_dialect(raw_text: str):
    sample = raw_text[:2000]
    try:
        return csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t"])
    except Exception:
        return csv.excel  # default comma


def read_input_rows(path: str):
    """
    Reads input.csv which is step-based:
      summary;no;steps;expectedresult
    summary is filled only at testcase start; next rows summary is empty -> continues previous testcase.
    """
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    dialect = sniff_dialect(raw)

    reader = csv.DictReader(io.StringIO(raw), dialect=dialect)
    if not reader.fieldnames:
        raise ValueError("CSV has no header row / fieldnames.")

    # Normalize headers
    header_norm = [h.strip().lower() for h in reader.fieldnames]
    required = {"summary", "no", "steps", "expectedresult"}
    missing = required - set(header_norm)
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}. Found: {reader.fieldnames}")

    rows = []
    for r in reader:
        rr = {k.strip().lower(): (v if v is not None else "") for k, v in r.items()}
        rows.append({
            "summary": clean_text_for_kiwi(rr.get("summary", "")),
            "no": parse_int(rr.get("no", "")),
            "steps": rr.get("steps", "").strip(),
            "expectedresult": rr.get("expectedresult", "").strip(),
        })

    return rows


def group_into_testcases(rows):
    """
    Convert step rows into list of:
      { summary: str, steps: [row,row,...] }
    """
    testcases = []
    current = None

    for r in rows:
        summary = (r.get("summary") or "").strip()

        if summary:
            if current:
                testcases.append(current)
            current = {"summary": summary, "steps": []}

        if not current:
            # skip rows before first summary
            continue

        current["steps"].append(r)

    if current:
        testcases.append(current)

    return testcases


def import_to_kiwi(testcases):
    tcms = TCMS(KIWI_XMLRPC_URL, username=USERNAME, password=PASSWORD).exec

    created = 0
    failed = 0

    for idx, tc in enumerate(testcases, start=1):
        summary = (tc.get("summary") or "").strip()
        if not summary:
            continue

        steps_text = build_steps_text(tc.get("steps") or [])
        steps_text = clean_text_for_kiwi(steps_text)

        values = {
            "summary": summary,
            "product": int(PRODUCT),
            "category": int(CATEGORY),
            "priority": int(DEFAULT_PRIORITY_ID),
            "text": steps_text,
            "case_status": int(CASE_STATUS_ID),
        }

        if DRY_RUN:
            created += 1
            print(f"[DRY] {idx}. summary={summary}")
            print(steps_text)
            print("-" * 60)
            continue

        try:
            created_tc = tcms.TestCase.create(values)
            created += 1
            print(f"OK {idx}: created TestCase id={created_tc.get('id')} summary={summary}")
        except Exception as e:
            failed += 1
            print(f"FAIL {idx}: {summary} -> {e}")

    print(f"\nDONE. created={created} failed={failed}")


def main():
    try:
        rows = read_input_rows(INPUT_FILE)
        testcases = group_into_testcases(rows)
        print(f"Parsed {len(rows)} rows into {len(testcases)} testcases.")
        import_to_kiwi(testcases)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
