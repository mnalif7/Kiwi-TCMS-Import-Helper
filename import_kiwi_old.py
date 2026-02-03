import csv
import re
import sys
from tcms_api import TCMS

# ====== CONFIG ======
KIWI_XMLRPC_URL = "http://hub-stg.bosnetdis.com:8000/xml-rpc/"  # e.g. https://hub-stg.bosnetdis.com/xmlrpc/
USERNAME = "administrator"
PASSWORD = "QA_Bosn3t"

CSV_FILE = "kiwi_one_line.csv"  # your file
DELIMITER = ","  # change to ';' if your CSV is semicolon-delimited
DEFAULT_PRIORITY_ID = 1  # adjust if needed
# ====================


def clean_text(s: str) -> str:
    if s is None:
        return ""
    s = str(s)

    # Fix common CSV escaping artifacts that end up in the text:
    # 1) Convert doubled quotes "" -> "
    s = s.replace('""', '"')

    # 2) Remove accidental lone trailing quote at the very end
    s = re.sub(r'"\s*$', "", s)

    # 3) Normalize CRLF
    s = s.replace("\r\n", "\n")
    return s.strip()


def main():
    tcms = TCMS(KIWI_XMLRPC_URL, username=USERNAME, password=PASSWORD).exec  

    created = 0
    failed = 0

    with open(CSV_FILE, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=DELIMITER)

        required_cols = {"summary", "product", "category", "steps_text"}
        missing = required_cols - set((c or "").strip().lower() for c in reader.fieldnames or [])
        if missing:
            print(f"ERROR: CSV missing columns: {missing}")
            sys.exit(1)

        for i, row in enumerate(reader, start=2):  # start=2 because header is line 1
            summary = (row.get("summary") or "").strip()
            if not summary:
                print(f"SKIP line {i}: empty summary")
                continue

            try:
                product_id = int(str(row.get("product") or "").strip())
                category_id = int(str(row.get("category") or "").strip())
            except ValueError:
                print(f"FAIL line {i}: product/category must be integers. row={row}")
                failed += 1
                continue

            steps_text = clean_text(row.get("steps_text") or "")

            values = {
                "summary": summary,
                "product": product_id,
                "category": category_id,
                "priority": DEFAULT_PRIORITY_ID,
                # Store your formatted steps in the case TEXT field
                "text": steps_text,
                "case_status": 1,
            }

            try:
                tc = tcms.TestCase.create(values)
                created += 1
                print(f"OK line {i}: created TestCase id={tc.get('id')} summary={summary}")
            except Exception as e:
                failed += 1
                print(f"FAIL line {i}: {summary} -> {e}")

    print(f"\nDONE. created={created} failed={failed}")


if __name__ == "__main__":
    main()
