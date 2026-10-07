# Why SurveyLens is useful

## The problem and intended audience

A spreadsheet can calculate an average while hiding how invalid answers, duplicate exports, and conflicting corrections were handled. SurveyLens makes those decisions explicit: validate before counting, preserve import receipts, and apply one reporting rule to both machine-readable JSON and human-readable HTML.

The repository is a personal portfolio and teaching project. Its synthetic fixture supports learning by junior data engineers, analysts exploring Python and SQL, and reviewers assessing transactional data-processing code. There is no claim of institutional deployment, actual students, paying customers, or an origin inside an employer.

## A hypothetical workflow

Imagine a fictional training coordinator, Sam, collecting workshop ratings from several invented courses. Before using a pipeline, Sam copies rows between workbooks, accidentally imports one export twice, and notices that a two-person class has an identifiable average. There is no clear record of why last week's chart changed.

In a SurveyLens demonstration, Sam imports the included synthetic CSV. The receipt explains the counts; invalid records receive reason codes, a duplicate does not inflate an average, and an ID conflict does not overwrite the earlier answer. Replaying the exact file returns the original receipt. Sam exports a report with a five-answer minimum and reviews the same values in JSON and HTML.

This scenario illustrates the software's intended benefit, not a real customer story. The benefit is inspectability and repeatability, not evidence that it improves educational outcomes or guarantees confidentiality.

## Before and after

| Before | With this project |
| --- | --- |
| Copy/paste can count the same response twice | Hash receipts and stable IDs make duplicate semantics explicit |
| Bad values enter a formula or disappear silently | Invalid records are counted with redacted reasons |
| Report calculations differ between tools | One aggregate payload feeds HTML and JSON |
| Small groups are displayed like large groups | Counts and scores are suppressed below a chosen minimum |
| A broken import leaves uncertainty | A failed parsing/database transaction rolls back its changes |

The evidence is in [pipeline.py](../surveylens/pipeline.py), [render.py](../surveylens/render.py), and [the regression tests](../tests/test_pipeline.py). The [manual](technical-manual.md) explains the contracts and reproducible commands.

## What the software cannot promise

Suppression is not anonymity. There is no consent management, access control, retention engine, statistical significance analysis, enrollment-based response rate, or integration with a real survey platform. The database retains accepted response-level records. The 25 MiB snapshot cap deliberately limits scale. Report files can be copied without authentication, so only synthetic data belongs in the public demo.

## A 60–90 second demo narration

“SurveyLens is a small Python pipeline for making survey reporting reproducible. All of these responses and course names are synthetic. I run the demo, and its receipt shows 13 accepted answers, one duplicate, and three quarantined records. The quarantine reports reasons without copying rejected input values.

“Here is the report. CS101 has a 3.83 mean and 66.7 percent favorable, where favorable means four or five out of five. ENG201 sits exactly at the five-answer threshold, so it is visible. ART105 is below that threshold, so both its count and scores are hidden.

“Now I import the same file into a persistent database twice. The second call says replayed, and the response count stays unchanged. This is the useful engineering lesson: report trust depends on consistent ingestion rules and transaction boundaries, not just a chart. The code is small enough to trace from CSV validation through SQL aggregation to escaped HTML. It is a learning tool, and the suppression rule is not a privacy guarantee.”
