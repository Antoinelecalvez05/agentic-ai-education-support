# CAD Generation Prototype

`cad-ai-prototype` is an AI-assisted CAD generation prototype. Its goal is to convert different types of design intent into structured CAD models.

The system is designed to accept natural language descriptions of mechanical parts or assemblies, and to progressively support additional input types such as hand-drawn sketches, uploaded 2D plans, OCR-extracted text, geometry extraction, and Excel-based design constraints.

The project uses an AI planning pipeline to transform incomplete or messy inputs into a validated CAD plan, then generates CAD models through FreeCAD or CadQuery.

This is an active prototype, not a finished industrial CAD product.

## Project Vision

The long-term vision is to support:

* natural language to CAD
* hand-drawn sketch to CAD
* 2D technical drawing to CAD
* Excel constraints to CAD
* AI-assisted validation and repair
* automatic STEP generation for parts and assemblies

Hand-drawn sketch support, OCR interpretation, and geometry extraction are part of the intended pipeline, but may still be experimental depending on the current implementation.

## Current Pipeline

The intended pipeline is:

```text
User prompt
+ optional hand-drawn sketch / 2D plan
+ optional OCR extraction
+ optional geometry extraction
+ optional Excel constraints
        ↓
aggregator.py
        ↓
normalizer.py
        ↓
validator.py
        ↓
mistral_agent.py
        ↓
AI CAD planning
        ↓
validation
        ↓
AI repair / verification loop if the CAD plan is invalid
        ↓
orchestrator.py
        ↓
CAD backend
        ↓
generated Python CAD script
        ↓
STEP / FCStd output
```

## Main AI Components

The system uses an AI planning and validation loop.

* Mistral is used as the CAD planning agent.
* The system prompt converts user intent into structured JSON CAD plans.
* The normalizer cleans and canonicalizes operations.
* The validator checks schema, dimensions, targets, positions, patterns, rotations, and assembly structure.
* A repair loop can send validation errors back to the AI so that it can correct the CAD plan.
* This creates an AI verification loop before CAD generation.

## Supported or Planned Inputs

* Natural language prompts
* Uploaded 2D plans
* Hand-drawn sketches
* OCR-extracted text
* Geometry extraction from drawings
* Excel constraints

## CAD Backends

### 1. FreeCAD backend

The FreeCAD backend is designed to:

* generate FreeCAD Python scripts
* export `.FCStd` files
* export STEP files

### 2. CadQuery backend

The CadQuery backend is the main backend currently used.

It is designed to:

* generate CadQuery Python scripts
* export STEP files
* support regression testing more easily
* support single parts and multi-part assemblies

## Current CadQuery Features

The current CadQuery implementation supports:

* basic solids: boxes, cylinders, rounded rectangle plates
* simple holes
* threaded holes
* counterbore holes
* countersink holes
* slots and rectangular cutouts
* rectangular and circular pockets
* bosses and cylindrical bosses
* mounting standoffs
* holes on bosses
* ribs and gussets
* raised borders
* open enclosures and lids
* recesses
* linear patterns
* circular patterns
* mirror features
* fillets and chamfers
* multi-part assemblies
* STEP export for the full assembly
* separate STEP export for each individual part
* real rotations in assembly placements
* smart placement rules such as `on_top_of`, `under`, `right_of`, `left_of`, `behind`, `in_front_of`, `centered_on`, `flush_top`, and `flush_bottom`
* offset reference rules for smarter local placement

## Supported CAD Plan Formats

### Single-part format

```json
{
  "units": "mm",
  "steps": [
    {
      "operation": "create_box",
      "name": "base_plate",
      "length": 120,
      "width": 80,
      "height": 10,
      "position": [0, 0, 0]
    }
  ],
  "assumptions": [],
  "missing_information": []
}
```

### Multi-part assembly format

```json
{
  "units": "mm",
  "parts": [
    {
      "name": "body",
      "steps": []
    },
    {
      "name": "lid",
      "steps": []
    }
  ],
  "assembly": [
    {
      "part": "body",
      "position": [0, 0, 0],
      "rotation": [0, 0, 0]
    },
    {
      "part": "lid",
      "place": "on_top_of",
      "target": "body",
      "clearance": 2,
      "rotation": [0, 0, 0]
    }
  ],
  "assumptions": [],
  "missing_information": []
}
```

## Installation

Create and activate a Python virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Depending on the backend used, FreeCAD, CadQuery, or additional CAD-related dependencies may need to be installed separately.

## Running the Streamlit App

If the Streamlit interface is available in the current implementation, run:

```bash
streamlit run app.py
```

## Running Regression Tests

The CadQuery regression test suite is located in:

```text
tests/cad_plans
```

The test runner is:

```bash
python tests/run_cadquery_regression_tests.py
```

At the current stage, 20 regression tests pass, covering:

* basic plates
* holes
* slots
* counterbores
* countersinks
* pockets
* bosses
* standoffs
* ribs
* gussets
* raised borders
* mirror features
* open enclosures
* lids
* multi-part assemblies
* separate part exports
* rotations
* smart placements

## Output Files

The project can generate:

* `.step` files for CAD exchange
* `.FCStd` files when using the FreeCAD backend
* generated Python CAD scripts
* separate STEP exports for individual parts
* global STEP exports for assemblies

Generated output files are usually excluded from version control unless they are intentionally included as examples.

## Project Milestones

* V1: natural language to simple single-part CAD
* V2: advanced CadQuery operations and regression tests
* V3: multi-part assembly support
* V4: global STEP assembly and separate STEP files by part
* V5: real rotations in assemblies
* V6: smart placement rules for assemblies
* V6.1: improved `offset_reference` for local smart placement
* Future: improved hand-drawn sketch understanding and more robust OCR / geometry extraction

## Limitations

This project is still experimental.

Current limitations may include:

* incomplete hand-drawn sketch interpretation
* experimental OCR and geometry extraction
* limited robustness for ambiguous prompts
* possible failure cases in complex assemblies
* no guarantee of manufacturability
* no replacement for professional mechanical design validation

## Example Prompts

```text
Create a rectangular base plate 120 mm long, 80 mm wide, and 10 mm thick, with four mounting holes in the corners.
```

```text
Create an open electronics enclosure with a removable lid, internal standoffs, and screw holes.
```

```text
Generate a two-part assembly with a base and a cover placed on top with 2 mm clearance.
```

## License

License to be added.
