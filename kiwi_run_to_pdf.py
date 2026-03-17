import os
import re
from datetime import datetime
from tcms_api import TCMS
from jinja2 import Template

OUTPUT_HTML = "qa_test_report.html"
EVIDENCE_FOLDER = "evidence"
LOGO_FILE = "bosnet_logo.png"

KIWI_XMLRPC_URL = "http://hub-stg.bosnetdis.com:8000/xml-rpc/"
USERNAME = "administrator"
PASSWORD = "QA_Bosn3t"

TEST_RUN_ID = 37
CLIENT_NAME = "PT. SOFTEX INDONESIA"
PROJECT_CODE = "BDI/BND/SGPA/01/00278"
ENVIRONMENT = "Staging"


def parse_kiwi_datetime(value):
    if not value:
        return None

    value = str(value).strip()

    for fmt in ("%Y%m%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue

    return None


def get_run_information(tcms):
    run = tcms.TestRun.filter({"id": TEST_RUN_ID})[0]

    plan_id = run["plan"]
    plan = tcms.TestPlan.filter({"id": plan_id})[0]

    product_id = plan["product"]
    product = tcms.Product.filter({"id": product_id})[0]

    start_date = parse_kiwi_datetime(run.get("start_date"))
    end_date = parse_kiwi_datetime(run.get("stop_date"))

    return {
        "project": plan.get("name", ""),
        "run_summary": run.get("summary", ""),
        "product": product.get("name", ""),
        "start_date": start_date,
        "end_date": end_date,
    }


def get_execution_sort_key(execution):
    exec_id = int(execution.get("id", 0))

    for field in ["tested_date", "stop_date", "close_date", "modified_date"]:
        dt = parse_kiwi_datetime(execution.get(field))
        if dt:
            return (1, dt.timestamp(), exec_id)

    return (0, exec_id)


def collect_evidence_files():
    if not os.path.exists(EVIDENCE_FOLDER):
        return []

    files = []
    for name in os.listdir(EVIDENCE_FOLDER):
        full_path = os.path.join(EVIDENCE_FOLDER, name)
        if os.path.isfile(full_path):
            files.append((name, full_path))

    return files

def extract_sort_key(filepath):
    filename = os.path.basename(filepath)

    # extract last number (usually step number)
    numbers = re.findall(r'\d+', filename)
    order = int(numbers[-1]) if numbers else 0

    return order

def find_evidence_for_case(evidence_files, execution_id, testcase_id):
    matched = []

    exec_prefixes = [
        f"EXEC-{execution_id}-",
        f"TE-{execution_id}-",
    ]

    tc_prefixes = [
        f"TC-{testcase_id}-",
    ]

    for filename, full_path in evidence_files:
        upper_name = filename.upper()

        if any(upper_name.startswith(prefix.upper()) for prefix in exec_prefixes):
            matched.append(full_path)

    if matched:
        matched.sort(key=extract_sort_key)
        return matched

    for filename, full_path in evidence_files:
        upper_name = filename.upper()

        if any(upper_name.startswith(prefix.upper()) for prefix in tc_prefixes):
            matched.append(full_path)

    matched.sort(key=extract_sort_key)
    return matched


def get_cases_from_run(tcms):
    executions = tcms.TestExecution.filter({"run": TEST_RUN_ID})

    latest_execution_by_case = {}

    for e in executions:
        tc_id = e.get("case") or e.get("testcase")
        exec_id = e.get("id")

        if not tc_id or not exec_id:
            continue

        tc_id = int(tc_id)
        exec_id = int(exec_id)

        current = {
            "execution_id": exec_id,
            "testcase_id": tc_id,
            "status": str(e.get("status__name", "UNKNOWN")).upper(),
            "raw": e,
        }

        existing = latest_execution_by_case.get(tc_id)
        if not existing:
            latest_execution_by_case[tc_id] = current
            continue

        current_key = get_execution_sort_key(e)
        existing_key = get_execution_sort_key(existing["raw"])

        if current_key > existing_key:
            latest_execution_by_case[tc_id] = current

    case_ids = list(latest_execution_by_case.keys())
    if not case_ids:
        return [], 0, 0, 0

    testcases = tcms.TestCase.filter({"id__in": case_ids})
    testcase_map = {int(tc["id"]): tc for tc in testcases}

    evidence_files = collect_evidence_files()

    normalized = []
    passed = 0
    failed = 0

    for tc_id in sorted(case_ids):
        selected = latest_execution_by_case[tc_id]
        exec_id = selected["execution_id"]
        status = selected["status"]

        tc = testcase_map.get(tc_id, {})

        evidence = find_evidence_for_case(
            evidence_files=evidence_files,
            execution_id=exec_id,
            testcase_id=tc_id,
        )

        if status == "PASSED":
            passed += 1
        elif status == "FAILED":
            failed += 1

        normalized.append({
            "testcase_id": tc_id,
            "execution_id": exec_id,
            "summary": tc.get("summary", ""),
            "category": tc.get("category__name", ""),
            "text": (tc.get("text") or "").replace("\\r\\n", "\n"),
            "status": status,
            "evidence": evidence,
        })

    executed = len(normalized)
    return normalized, executed, passed, failed


def main():
    tcms = TCMS(
        KIWI_XMLRPC_URL,
        username=USERNAME,
        password=PASSWORD
    ).exec

    run_info = get_run_information(tcms)
    testcases, executed, passed, failed = get_cases_from_run(tcms)

    context = {
        "logo": LOGO_FILE,
        "project": run_info["project"],
        "code": PROJECT_CODE,
        "product": run_info["product"],
        "client": CLIENT_NAME,
        "env": ENVIRONMENT,
        "run_id": TEST_RUN_ID,
        "run_summary": run_info["run_summary"],
        "start_date": run_info["start_date"],
        "end_date": run_info["end_date"],
        "executed": executed,
        "passed": passed,
        "failed": failed,
        "testcases": testcases,
    }

    with open("template.html", "r", encoding="utf-8") as f:
        template = Template(f.read())
        html = template.render(**context)

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print("HTML generated")


if __name__ == "__main__":
    main()