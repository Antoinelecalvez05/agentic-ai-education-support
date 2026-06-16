# Feedback, OCR and Grading Support System

This document describes the feedback and grading-support module of the `agentic-ai-education-support` project.

The module is located under:

```text
src/feedback_grading/
```

It is designed to support lecturers with OCR-assisted ingestion of assessment documents, AI-based rubric extraction, AI-based copy parsing, indicative grading, personalised feedback generation, and consistency comparison across anonymised corrected copies.

The system is not intended to replace lecturers. It is a lecturer-support tool where human validation remains mandatory.

---

## Purpose

In higher education, lecturers often need to provide feedback to large numbers of students while maintaining fairness, consistency, and pedagogical quality.

This module explores how AI can support that process by:

* extracting marking schemes from uploaded or scanned documents
* converting marking schemes into structured rubrics
* processing corrected reference copies
* extracting student answers, teacher comments, correction marks, and scores
* processing new student submissions
* generating indicative scores and feedback
* comparing new answers with previous anonymised corrected answers
* helping lecturers identify possible consistency issues

The final academic decision always remains with the lecturer.

## High-Level Workflow

```text
Marking scheme document
        ↓
OCR extraction if needed
        ↓
AI rubric parsing
        ↓
Lecturer validation

Corrected reference copies
        ↓
OCR extraction
        ↓
AI extraction of answer, score, comments
        ↓
Lecturer validation

New student copies
        ↓
OCR extraction
        ↓
AI extraction of student answer
        ↓
Lecturer validation

Validated rubric
+ validated reference copies
+ validated new submissions
        ↓
Batch grading and comparison pipeline
        ↓
Indicative feedback reports
        ↓
Lecturer review and final decision
```

## Main Components

### `streamlit_app.py`

Provides the graphical interface for the lecturer-supervised workflow.

It supports:

* marking scheme upload or manual input
* OCR extraction from documents
* AI rubric generation
* rubric validation
* upload of corrected reference copies
* OCR and AI extraction from corrected copies
* upload of new student submissions
* batch analysis
* export of JSON, CSV, and Markdown reports

---

### `mistral_client.py`

Centralises Mistral client creation.

It loads credentials and model names from environment variables.

Expected `.env` values:

```text
MISTRAL_API_KEY=...
MISTRAL_TEXT_MODEL=...
MISTRAL_OCR_MODEL=...
```

The `.env` file must never be committed to GitHub.

---

### `ocr_extractor.py`

Handles OCR-based document ingestion.

It is intended to extract text from:

* scanned marking schemes
* corrected student copies
* new student submissions
* PDF files
* image files

The OCR output is treated as a draft and must be reviewed before use.

---

### `rubric_ai_parser.py`

Uses a Mistral text model to convert raw marking scheme text into structured rubric JSON.

The generated rubric may include:

* assignment ID
* question
* criteria
* maximum points
* expected elements
* common errors
* feedback guidance

The generated rubric must be validated by a lecturer before being used in the grading pipeline.

---

### `copy_ai_parser.py`

Uses a Mistral text model to structure OCR output from student copies.

It supports two main modes:

#### Corrected Reference Copy Mode

Extracts:

* copy ID
* student answer
* detected score
* maximum score
* grader ID
* teacher comment
* correction marks
* uncertainties

#### New Student Submission Mode

Extracts:

* student ID
* student answer
* metadata
* uncertainties

If information is unclear, the parser should not invent it. Instead, it should add an uncertainty that can be reviewed by the lecturer.

---

### `schemas.py`

Defines the structured data models used across the module, such as:

* rubric
* criteria
* student submission
* previous graded answer

These schemas help keep AI outputs controlled and auditable.

---

### `grading_engine.py`

Evaluates a student answer against a validated rubric.

It produces:

* criterion-by-criterion evaluation
* indicative score
* percentage
* explanation of matched and missing elements

The score is indicative only.

---

### `comparison_engine.py`

Compares a new student answer with previous anonymised corrected copies.

It supports:

* finding similar previous answers
* comparing indicative scores with historical corrected scores
* identifying possible grading consistency issues
* providing a fairness reference for lecturer review

The comparison result is not an automatic decision.

---

### `report_generator.py`

Generates Markdown reports for lecturer review.

Reports may include:

* student ID
* indicative score
* criterion-level feedback
* missing elements
* similar-copy comparison
* consistency reference
* warnings and uncertainties

---

### `pipeline.py`

Connects the full backend workflow.

It combines:

* rubric
* student submission
* previous corrected answers
* grading engine
* comparison engine
* report generation
* structured output generation

---

## OCR and Handwriting Limitations

OCR extraction can be unreliable when documents contain:

* handwriting
* crossed-out text
* poor scans
* low-resolution photos
* unusual layouts
* teacher annotations written in the margins
* unclear scores

For this reason, OCR output is always treated as a draft.

The lecturer must review and validate:

* extracted marking scheme text
* generated rubric
* extracted student answers
* detected scores
* extracted teacher comments
* uncertainties raised by the AI parser

---

## Academic Integrity and Safety Principles

The module follows these principles:

### Lecturer validation is mandatory

The system does not make final grading decisions.

### Indicative scores only

Scores are generated as references for lecturer review, not as official grades.

### Anonymised data

Student copies should be anonymised before processing.

### No blind automation

AI outputs must be inspected before being used.

### Traceable workflow

Rubrics, extracted data, feedback, and exports should be inspectable and auditable.

---

## Example Use Case

A lecturer wants to grade an engineering question about Ohm’s Law.

The system can:

1. extract the official marking scheme from a PDF
2. convert it into a structured rubric
3. allow the lecturer to validate the rubric
4. process previous corrected copies
5. extract student answers, comments, and scores
6. process new student submissions
7. generate indicative scores and feedback
8. compare answers with similar corrected copies
9. export reports for lecturer review

---

## Running the Streamlit Interface

From the repository root:

```bash
streamlit run src/feedback_grading/streamlit_app.py
```

---

## Testing

Recommended testing should include:

* clean typed marking schemes
* scanned marking schemes
* corrected reference copies with comments and scores
* new uncorrected submissions
* OCR stress tests with unclear layout or handwriting-style annotations
* direct JSON upload tests

Test documents can be stored under:

```text
test_documents/
```

All test data should be fictional and anonymised.

---

## Current Status

This module is an active prototype.

It currently demonstrates the architecture and first implementation of an OCR-assisted, AI-supported feedback and grading workflow.

Future improvements may include:

* stronger OCR validation
* better handwritten text handling
* improved uncertainty detection
* full RAG integration
* better cross-grader consistency analysis
* support for additional assessment formats
* deeper integration with engineering tools such as CAD and LTSpice
