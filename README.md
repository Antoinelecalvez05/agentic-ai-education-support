# Agentic AI for Feedback and Learning Support

This repository documents and implements an independent agentic AI project focused on feedback, assessment support, OCR-assisted document ingestion, and technical learning in higher education.

The project was initially developed around the Ireland Quest context. It explores how AI could support lecturers and students in environments where increasing student numbers and limited academic staffing reduce the time available for personalised feedback and technical guidance.

The objective is not to replace lecturers or automate academic decisions. The system is designed as a human-in-the-loop support tool where lecturers remain responsible for all final assessment, feedback, and instructional decisions.

## Project Vision

The long-term vision is to build a controlled agentic AI system that can support two complementary use cases:

### 1. Feedback and Grading Support

The feedback and grading module aims to help lecturers:

* analyse marking schemes and corrected student work
* extract rubric criteria from lecturer-verified documents
* process scanned or uploaded student copies using OCR
* extract student answers, teacher annotations, scores, and comments
* compare new student answers against previous anonymised corrected copies
* generate structured feedback reports
* provide indicative grading references for lecturer review
* support consistency across multiple examiners

The system does not generate final grades automatically. Scores are indicative only and require lecturer validation.

### 2. Technical Learning Support

The technical learning-support module explores how AI can help students understand engineering software workflows without giving direct answers to assessed work.

It can support:

* analogous CAD or circuit simulation demonstrations
* project-based learning explanations
* structured technical artefacts such as CAD plans, scripts, and generated models
* learning guidance for engineering tools and workflows

## Current Repository Status

This repository now contains both conceptual documentation and implemented prototype code.

### Currently Implemented

#### Feedback, OCR and Grading Support

Implemented under:

```text
src/feedback_grading/
```

Current features include:

* Streamlit interface for lecturer-supervised workflow
* marking scheme input through text, JSON, and OCR-supported documents
* Mistral OCR integration for scanned marking schemes and student copies
* AI-based rubric extraction from raw marking scheme text
* AI-based extraction of student answers, teacher comments, detected scores, and correction marks
* manual validation of extracted OCR/AI outputs
* batch processing of multiple new student submissions
* criterion-by-criterion indicative grading
* comparison with anonymised previously corrected reference copies
* fairness and consistency reference across similar answers
* Markdown, JSON, and CSV export options

#### CAD / 3D Generation Prototype

Implemented under:

```text
src/cad_generation/
```

Current features include:

* structured CAD planning workflow
* CadQuery-based generation backend
* STEP export for generated parts and assemblies
* support for single-part and multi-part assemblies
* validation-oriented CAD generation
* regression tests for CAD generation features

## Feedback and Grading Workflow

The feedback and grading-support module follows this workflow:

```text
Official marking scheme / scanned rubric
        ↓
OCR extraction if needed
        ↓
AI parsing into structured rubric JSON
        ↓
Lecturer validates rubric

Corrected reference copies
        ↓
OCR extraction
        ↓
AI extraction of student answer, score, teacher comment
        ↓
Lecturer validates extracted data

New student submissions
        ↓
OCR extraction
        ↓
AI extraction of student answer
        ↓
Lecturer validates extracted answer

Validated rubric
+ validated corrected reference copies
+ validated new submissions
        ↓
Batch feedback and grading-support pipeline
        ↓
Indicative scores, feedback reports, similar-copy comparison
        ↓
Lecturer review and final academic decision
```

## Repository Structure

```text
agentic-ai-education-support/
│
├── README.md
├── requirements.txt
├── .gitignore
│
├── feedback_agent_pseudocode.md
├── learning_support_agent_pseudocode.md
├── sample_feedback_output.md
│
├── docs/
│   ├── project_brief.md
│   └── feedback_grading_system.md
│
└── src/
    ├── cad_generation/
    │   ├── README.md
    │   ├── app.py
    │   ├── orchestrator.py
    │   ├── schemas/
    │   ├── core/
    │   ├── cad/
    │   ├── extractors/
    │   └── tests/
    │
    └── feedback_grading/
        ├── streamlit_app.py
        ├── mistral_client.py
        ├── ocr_extractor.py
        ├── rubric_ai_parser.py
        ├── copy_ai_parser.py
        ├── schemas.py
        ├── grading_engine.py
        ├── comparison_engine.py
        ├── report_generator.py
        ├── pipeline.py
        ├── run_pipeline.py
        ├── run_rubric_parser.py
        └── examples/
```

## Running the Feedback and Grading App

From the repository root:

```bash
streamlit run src/feedback_grading/streamlit_app.py
```

The app supports:

1. marking scheme upload or text input
2. OCR extraction where applicable
3. AI rubric parsing
4. lecturer validation of the rubric
5. upload of corrected reference copies
6. OCR and AI extraction of answers, scores, and comments
7. upload of new student submissions
8. batch feedback and grading-support analysis
9. export of reports and structured results

## Design Principles

The project follows four main principles:

### Human-in-the-loop control

Lecturers remain responsible for all academic decisions.

### Structured outputs

AI-generated actions should be represented in controlled formats such as JSON plans, structured rubrics, and auditable reports.

### Validation before execution

Generated plans, rubrics, OCR outputs, and grading references should be checked before being used.

### Learning support without direct answer generation

The system should generate analogous demonstrations and explanations rather than solving assessed student projects directly.

## Important Limitations

This is an active prototype.

The feedback and grading module should not be understood as a deployed AI grading system. OCR and handwriting extraction may contain errors, especially when documents are scanned, handwritten, crossed out, or poorly formatted.

AI-generated rubric extraction and copy parsing are treated as drafts only.

The system produces indicative scores and feedback suggestions for lecturer review. It does not replace academic judgement and does not produce final grades automatically.

## Documentation

More detailed documentation is available in:

* `docs/project_brief.md` — full project brief and educational rationale
* `docs/feedback_grading_system.md` — detailed feedback, OCR, and grading-support workflow
* `src/cad_generation/README.md` — technical documentation for the CAD generation prototype

## Current Status

This repository combines:

* implemented prototype code
* OCR and AI-based feedback/grading support workflow
* CAD generation prototype
* system design documentation
* exploratory research notes
* future development roadmap

It is intended as a research and prototyping project, not as a final production system.

## License

License to be added.
