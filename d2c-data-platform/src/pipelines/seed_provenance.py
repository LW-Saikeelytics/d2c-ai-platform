
import ast
import json

from .pipeline_logger import ROOT
from .reproducibility_baseline import (
    BASELINE_PATH,
    build_baseline,
    sha256_file
)


SOURCE = ROOT.parent / "d2c-synthetic-data" / "simulation"

REPORT = ROOT / "reports" / "seed_provenance.json"

ENGINE_FILES = {
    "CustomerEngine": "customer_engine.py",
    "EventEngine": "event_engine.py",
    "BehaviorEngine": "behavior_engine.py",
    "ConversionEngine": "conversion_engine.py",
    "OrderEngine": "order_engine.py"
}


def parse_source(path):
    if not path.is_file():
        raise RuntimeError(f"Missing generator file: {path}")

    return ast.parse(
        path.read_text(encoding="utf-8")
    )


def matches_expression(actual, expected_text):
    expected = ast.parse(
        expected_text, mode="eval"
    ).body

    return ast.dump(
        actual, include_attributes=False
    ) == ast.dump(
        expected, include_attributes=False
    )


def check_rng(tree, class_name, attribute, expression):

    classes = [
        node for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == class_name
    ]

    if len(classes) != 1:
        raise RuntimeError(
            f"Missing or ambiguous class: {class_name}"
        )

    initializers = [
        node for node in classes[0].body
        if isinstance(node, ast.FunctionDef)
        and node.name == "__init__"
    ]

    if len(initializers) != 1:
        raise RuntimeError(
            f"Missing initializer: {class_name}"
        )

    for node in ast.walk(initializers[0]):

        if not isinstance(node, ast.Assign):
            continue

        targets = [
            target for target in node.targets
            if isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "self"
            and target.attr == attribute
        ]

        if not targets:
            continue

        value = node.value

        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and isinstance(value.func.value, ast.Name)
            and value.func.value.id == "random"
            and value.func.attr == "Random"
            and len(value.args) == 1
            and matches_expression(
                value.args[0], expression
            )
        ):
            return

    raise RuntimeError(
        f"Unexpected RNG wiring: "
        f"{class_name}.{attribute}"
    )


def check_runner_seed(tree, class_name, expected_seed):

    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == class_name
    ]

    if len(calls) != 1:
        raise RuntimeError(
            f"Expected one {class_name} initialization"
        )

    seed_arguments = [
        keyword.value
        for keyword in calls[0].keywords
        if keyword.arg == "seed"
    ]

    if expected_seed is None:
        if seed_arguments:
            raise RuntimeError(
                f"Unexpected {class_name} seed argument"
            )
    elif (
        len(seed_arguments) != 1
        or not matches_expression(
            seed_arguments[0], str(expected_seed)
        )
    ):
        raise RuntimeError(
            f"Unexpected production seed for {class_name}"
        )


def main():

    print("=" * 70)
    print("PHASE 8 - SEED PROVENANCE VALIDATION")
    print("=" * 70)

    # Confirm that tracked platform inputs
    # still match the immutable baseline.

    if not BASELINE_PATH.is_file():
        raise RuntimeError(
            "Run reproducibility_baseline first"
        )

    saved_baseline = json.loads(
        BASELINE_PATH.read_text(encoding="utf-8")
    )

    current_baseline = build_baseline()

    if saved_baseline != current_baseline:
        raise RuntimeError(
            "Source/configuration baseline changed"
        )

    runner_path = SOURCE / "production_dataset_runner.py"
    runner_tree = parse_source(runner_path)

    source_paths = [runner_path]

    # Verify the four explicitly seeded engines.

    for class_name, filename in ENGINE_FILES.items():

        path = SOURCE / filename
        tree = parse_source(path)
        source_paths.append(path)

        if class_name == "OrderEngine":
            check_runner_seed(
                runner_tree, class_name, None
            )
            check_rng(
                tree, class_name, "random", "42"
            )
        else:
            check_runner_seed(
                runner_tree, class_name, 42
            )
            check_rng(
                tree, class_name, "random", "seed"
            )

        print(f"{class_name}: PASS")

    # Customer profiles use a dedicated
    # seed-offset random stream.

    customer_tree = parse_source(
        SOURCE / "customer_engine.py"
    )

    check_rng(
        customer_tree,
        "CustomerEngine",
        "profile_random",
        "seed + 101"
    )

    print("Customer profile RNG offset (+101): PASS")

    # Preserve a deterministic source fingerprint.
    # No timestamps or machine-specific paths.

    source_hashes = {
        path.relative_to(ROOT.parent).as_posix():
            sha256_file(path)
        for path in source_paths
    }

    provenance = {
        "version": 1,
        "source_run_id": current_baseline["run_id"],
        "input_fingerprint_sha256":
            current_baseline["fingerprint_sha256"],
        "production_base_seed": 42,
        "engine_seeds": {
            "customer": 42,
            "event": 42,
            "behavior": 42,
            "conversion": 42,
            "order": 42,
            "customer_profile": 143
        },
        "order_seed_hardcoded": True,
        "verification_scope": "static_seed_wiring",
        "generator_source_sha256": source_hashes
    }

    REPORT.parent.mkdir(
        parents=True, exist_ok=True
    )

    if REPORT.exists():

        saved = json.loads(
            REPORT.read_text(encoding="utf-8")
        )

        if saved != provenance:
            raise RuntimeError(
                "Seed provenance changed. "
                "Existing report preserved."
            )

        status = "MATCHED"

    else:

        with REPORT.open(
            "x", encoding="utf-8"
        ) as file:
            json.dump(
                provenance,
                file,
                indent=2,
                sort_keys=True
            )

        status = "CREATED"

    print(f"Input baseline: MATCHED")
    print(f"Production base seed: 42")
    print(f"Customer profile seed: 143")
    print(f"Generator source files tracked: 6")
    print(f"Seed provenance status: {status}")
    print(f"Report: {REPORT}")

    print()
    print("SEED PROVENANCE VALIDATION PASSED.")


if __name__ == "__main__":
    main()
