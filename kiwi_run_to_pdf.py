import sys
from datetime import datetime
from tcms_api import TCMS
from jinja2 import Template

# ====== CONFIG ======
KIWI_XMLRPC_URL = "http://hub-stg.bosnetdis.com:8000/xml-rpc/"
USERNAME = "administrator"
PASSWORD = "QA_Bosn3t"

TEST_RUN_ID = 3  # <-- change this

PROJECT_NAME = "Bosnet Project"
CLIENT_NAME = "Client Name"
ENVIRONMENT = "Staging"
QA_PREPARED_BY = "QA Team"

OUTPUT_HTML = "qa_test_report.html"
OUTPUT_PDF = "qa_test_report.pdf"
# ====================


HTML_TEMPLATE = r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>QA Test Report</title>
  <style>
    @page {
      size: A4;
      margin: 18mm 16mm 18mm 16mm;
      @bottom-right {
        content: "Page " counter(page) " of " counter(pages);
        font-size: 10px;
        color: #666;
      }
      @bottom-left {
        content: "{{ project_name }} — QA Test Report";
        font-size: 10px;
        color: #666;
      }
    }
    body { font-family: Arial, Helvetica, sans-serif; font-size: 12px; color: #111; }
    h1 { font-size: 22px; margin: 0 0 6px 0; }
    h2 { font-size: 16px; margin: 18px 0 8px 0; }
    h3 { font-size: 13px; margin: 12px 0 6px 0; }
    .muted { color: #666; }
    .cover { padding-top: 10mm; }
    .kv { margin-top: 12px; border: 1px solid #eee; border-radius: 8px; padding: 10px 12px; }
    .kv .row { display: flex; gap: 10px; padding: 2px 0; }
    .kv .k { width: 130px; font-weight: bold; color: #333; }
    .kv .v { flex: 1; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; border: 1px solid #ddd; }
    .badge.ok { border-color: #b7e1cd; background: #e6f4ea; }
    .badge.warn { border-color: #ffeeba; background: #fff3cd; }
    .table { width: 100%; border-collapse: collapse; margin-top: 8px; }
    .table th, .table td { border: 1px solid #eee; padding: 8px; vertical-align: top; }
    .table th { background: #fafafa; text-align: left; }
    .tc { border: 1px solid #eee; border-radius: 10px; padding: 10px 12px; margin: 10px 0; }
    .tc-meta { display: flex; flex-wrap: wrap; gap: 8px 12px; margin: 6px 0 10px 0; }
    .tc-meta div { color: #333; }
    pre {
      white-space: pre-wrap;
      word-wrap: break-word;
      background: #fbfbfb;
      border: 1px solid #eee;
      border-radius: 8px;
      padding: 10px;
      margin: 6px 0 0 0;
      font-family: Consolas, Menlo, Monaco, monospace;
      font-size: 11px;
      line-height: 1.35;
    }
    .page-break { page-break-after: always; }
  </style>
</head>
<body>

  <!-- COVER -->
  <div class="cover">
    <h1>QA Test Report</h1>
    <div class="muted">Generated on {{ generated_on }}</div>

    <div class="kv">
      <div class="row"><div class="k">Project</div><div class="v">{{ project_name }}</div></div>
      <div class="row"><div class="k">Client</div><div class="v">{{ client_name }}</div></div>
      <div class="row"><div class="k">Environment</div><div class="v">{{ environment }}</div></div>
      <div class="row"><div class="k">Test Run ID</div><div class="v">{{ test_run_id }}</div></div>
      <div class="row"><div class="k">Prepared By</div><div class="v">{{ prepared_by }}</div></div>
      <div class="row"><div class="k">Total Test Cases</div><div class="v"><span class="badge ok">{{ total_cases }}</span></div></div>
    </div>
  </div>

  <div class="page-break"></div>

  <!-- SUMMARY -->
  <h2>Test Execution Summary</h2>
  <table class="table">
    <tr><th>Metric</th><th>Value</th></tr>
    <tr><td>Test Run ID</td><td>{{ test_run_id }}</td></tr>
    <tr><td>Total unique test cases in run</td><td>{{ total_cases }}</td></tr>
    <tr><td>Notes</td><td class="muted">This report lists scenario-level test cases executed in the run, including the latest saved steps (text).</td></tr>
  </table>

  <h2>Test Case List</h2>
  <div class="muted">Scenario + general steps (latest text)</div>

  {% for tc in testcases %}
    <div class="tc">
      <h3>{{ loop.index }}. [TC-{{ tc.id }}] {{ tc.summary }}</h3>
      <div class="tc-meta">
        <div><b>Category:</b> {{ tc.category }}</div>
      </div>
      <div><b>Steps / Expected:</b></div>
      <pre>{{ tc.text }}</pre>
    </div>
  {% endfor %}

</body>
</html>
"""


def get_cases_from_run(tcms, run_id: int):
    # 1) executions in the run
    executions = tcms.TestExecution.filter({"run": run_id})
    if not executions:
        return []

    # 2) extract case IDs
    case_ids = set()
    for e in executions:
        tc_id = e.get("case") or e.get("testcase")
        if tc_id:
            case_ids.add(int(tc_id))

    if not case_ids:
        return []

    case_ids = sorted(case_ids)

    # 3) fetch cases with latest "text" via TestCase.filter
    testcases = tcms.TestCase.filter({"id__in": case_ids})

    # normalize to simple fields for template
    normalized = []
    for tc in sorted(testcases, key=lambda x: int(x.get("id", 0))):
        normalized.append({
            "id": tc.get("id"),
            "summary": tc.get("summary") or "",
            "category": tc.get("category__name") or tc.get("category") or "",
            "text": (tc.get("text") or "").replace("\r\n", "\n").strip(),
        })
    return normalized


def render_html(context: dict) -> str:
    tpl = Template(HTML_TEMPLATE)
    return tpl.render(**context)


def html_to_pdf(html_path: str, pdf_path: str):
    try:
        from weasyprint import HTML
    except Exception as e:
        print("ERROR: WeasyPrint import failed.")
        print("Install with: pip install weasyprint")
        print(f"Details: {e}")
        sys.exit(1)

    HTML(filename=html_path).write_pdf(pdf_path)


def main():
    tcms = TCMS(KIWI_XMLRPC_URL, username=USERNAME, password=PASSWORD).exec

    testcases = get_cases_from_run(tcms, TEST_RUN_ID)
    if not testcases:
        print(f"No test cases found for Test Run {TEST_RUN_ID}")
        sys.exit(0)

    context = {
        "generated_on": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "project_name": PROJECT_NAME,
        "client_name": CLIENT_NAME,
        "environment": ENVIRONMENT,
        "prepared_by": QA_PREPARED_BY,
        "test_run_id": TEST_RUN_ID,
        "total_cases": len(testcases),
        "testcases": testcases,
    }

    html = render_html(context)

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"OK: HTML generated -> {OUTPUT_HTML}")

    html_to_pdf(OUTPUT_HTML, OUTPUT_PDF)
    print(f"OK: PDF generated  -> {OUTPUT_PDF}")
    print("DONE 🔥")


if __name__ == "__main__":
    main()
