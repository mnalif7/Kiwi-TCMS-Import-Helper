import os
from datetime import datetime
from tcms_api import TCMS
from jinja2 import Template

KIWI_XMLRPC_URL = "http://hub-stg.bosnetdis.com:8000/xml-rpc/"
USERNAME = "administrator"
PASSWORD = "QA_Bosn3t"

TEST_RUN_ID = 34

CLIENT_NAME = "PT. KALBE NUTRITIONALS"
ENVIRONMENT = "Staging"

OUTPUT_HTML = "qa_test_report.html"

EVIDENCE_FOLDER = "evidence"
LOGO_FILE = "bosnet_logo.png"


HTML_TEMPLATE = """

<!DOCTYPE html>
<html>
<head>

<meta charset="utf-8">
<title>Book of Scenario DCA Dashboard</title>

<style>

body{
font-family:Arial, Helvetica, sans-serif;
margin:0;
background:#ffffff;
color:#333;
}

.header-banner img{
width:100%;
display:block;
}

.container{
padding:28px;
max-width:1000px;
margin:auto;
}

h2{
font-size:18px;
margin-bottom:6px;
}

.project-table{
margin-top:6px;
font-size:12px;
border-collapse:collapse;
}

.project-table td{
padding:2px 10px 2px 0;
vertical-align:top;
}

.project-label{
font-weight:bold;
width:160px;
}

/* SUMMARY */

.summary{
margin-top:10px;
padding:6px 0;
}

.summary h3{
font-size:13px;
margin-bottom:4px;
}

.summary table td{
font-size:11px;
padding:1px 14px 1px 0;
}

/* TESTCASE */

.tc{
padding:6px 0;
margin-top:10px;
page-break-inside: avoid;
break-inside: avoid;
}

.tc h3{
font-size:13px;
font-weight:600;
margin-bottom:2px;
display:flex;
justify-content:space-between;
align-items:center;
}

.title{
flex:1;
padding-right:10px;
}

.category{
font-size:11px;
margin-bottom:2px;
color:#444;
}

.badge{
padding:2px 8px;
border-radius:999px;
font-size:10px;
font-weight:600;
white-space:nowrap;
flex-shrink:0;
}

.PASSED{
background:#d1fae5;
color:#065f46;
}

.FAILED{
background:#fdecea;
color:#b02a37;
}

.BLOCKED{
background:#fff4e5;
color:#a15c00;
}

.ERROR{
background:#fdecea;
color:#b02a37;
}

.UNKNOWN{
background:#eee;
color:#555;
}

/* STEPS */

pre{
background:#ffffff;
padding:4px 0;
white-space:pre-wrap;
font-size:11px;
line-height:15px;
margin-top:2px;
}

/* EVIDENCE */

.evidence-title{
font-size:10px;
margin-top:4px;
margin-bottom:3px;
}

.evidence-grid{
display:grid;
grid-template-columns:repeat(2,1fr);
gap:10px;
margin-top:4px;
}

.evidence-grid img{
width:100%;
max-width:420px;
border-radius:3px;
}

</style>

</head>

<body>

<div class="header-banner">
<img src="{{logo}}">
</div>

<div class="container">

<h2>Book of Scenario DCA Dashboard</h2>

<table class="project-table">

<tr>
<td class="project-label">PROJECT NAME</td>
<td>: {{project}}</td>
</tr>

<tr>
<td class="project-label">CODE</td>
<td>: BDI/BND/SGPA/01/00278</td>
</tr>

<tr>
<td class="project-label">PRODUCT</td>
<td>: {{product}}</td>
</tr>

<tr>
<td class="project-label">CLIENT</td>
<td>: {{client}}</td>
</tr>

<tr>
<td class="project-label">ENVIRONMENT</td>
<td>: {{env}}</td>
</tr>

<tr>
<td class="project-label">RUN ID</td>
<td>: {{run_id}}</td>
</tr>

<tr>
<td class="project-label">DATE EXECUTION</td>
<td>: {{execution_date}}</td>
</tr>

</table>

<div class="summary">

<h3>Test Execution Summary</h3>

<table>
<tr>
<td>Executed Test Cases</td>
<td>: {{executed}}</td>
</tr>

<tr>
<td>Passed</td>
<td>: {{passed}}</td>
</tr>

<tr>
<td>Failed</td>
<td>: {{failed}}</td>
</tr>

</table>

</div>

{% for tc in testcases %}

<div class="tc">

<h3>

<div class="title">
{{loop.index}}. {{tc.summary}}
</div>

<span class="badge {{tc.status}}">
{{tc.status}}
</span>

</h3>

<div class="category">
<b>Category:</b> {{tc.category}}
</div>

<pre>{{tc.text}}</pre>

{% if tc.evidence %}

<div class="evidence-title"><b>Evidence</b></div>

<div class="evidence-grid">

{% for img in tc.evidence %}

<img src="{{img}}">

{% endfor %}

</div>

{% endif %}

</div>

{% endfor %}

</div>

</body>
</html>

"""


def get_run_information(tcms):

    run = tcms.TestRun.filter({"id": TEST_RUN_ID})[0]

    plan_id = run["plan"]
    plan = tcms.TestPlan.filter({"id": plan_id})[0]

    product_id = plan["product"]
    product = tcms.Product.filter({"id": product_id})[0]

    finished = run.get("stop_date")

    execution_date = ""

    if finished:
        finished_str = str(finished)
        dt = datetime.strptime(finished_str, "%Y%m%dT%H:%M:%S")
        execution_date = dt.strftime("%d %B %Y")

    return {
        "project": plan["name"],
        "product": product["name"],
        "execution_date": execution_date
    }


def get_cases_from_run(tcms):

    executions = tcms.TestExecution.filter({"run": TEST_RUN_ID})

    case_ids = []
    status_map = {}

    passed = 0
    failed = 0

    for e in executions:

        tc_id = e.get("case") or e.get("testcase")

        if not tc_id:
            continue

        tc_id = int(tc_id)
        case_ids.append(tc_id)

        status = str(e.get("status__name","UNKNOWN")).upper()
        status_map[tc_id] = status

        if status == "PASSED":
            passed += 1

        if status == "FAILED":
            failed += 1

    testcases = tcms.TestCase.filter({"id__in": case_ids})

    normalized = []

    for idx, tc in enumerate(testcases, start=1):

        tc_id = int(tc.get("id"))

        evidence = []

        if os.path.exists(EVIDENCE_FOLDER):

            for f in os.listdir(EVIDENCE_FOLDER):

                if f.startswith(f"TC-{idx}-"):
                    evidence.append(os.path.join(EVIDENCE_FOLDER, f))

        evidence.sort()

        normalized.append({
            "summary": tc.get("summary",""),
            "category": tc.get("category__name",""),
            "text": (tc.get("text") or "").replace("\\r\\n","\\n"),
            "status": status_map.get(tc_id,"UNKNOWN"),
            "evidence": evidence
        })

    return normalized, len(case_ids), passed, failed


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
        "product": run_info["product"],
        "client": CLIENT_NAME,
        "env": ENVIRONMENT,
        "run_id": TEST_RUN_ID,
        "execution_date": run_info["execution_date"],
        "executed": executed,
        "passed": passed,
        "failed": failed,
        "testcases": testcases
    }

    html = Template(HTML_TEMPLATE).render(**context)

    with open(OUTPUT_HTML,"w",encoding="utf-8") as f:
        f.write(html)

    print("HTML generated")


if __name__ == "__main__":
    main()
