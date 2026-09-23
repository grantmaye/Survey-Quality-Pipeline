"""Render the same aggregate payload to JSON and a portable HTML report."""
import html
import json
from pathlib import Path


def render_html(payload: dict) -> str:
    rows = []
    for group in payload["groups"]:
        course, term = html.escape(group["course"]), html.escape(group["term"])
        if group["suppressed"]:
            cells = '<td colspan="3" class="muted">Hidden: fewer than the minimum responses</td>'
        else:
            cells = (f'<td>{group["responses"]}</td><td><strong>{group["mean_rating"]:.2f}</strong> / 5</td>'
                     f'<td>{group["favorable_pct"]:.1f}%</td>')
        rows.append(f"<tr><th scope='row'>{course}</th><td>{term}</td>{cells}</tr>")
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>SurveyLens | Evaluation report</title>
<style>
:root{font-family:system-ui,sans-serif;color:#172e40;background:#eef3f6}body{margin:0;padding:48px 24px}
main{max-width:1000px;margin:auto}header{background:#143b48;color:white;padding:36px;border-radius:18px}
.eyebrow{letter-spacing:.16em;font-size:12px;color:#b5e8dd}h1{font-size:36px;margin:12px 0}p{line-height:1.6}
.card{background:white;padding:24px;margin-top:24px;border-radius:18px;border:1px solid #dce5eb}
.scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;text-align:left;white-space:nowrap}
th,td{padding:16px 12px;border-bottom:1px solid #e0e8ed}thead{color:#496573;font-size:13px}
.muted{color:#586c78}strong{color:#12624d}footer{font-size:13px;color:#496573;margin:24px 8px}.table-hint{display:none}
@media(max-width:600px){body{padding:20px 12px}header{padding:24px}h1{font-size:28px}.card{padding:12px}.table-hint{display:block;font-size:12px;color:#586c78}}
</style></head><body><main><header><div class="eyebrow">SURVEYLENS / SAMPLE EVALUATIONS</div>
<h1>From raw responses to usable insight.</h1><p>Validated course evaluations, summarized by term and course.
Favorable means a rating of 4 or 5.</p></header><section class="card"><h2>Course results</h2>
<p class="muted">Groups below MINIMUM responses have their counts and scores hidden.</p>
<p class="table-hint">Scroll the table sideways to view all results.</p>
<div class="scroll" tabindex="0" role="region" aria-label="Course results, scroll horizontally on small screens"><table><thead><tr><th scope="col">Course</th><th scope="col">Term</th>
<th scope="col">Responses</th><th scope="col">Mean rating</th><th scope="col">Favorable</th></tr></thead>
<tbody>ROWS</tbody></table></div></section><footer>Independent personal project. Demo inputs are synthetic.
Small-group suppression is a reporting rule, not a guarantee of anonymity.</footer></main></body></html>""".replace(
        "MINIMUM", str(payload["minimum_responses"])).replace("ROWS", "".join(rows) or '<tr><td colspan="5">No data imported.</td></tr>')


def write_report(payload: dict, directory: str | Path) -> dict:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "report.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (directory / "report.html").write_text(render_html(payload), encoding="utf-8")
    return {"json": str(directory / "report.json"), "html": str(directory / "report.html")}
