# Agentic AI for Feedback and Learning Support

This repository documents an independent agentic AI project focused on feedback, assessment support, and technical learning in higher education.

The project was initially developed around the Ireland Quest context. It explores how AI could support lecturers and students in environments where increasing student numbers and limited academic staffing reduce the time available for personalised feedback and technical guidance.

The objective is not to replace lecturers or automate academic decisions. The system is designed as a human-in-the-loop support tool where lecturers remain responsible for all final assessment, feedback, and instructional decisions.

## Project Vision

The long-term vision is to build a controlled agentic AI system that can support two complementary use cases:

1. **Feedback and grading support**

   * analyse corrected student work
   * compare answers against lecturer-verified marking schemes
   * generate structured personalised feedback
   * provide indicative grading references for lecturers
   * support consistency across multiple examiners

2. **Technical learning support**

   * help students understand engineering software workflows
   * generate analogous CAD or circuit simulation demonstrations
   * support project-based learning without giving direct solutions to assessed work
   * produce structured technical artefacts such as CAD plans, scripts, and generated models

## Current Repository Status

This repository contains both conceptual documentation and implemented prototype code.

### Currently implemented

* CAD / 3D generation prototype under `src/cad_generation`
* Structured CAD planning workflow
* CadQuery-based generation backend
* STEP export for generated parts and assemblies
* Regression tests for CAD generation features
* Conceptual pseudocode for feedback and learning-support agents
* Sample simulated feedback output

### Conceptual or in progress

* Full feedback generation agent
* RAG-based feedback grounded in lecturer-validated marking schemes
* Cross-grader comparison workflow
* End-to-end grading support pipeline
* LTSpice learning-support demonstrations
* Complete lecturer-supervised workflow

## Repository Structure

```text
agentic-ai-education-support/
│
├── README.md
├── feedback_agent_pseudocode.md
├── learning_support_agent_pseudocode.md
├── sample_feedback_output.md
│
├── docs/
│   ├── project_brief.md
│   └── feedback_grading_system.md
│
└── src/
    └── cad_generation/
        ├── README.md
        ├── app.py
        ├── orchestrator.py
        ├── requirements.txt
        ├── schemas/
        ├── core/
        ├── cad/
        ├── extractors/
        └── tests/
```

## Design Principles

The project follows four main principles:

1. **Human-in-the-loop control**
   Lecturers remain responsible for all academic decisions.

2. **Structured outputs**
   AI-generated actions should be represented in controlled formats such as JSON plans rather than free text alone.

3. **Validation before execution**
   Generated plans should be checked before being passed to external tools.

4. **Learning support without direct answer generation**
   The system should generate analogous demonstrations and explanations rather than solving assessed student projects directly.

## Main Technical Module: CAD Generation

The most developed implemented component is the CAD / 3D generation prototype located in:

```text
src/cad_generation/
```

This module explores how natural language, structured design constraints, OCR, geometry extraction, and Excel-based inputs could be converted into validated CAD plans and then into generated CAD models.

The current implementation focuses mainly on CadQuery-based generation and STEP export.

## Documentation

More detailed documentation is available in:

* `docs/project_brief.md` — full project brief and educational rationale
* `docs/feedback_grading_system.md` — planned feedback and grading support workflow
* `src/cad_generation/README.md` — technical documentation for the CAD generation prototype

## Current Status

This is an active prototype.

It should not be understood as a finished industrial CAD product or a deployed AI grading system. The repository currently combines:

* implemented prototype code,
* system design documentation,
* exploratory research notes,
* future development roadmap.

## License

License to be added.
