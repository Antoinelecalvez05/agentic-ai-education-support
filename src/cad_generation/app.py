import os
import streamlit as st
from orchestrator import CADPipeline


st.set_page_config(page_title="AI CAD Generator", layout="wide")

st.title("AI CAD Generator from Prompt, 2D Plan, and Excel")

st.write(
    "MVP test: you can generate a CAD model from a text prompt only. "
    "A 2D plan and Excel constraints are optional."
)

backend = st.selectbox(
    "CAD backend",
    ["freecad", "cadquery"],
    index=1,
    help=(
        "Choose FreeCAD if you want .FCStd + STEP output. "
        "Choose CadQuery if you want faster STEP-focused generation."
    ),
)

prompt = st.text_area(
    "Describe what you want to generate",
    placeholder=(
        "Example: Create a rectangular base plate 120 mm long, "
        "80 mm wide and 10 mm thick with four 8 mm through-holes "
        "and one central horizontal slot."
    ),
)

plan_file = st.file_uploader(
    "Upload a 2D plan (optional)",
    type=["png", "jpg", "jpeg", "pdf"],
)

excel_file = st.file_uploader(
    "Upload Excel constraints (optional)",
    type=["xlsx"],
)


def safe_read_text_file(path):
    if not path:
        return None

    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as file:
        return file.read()


def safe_read_binary_file(path):
    if not path:
        return None

    if not os.path.exists(path):
        return None

    with open(path, "rb") as file:
        return file.read()


def get_download_filename(path, fallback):
    if path:
        return os.path.basename(path)

    return fallback


def display_generation_result(result):
    """
    Displays all pipeline outputs in Streamlit.
    This function is separated from the button logic so that error handling
    stays clean and readable.
    """

    st.subheader("Status")
    st.write(result.get("status"))

    st.subheader("Selected Backend")
    st.write("Requested backend:", result.get("backend_requested"))
    st.write("Selected backend:", result.get("backend"))

    backend_warning = result.get("backend_warning")
    if backend_warning:
        st.warning(backend_warning)

    generation = result.get("generation", {})

    st.subheader("Generation Backend Debug")
    st.write("Generation backend:", generation.get("backend"))
    st.write("Generation filename:", generation.get("filename"))
    st.json(generation)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("OCR Result")
        st.json(result.get("ocr_result", {}))

        st.subheader("Geometry Result")
        st.json(result.get("geometry_result", {}))

    with col2:
        st.subheader("Excel Result")
        st.json(result.get("excel_result", {}))

        st.subheader("Validation")
        st.json(result.get("validation", {}))

    # ----------------------------------------------------
    # Repair History
    # ----------------------------------------------------
    st.subheader("Repair History")

    repair_history = result.get("repair_history", [])

    if repair_history:
        st.success(
            f"Repair loop used {len(repair_history)} attempt(s). "
            "The validator feedback was sent back to the AI for correction."
        )

        for repair in repair_history:
            attempt_number = repair.get("attempt", "?")

            with st.expander(f"Repair attempt {attempt_number}", expanded=True):
                st.write("Errors before repair:")
                st.json(repair.get("errors_before_repair", []))

                st.write("Valid after repair:")
                st.json(repair.get("valid_after_repair", False))

                st.write("Errors after repair:")
                st.json(repair.get("errors_after_repair", []))

        with st.expander("Full repair history JSON"):
            st.json(repair_history)

    else:
        st.info(
            "No repair was needed. The first CAD plan passed validation directly."
        )

    # ----------------------------------------------------
    # Canonical / CAD Plans
    # ----------------------------------------------------
    st.subheader("Canonical JSON")
    st.json(result.get("canonical_input", {}))

    st.subheader("Raw CAD Plan from Mistral")
    st.json(result.get("cad_plan", {}))

    st.subheader("Normalized CAD Plan")
    st.json(result.get("normalized_cad_plan", {}))

    # ----------------------------------------------------
    # Repair Notes from CAD Plan
    # ----------------------------------------------------
    normalized_cad_plan = result.get("normalized_cad_plan", {})
    repair_notes = normalized_cad_plan.get("repair_notes", [])

    if repair_notes:
        st.subheader("Repair Notes")

        for note in repair_notes:
            st.write(f"- {note}")

    # ----------------------------------------------------
    # Generated Model Summary
    # ----------------------------------------------------
    st.subheader("Generated Model Summary")

    model_summary = result.get("model_summary", {})

    if model_summary:
        readable_summary = model_summary.get("readable_summary", [])

        if readable_summary:
            for line in readable_summary:
                st.write(f"- {line}")
        else:
            st.info("Model summary exists, but no readable summary was generated.")

        with st.expander("Full model summary JSON"):
            st.json(model_summary)

    else:
        st.info("No model summary available.")

    # ----------------------------------------------------
    # Generation result
    # ----------------------------------------------------
    st.subheader("Generation Result")
    st.json(generation)

    if not generation:
        st.info("No generation result was returned.")
        return

    if generation.get("success") is False:
        st.error(generation.get("message", "CAD generation failed."))

        if generation.get("error"):
            with st.expander("Generation error"):
                st.code(str(generation.get("error")))

    selected_backend = result.get("backend", "freecad")

    script_path = generation.get("script_path")
    json_path = generation.get("json_path")
    fcstd_path = generation.get("fcstd_path")
    step_path = generation.get("step_path")

    # ----------------------------------------------------
    # Python script display/download
    # Works for both FreeCAD and CadQuery if the generator returns script_path.
    # ----------------------------------------------------
    script_content = safe_read_text_file(script_path)

    if script_content:
        if selected_backend == "cadquery":
            script_label = "Download CadQuery Python Script"
            script_file_name = get_download_filename(
                script_path,
                "generated_model_cq.py",
            )
            st.subheader("Generated CadQuery Python Script")
        else:
            script_label = "Download FreeCAD Python Script"
            script_file_name = get_download_filename(
                script_path,
                "generated_model.py",
            )
            st.subheader("Generated FreeCAD Python Script")

        st.code(script_content, language="python")

        st.download_button(
            label=script_label,
            data=script_content,
            file_name=script_file_name,
            mime="text/x-python",
        )

    # ----------------------------------------------------
    # CAD plan JSON download
    # Usually CadQuery returns generated_model_cq_cad_plan.json.
    # FreeCAD may return generated_model_cad_plan.json if implemented.
    # ----------------------------------------------------
    json_content = safe_read_text_file(json_path)

    if json_content:
        if selected_backend == "cadquery":
            json_file_name = get_download_filename(
                json_path,
                "generated_model_cq_cad_plan.json",
            )
        else:
            json_file_name = get_download_filename(
                json_path,
                "generated_model_cad_plan.json",
            )

        st.download_button(
            label="Download CAD Plan JSON",
            data=json_content,
            file_name=json_file_name,
            mime="application/json",
        )

    # ----------------------------------------------------
    # FreeCAD .FCStd download
    # Only expected for FreeCAD backend.
    # ----------------------------------------------------
    fcstd_content = safe_read_binary_file(fcstd_path)

    if fcstd_content:
        st.download_button(
            label="Download FreeCAD Model (.FCStd)",
            data=fcstd_content,
            file_name=get_download_filename(
                fcstd_path,
                "generated_model.FCStd",
            ),
            mime="application/octet-stream",
        )

    elif selected_backend == "cadquery":
        st.info("CadQuery backend does not generate a .FCStd file. This is normal.")

    # ----------------------------------------------------
    # STEP download
    # FreeCAD: generated_model.step
    # CadQuery: generated_model_cq.step
    # ----------------------------------------------------
    step_content = safe_read_binary_file(step_path)

    if step_content:
        if selected_backend == "cadquery":
            step_file_name = get_download_filename(
                step_path,
                "generated_model_cq.step",
            )
        else:
            step_file_name = get_download_filename(
                step_path,
                "generated_model.step",
            )

        st.download_button(
            label="Download STEP File (.step)",
            data=step_content,
            file_name=step_file_name,
            mime="application/step",
        )


if st.button("Generate"):
    if not prompt.strip():
        st.error("Please write a prompt.")

    else:
        with st.spinner(f"Generating CAD model with {backend} backend..."):
            try:
                pipeline = CADPipeline(backend=backend)

                result = pipeline.run(
                    prompt=prompt,
                    plan_file=plan_file,
                    excel_file=excel_file,
                    backend=backend,
                )

            except RuntimeError as error:
                error_message = str(error)

                if (
                    "429" in error_message
                    or "capacity" in error_message.lower()
                    or "service_tier_capacity_exceeded" in error_message
                ):
                    st.error(
                        "Mistral is currently refusing the request because the selected "
                        "model has reached capacity for your service tier."
                    )

                    st.warning(
                        "This is not a FreeCAD or CadQuery problem and not necessarily "
                        "a bug in your CAD code. The AI model call failed before the CAD "
                        "plan could be generated."
                    )

                    st.info(
                        "Try again later, change the Mistral model in your .env file, "
                        "or temporarily reduce repair attempts while testing."
                    )

                    with st.expander("Full technical error"):
                        st.code(error_message)

                else:
                    st.error("A runtime error occurred during generation.")

                    with st.expander("Full technical error"):
                        st.code(error_message)

                st.stop()

            except ValueError as error:
                st.error("A value error occurred during generation.")

                with st.expander("Full technical error"):
                    st.code(str(error))

                st.stop()

            except Exception as error:
                st.error("Unexpected error during generation.")

                with st.expander("Full technical error"):
                    st.code(str(error))

                st.stop()

        display_generation_result(result)