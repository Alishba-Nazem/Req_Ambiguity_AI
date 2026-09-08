"""Configuration for the first text-classification experiment.

Dataset files keep integer labels 1-6. Names below are the verified
Fault-Prone SRS mapping, not the project research taxonomy.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TRAIN_CSV = PROJECT_ROOT / "dataset" / "processed" / "train.csv"
VALIDATION_CSV = PROJECT_ROOT / "dataset" / "processed" / "validation.csv"
TEST_CSV = PROJECT_ROOT / "dataset" / "processed" / "test.csv"

TEXT_COLUMN = "requirement"
LABEL_COLUMN = "label"

# Verified dataset mapping. Do not rewrite the CSV label column.
LABEL_TO_NAME = {
    1: "lexical",
    2: "syntactic",
    3: "semantic",
    4: "syntax",
    5: "pragmatic",
    6: "clean",
}

NAME_TO_LABEL = {name: idx for idx, name in LABEL_TO_NAME.items()}

LABEL_TO_FULL_NAME = {
    1: "Lexical Ambiguity",
    2: "Syntactic Ambiguity",
    3: "Semantic Ambiguity",
    4: "Syntax Ambiguity",
    5: "Pragmatic Ambiguity",
    6: "Clean",
}

NUM_LABELS = 6
LABEL_IDS = (1, 2, 3, 4, 5, 6)

# 0-based index for a future classifier head: dataset label L -> L - 1
ID2LABEL = {label - 1: name for label, name in LABEL_TO_NAME.items()}
LABEL2ID = {name: index for index, name in ID2LABEL.items()}

RANDOM_SEED = 42

MODEL_NAME = "bert-base-uncased"
MAX_LENGTH = 128
BATCH_SIZE = 16
LEARNING_RATE = 2e-5
NUM_EPOCHS = 3

OUTPUT_DIR = PROJECT_ROOT / "ml" / "outputs"
BEST_MODEL_DIR = OUTPUT_DIR / "best_model"

# Second experiment: same data/split/seed, weighted loss to counter class imbalance.
# Kept in a separate directory so the original (unweighted) baseline results
# above are preserved for comparison.
WEIGHTED_OUTPUT_DIR = PROJECT_ROOT / "ml" / "outputs_weighted"
WEIGHTED_BEST_MODEL_DIR = WEIGHTED_OUTPUT_DIR / "best_model"
ERROR_ANALYSIS_DIR = WEIGHTED_OUTPUT_DIR / "error_analysis"

# Third experiment: two-stage clean-vs-ambiguous, then ambiguity type.
# Separate directory so baseline and weighted outputs stay untouched.
TWO_STAGE_OUTPUT_DIR = PROJECT_ROOT / "ml" / "outputs_two_stage"
STAGE_A_OUTPUT_DIR = TWO_STAGE_OUTPUT_DIR / "stage_a"
STAGE_A_BEST_MODEL_DIR = STAGE_A_OUTPUT_DIR / "best_model"
STAGE_B_OUTPUT_DIR = TWO_STAGE_OUTPUT_DIR / "stage_b"
STAGE_B_BEST_MODEL_DIR = STAGE_B_OUTPUT_DIR / "best_model"

# Stage A: dataset label 6 -> 0 (clean); labels 1-5 -> 1 (ambiguous).
STAGE_A_NUM_LABELS = 2
STAGE_A_ID2LABEL = {0: "clean", 1: "ambiguous"}
STAGE_A_LABEL2ID = {name: index for index, name in STAGE_A_ID2LABEL.items()}

# Stage B: dataset labels 1-5 only, remapped to 0-4. Clean is excluded.
STAGE_B_NUM_LABELS = 5
STAGE_B_ID2LABEL = {
    0: "lexical",
    1: "syntactic",
    2: "semantic",
    3: "syntax",
    4: "pragmatic",
}
STAGE_B_LABEL2ID = {name: index for index, name in STAGE_B_ID2LABEL.items()}
