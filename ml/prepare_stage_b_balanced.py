"""Prepare an auditable Stage B-only augmented training split.

Original train/validation/test CSVs are read-only inputs. The output contains
only the original Stage B training rows plus curated short examples.
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

ML_DIR = Path(__file__).resolve().parent
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

from config import LABEL_TO_NAME, TEST_CSV, TRAIN_CSV, VALIDATION_CSV

OUTPUT_DIR = Path(__file__).resolve().parent / "data" / "stage_b_balanced"
CURATED_CSV = OUTPUT_DIR / "curated_short_examples.csv"
TRAIN_OUTPUT = OUTPUT_DIR / "train.csv"
REPORT_OUTPUT = OUTPUT_DIR / "report.txt"
STAGE_B_NAMES = ("lexical", "syntactic", "semantic", "syntax", "pragmatic")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text.lower())).strip()


def bucket(text: str) -> str:
    count = len(text.split())
    if count <= 5:
        return "<=5"
    if count <= 15:
        return "6-15"
    return ">15"


def stage_b_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if int(row["label"]) != 6]


def write_rows(rows: list[dict[str, str]]) -> None:
    with TRAIN_OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["requirement", "label"])
        writer.writeheader()
        writer.writerows({"requirement": row["requirement"], "label": row["label"]} for row in rows)


def main() -> None:
    original = stage_b_rows(read_csv(TRAIN_CSV))
    curated = read_csv(CURATED_CSV)
    validation = read_csv(VALIDATION_CSV)
    test = read_csv(TEST_CSV)

    if any(int(row["label"]) == 6 for row in curated):
        raise ValueError("Curated Stage B examples must not contain clean labels.")
    if len(curated) != 40:
        raise ValueError(f"Expected 40 curated examples, found {len(curated)}.")

    original_keys = {normalize(row["requirement"]) for row in original}
    heldout_keys = {
        normalize(row["requirement"])
        for row in [*validation, *test]
    }
    curated_keys = [normalize(row["requirement"]) for row in curated]
    exact_training_duplicates = [key for key, count in Counter(curated_keys).items() if count > 1]
    exact_heldout_leakage = sorted(set(curated_keys) & heldout_keys)
    near_matches: list[tuple[float, str, str]] = []
    heldout_texts = [normalize(row["requirement"]) for row in [*validation, *test]]
    for row in curated:
        source = normalize(row["requirement"])
        for target in heldout_texts:
            ratio = SequenceMatcher(None, source, target).ratio()
            if ratio >= 0.92:
                near_matches.append((ratio, source, target))

    final_rows = [*original, *({"requirement": row["requirement"], "label": row["label"]} for row in curated)]
    write_rows(final_rows)

    lines = [
        "Stage B balanced training-data report",
        f"Original Stage B training rows: {len(original)}",
        f"Curated rows added: {len(curated)}",
        f"Final Stage B training rows: {len(final_rows)}",
        "",
        "Class counts by length bucket:",
    ]
    for length_bucket in ("<=5", "6-15", ">15"):
        counts = Counter(
            LABEL_TO_NAME[int(row["label"])]
            for row in final_rows
            if bucket(row["requirement"]) == length_bucket
        )
        lines.append(f"{length_bucket}: " + ", ".join(f"{name}={counts[name]}" for name in STAGE_B_NAMES))
    lines.extend(
        [
            "",
            "Final class counts:",
            ", ".join(
                f"{name}={sum(LABEL_TO_NAME[int(row['label'])] == name for row in final_rows)}"
                for name in STAGE_B_NAMES
            ),
            "",
            f"Exact duplicate curated groups: {len(exact_training_duplicates)}",
            f"Exact leakage with validation/test: {len(exact_heldout_leakage)}",
            f"Near-match leakage at SequenceMatcher >= 0.92: {len(near_matches)}",
            f"Original training keys reused by curated rows: {len(set(curated_keys) & original_keys)}",
        ]
    )
    REPORT_OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWrote {TRAIN_OUTPUT}")
    print(f"Wrote {REPORT_OUTPUT}")


if __name__ == "__main__":
    main()
