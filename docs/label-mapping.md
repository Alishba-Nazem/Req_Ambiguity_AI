# Label mapping (Fault-Prone SRS, first experiment)

This document records the **verified** mapping for the integer labels stored in the processed split files. It does **not** change those files. It does **not** replace this project’s research taxonomy.

**Source of the mapping:** verified against the Fault-Prone SRS dataset label scheme (Muhamad et al., *Appl. Sci.* 2023, 13(14), 8368; Kaggle `corpus4panwo/fault-prone-srs-dataset`). The original `dataset.csv` has no header or legend; the integers `1`–`6` are what the CSVs contain. The names below are the verified meanings of those integers.

**Pipeline config:** `ml/config.py` (`LABEL_TO_NAME`, `NAME_TO_LABEL`).

---

## Mapping used for model training

Training files keep **integer labels 1–6**. The model pipeline must treat them as:

| Integer (`label`) | Pipeline name | Full class name |
| --- | --- | --- |
| 1 | `lexical` | Lexical Ambiguity |
| 2 | `syntactic` | Syntactic Ambiguity |
| 3 | `semantic` | Semantic Ambiguity |
| 4 | `syntax` | Syntax Ambiguity |
| 5 | `pragmatic` | Pragmatic Ambiguity |
| 6 | `clean` | Clean |

`syntactic` (2) and `syntax` (4) are **different** classes in this dataset.

When a 6-way classifier later needs 0-based class indices, use `label - 1` (so dataset `1` → index `0` = lexical). Do not rewrite `train.csv` / `validation.csv` / `test.csv`.

---

## Not this project’s research taxonomy

The project’s research taxonomy remains unchanged and is **not** these six classes:

- Terminological & Lexical Ambiguity
- Implicit Incompleteness
- Uncertainty & Instability

This first experiment classifies the **dataset’s** six labels. No mapping from `{1…6}` onto the research taxonomy is defined here.

---

## Split-file verification (read-only)

Inspected `dataset/processed/train.csv`, `validation.csv`, and `test.csv`. Those files were not modified.

| Check | Train | Validation | Test |
| --- | --- | --- | --- |
| Columns | `requirement`,`label` | `requirement`,`label` | `requirement`,`label` |
| Rows | 5,412 | 676 | 679 |
| Labels only in `{1,2,3,4,5,6}` | yes | yes | yes |
| Missing requirements | 0 | 0 | 0 |
| Missing labels | 0 | 0 | 0 |
| Unique texts | 5,412 | 676 | 679 |

Exact-text overlap: train ∩ val = **0**, train ∩ test = **0**, val ∩ test = **0**.

No issues found.

### Class counts in the splits

| label | name | Train | Val | Test |
| --- | --- | --- | --- | --- |
| 1 | lexical | 370 | 46 | 47 |
| 2 | syntactic | 478 | 60 | 60 |
| 3 | semantic | 475 | 59 | 60 |
| 4 | syntax | 379 | 47 | 48 |
| 5 | pragmatic | 650 | 81 | 82 |
| 6 | clean | 3,060 | 383 | 382 |
