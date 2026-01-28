import csv
import re
from pathlib import Path

INPUT_FILE = "input.csv"
OUTPUT_FILE = "kiwi_one_line.csv"

PRODUCT = 1
CATEGORY = 1
OUTPUT_DELIMITER = ','


def clean(s: str) -> str:
    if s is None:
        return ""
    # Trim whitespace + remove stray wrapping quotes only at the ends
    s = s.strip()
    s = s.strip('"')
    # Normalize internal whitespace a bit (but keep newlines if any)
    s = re.sub(r"[ \t]+", " ", s)
    return s


def parse_int(s: str) -> int:
    s = clean(s)
    try:
        return int(s)
    except Exception:
        return 0


def build_steps_text(step_rows):
    """
    step_rows: list of dicts with keys: no(int), steps(str), expected(str)
    """
    lines = []
    for r in sorted(step_rows, key=lambda x: x["no"]):
        action = clean(r["steps"])
        expected = r["expectedresult"]
        expected = expected.replace("\\n", "\n")  # if someone uses literal \n
        expected = expected.strip()

        if action:
            lines.append(f'{r["no"]}. {action}')
        else:
            lines.append(f'{r["no"]}.')  # fallback if action empty

        # Support multi-expected separated by newlines or " - " bullets
        # If expected has bullet-ish " - " patterns, we split conservatively:
        exp_lines = []
        if "\n" in expected:
            exp_lines = [x.strip() for x in expected.split("\n") if x.strip()]
        else:
            # If people wrote: "A - B - C" we convert into multiple outcomes
            # But avoid splitting negative numbers / dates; keep simple heuristic:
            if " - " in expected:
                exp_lines = [x.strip() for x in expected.split(" - ") if x.strip()]
            else:
                exp_lines = [expected] if expected else []

        for el in exp_lines:
            lines.append(f"   → {el}")

    return "\n".join(lines).strip()


def read_input_rows(path: str):
    # Try to sniff delimiter (comma vs semicolon)
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    sample = raw[:2000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t"])
    except Exception:
        dialect = csv.excel  # default comma

    rows = []
    reader = csv.DictReader(raw.splitlines(), dialect=dialect)
    for r in reader:
        # Normalize header names in case of different casing
        rr = {k.strip().lower(): (v if v is not None else "") for k, v in r.items()}
        rows.append({
            "summary": clean(rr.get("summary", "")),
            "no": parse_int(rr.get("no", "")),
            "steps": rr.get("steps", "").strip(),
            "expectedresult": rr.get("expectedresult", "").strip(),
        })
    return rows


def convert(input_file: str, output_file: str):
    rows = read_input_rows(input_file)

    testcases = []
    current = None

    for r in rows:
        summary = r["summary"]

        # If this row starts a new testcase
        if summary:
            if current:
                testcases.append(current)
            current = {
                "summary": summary,
                "steps": []
            }

        # If summary is empty but we don't have a current testcase yet, skip
        if not current:
            continue

        # Some rows may have empty expectedresult at the end (like your step 8 had trailing comma)
        current["steps"].append(r)

    if current:
        testcases.append(current)

    # Write output: one row per testcase
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=OUTPUT_DELIMITER, quoting=csv.QUOTE_ALL)
        w.writerow(["summary", "product", "category", "steps_text"])

        for tc in testcases:
            steps_text = build_steps_text(tc["steps"])
            w.writerow([tc["summary"], PRODUCT, CATEGORY, steps_text])

    print(f"OK: wrote {len(testcases)} testcases to {output_file}")


if __name__ == "__main__":
    convert(INPUT_FILE, OUTPUT_FILE)
