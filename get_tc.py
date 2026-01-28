import csv
import sys
from tcms_api import TCMS
import json


# ====== CONFIG ======
KIWI_XMLRPC_URL = "http://hub-stg.bosnetdis.com:8000/xml-rpc/"
USERNAME = "administrator"
PASSWORD = "QA_Bosn3t"

TEST_RUN_ID = 3
CSV_FILE = "kiwi_testcases_from_run.csv"
DELIMITER = ","
# ====================


def main():
    tcms = TCMS(
        KIWI_XMLRPC_URL,
        username=USERNAME,
        password=PASSWORD,
    ).exec

    # 1) Get executions from the run
    try:
        executions = tcms.TestExecution.filter({"run": TEST_RUN_ID})
    except Exception as e:
        print(f"ERROR fetching executions for run {TEST_RUN_ID}: {e}")
        sys.exit(1)

    if not executions:
        print(f"No executions found for Test Run {TEST_RUN_ID}")
        sys.exit(0)

    # 2) Collect unique case IDs from executions
    case_ids = set()
    for e in executions:
        tc_id = e.get("case") or e.get("testcase")
        if tc_id:
            case_ids.add(int(tc_id))

    if not case_ids:
        print("No test cases found in executions")
        sys.exit(0)

    case_ids = sorted(case_ids)
    print(f"Found {len(case_ids)} unique test cases in run {TEST_RUN_ID}")

    # 3) Fetch testcases (includes latest `text`)
    try:
        testcases = tcms.TestCase.filter({"id__in": case_ids})
    except Exception as e:
        print(f"ERROR fetching test cases via TestCase.filter(id__in): {e}")
        sys.exit(1)

    # 4) Write CSV (WITHOUT priority & case_status)
    with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(
            f,
            delimiter=DELIMITER,
            quoting=csv.QUOTE_ALL,  # important for multiline text
        )

        writer.writerow([
            "id",
            "summary",
            "category",
            "text",
        ])

        testcases = sorted(testcases, key=lambda x: int(x.get("id", 0)))

        for tc in testcases:
            writer.writerow([
                tc.get("id"),
                tc.get("summary"),
                tc.get("category__name") or tc.get("category"),
                (tc.get("text") or "").replace("\r\n", "\n"),
            ])

    print(f"\nDONE. Exported {len(testcases)} test cases to {CSV_FILE}")


if __name__ == "__main__":
    main()
