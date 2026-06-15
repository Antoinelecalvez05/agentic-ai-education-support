from pathlib import Path
import json
import sys
import traceback


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CAD_PLANS_DIR = Path(__file__).resolve().parent / "cad_plans"
OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from cad.cadquery_generator import CadQueryGenerator


def safe_test_name(path):
    stem = path.stem.lower()
    safe = []

    for char in stem:
        if char.isalnum() or char in {"_", "-"}:
            safe.append(char)
        else:
            safe.append("_")

    return "".join(safe)


def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def generation_succeeded(result):
    """
    Preferred contract:
    - result["success"] is True

    Backward-compatible fallback:
    - older generators may return status="generated" without success.
    """
    if result.get("success") is True:
        return True

    if result.get("status") == "generated":
        result["success"] = True
        return True

    return False


def get_step_path(result):
    step_path = result.get("step_path")

    if step_path:
        return Path(step_path)

    file_check = result.get("file_check", {})
    expected = file_check.get("expected_step_path") or file_check.get("step_path")

    if expected:
        return Path(expected)

    return None


def run_one_test(generator, json_path):
    cad_plan = load_json(json_path)
    filename = safe_test_name(json_path)

    result = generator.generate(
        cad_plan=cad_plan,
        filename=filename,
    )

    if result is None:
        result = {}

    success = generation_succeeded(result)
    step_path = get_step_path(result)
    step_exists = bool(step_path and step_path.exists())

    passed = success and step_exists

    return {
        "test": json_path.name,
        "passed": passed,
        "success": success,
        "step_exists": step_exists,
        "step_path": str(step_path) if step_path else None,
        "result": result,
    }


def print_result_table(results):
    print("")
    print("CadQuery regression test results")
    print("=" * 80)
    print(f"{'TEST':45} {'SUCCESS':8} {'STEP':8} {'STATUS'}")
    print("-" * 80)

    for item in results:
        status = "PASS" if item["passed"] else "FAIL"
        success_text = "yes" if item["success"] else "no"
        step_text = "yes" if item["step_exists"] else "no"

        print(
            f"{item['test'][:45]:45} "
            f"{success_text:8} "
            f"{step_text:8} "
            f"{status}"
        )

    print("=" * 80)
    print("")


def print_failures(results):
    failed = [item for item in results if not item["passed"]]

    if not failed:
        return

    print("")
    print("Failed test details")
    print("=" * 80)

    for item in failed:
        result = item.get("result", {})
        execution = result.get("execution", {})

        print("")
        print(f"TEST: {item['test']}")
        print(f"STEP PATH: {item.get('step_path')}")
        print(f"RESULT STATUS: {result.get('status')}")
        print(f"RESULT SUCCESS: {result.get('success')}")

        error = result.get("error") or execution.get("error")
        if error:
            print("")
            print("ERROR:")
            print(error)

        stdout = execution.get("stdout")
        if stdout:
            print("")
            print("STDOUT:")
            print(stdout)

        stderr = execution.get("stderr")
        if stderr:
            print("")
            print("STDERR:")
            print(stderr)

        tb = result.get("traceback") or execution.get("traceback")
        if tb:
            print("")
            print("TRACEBACK:")
            print(tb)

        print("-" * 80)


def main():
    if not CAD_PLANS_DIR.exists():
        print(f"Missing CAD plan directory: {CAD_PLANS_DIR}")
        return 1

    json_files = sorted(CAD_PLANS_DIR.glob("*.json"))

    if not json_files:
        print(f"No JSON regression plans found in: {CAD_PLANS_DIR}")
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    generator = CadQueryGenerator(output_dir=OUTPUT_DIR)

    results = []

    for json_path in json_files:
        try:
            result = run_one_test(generator, json_path)
        except Exception as error:
            result = {
                "test": json_path.name,
                "passed": False,
                "success": False,
                "step_exists": False,
                "step_path": None,
                "result": {
                    "status": "runner_exception",
                    "success": False,
                    "error": str(error),
                    "traceback": traceback.format_exc(),
                },
            }

        results.append(result)

    print_result_table(results)
    print_failures(results)

    all_passed = all(item["passed"] for item in results)

    if all_passed:
        print("All CadQuery regression tests passed.")
        return 0

    print("One or more CadQuery regression tests failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())