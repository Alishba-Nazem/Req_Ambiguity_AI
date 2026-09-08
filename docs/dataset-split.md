# Dataset Split (first text-classification experiment)

Splits were created from `dataset/processed/fault_prone_clean.csv` only. That file was not modified. Original Kaggle files were not modified. `featureboost.csv` and `finalreq.csv` were not used. Labels remain integers **1–6**. No model was trained.

**Outputs**

- `dataset/processed/train.csv`
- `dataset/processed/validation.csv`
- `dataset/processed/test.csv`

Columns in each split: `requirement`, `label`.

---

## Split strategy

- **Input:** 6,767 rows; every `requirement` string is unique.
- **Target:** 80% train / 10% validation / 10% test.
- **Stratification:** split **within each integer label** `{1,2,3,4,5,6}` separately, then concatenate.
- **Per-class sizes:**
  - `n_train = round(n * 0.80)`
  - `n_val = round(n * 0.10)`
  - `n_test = n - n_train - n_val`
- After assignment, each split was shuffled so rows are not grouped by label.
- Rounding is why overall counts are 5,412 / 676 / 679 rather than exact 5,413.6 / 676.7 / 676.7.

Every label appears in all three splits (minimum class size in the clean file is 463).

---

## Random seed

| Item | Value |
| --- | --- |
| Seed | **42** |
| RNG | mulberry32 |
| Shuffle | Fisher–Yates, one RNG stream |

Re-running the same procedure with seed 42 on the same `fault_prone_clean.csv` yields the same splits.

---

## Row counts

| Split | Rows | Share of 6,767 |
| --- | --- | --- |
| Train | **5,412** | 80.00% |
| Validation | **676** | 9.99% |
| Test | **679** | 10.03% |
| **Total** | **6,767** | 100% |

`5412 + 676 + 679 = 6767` (no rows dropped or duplicated).

### Per-label assignment

| label | Clean n | Train | Validation | Test |
| --- | --- | --- | --- | --- |
| 1 | 463 | 370 | 46 | 47 |
| 2 | 598 | 478 | 60 | 60 |
| 3 | 594 | 475 | 59 | 60 |
| 4 | 474 | 379 | 47 | 48 |
| 5 | 813 | 650 | 81 | 82 |
| 6 | 3,825 | 3,060 | 383 | 382 |

---

## Class distribution

Shares are within each split. Labels are the original integers (no taxonomy names).

### Train (5,412)

| label | Count | Share |
| --- | --- | --- |
| 1 | 370 | 6.84% |
| 2 | 478 | 8.83% |
| 3 | 475 | 8.78% |
| 4 | 379 | 7.00% |
| 5 | 650 | 12.01% |
| 6 | 3,060 | 56.54% |

### Validation (676)

| label | Count | Share |
| --- | --- | --- |
| 1 | 46 | 6.80% |
| 2 | 60 | 8.88% |
| 3 | 59 | 8.73% |
| 4 | 47 | 6.95% |
| 5 | 81 | 11.98% |
| 6 | 383 | 56.66% |

### Test (679)

| label | Count | Share |
| --- | --- | --- |
| 1 | 47 | 6.92% |
| 2 | 60 | 8.84% |
| 3 | 60 | 8.84% |
| 4 | 48 | 7.07% |
| 5 | 82 | 12.08% |
| 6 | 382 | 56.26% |

Label `6` remains the majority class in every split (~56%).

---

## Duplicate / leakage check

The clean file already had unique requirement strings. After the split:

| Check | Result |
| --- | --- |
| Identical `requirement` text in train ∩ validation | **0** |
| Identical `requirement` text in train ∩ test | **0** |
| Identical `requirement` text in validation ∩ test | **0** |
| Unique texts in train / val / test | 5,412 / 676 / 679 |

No exact-text leakage across splits.

---

## What was not done

- No edits to `fault_prone_clean.csv` or original Kaggle files
- No use of `featureboost.csv` or `finalreq.csv`
- No mapping of labels 1–6 to the project taxonomy
- No BERT or other model training
- No extra libraries installed
