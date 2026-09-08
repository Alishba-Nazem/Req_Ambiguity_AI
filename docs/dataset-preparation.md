# Dataset Preparation (first text-classification experiment)

Preparation of **`dataset.csv` only**. Original Kaggle files were not modified. `featureboost.csv` and `finalreq.csv` were not used. Labels were **not** mapped to this project’s research taxonomy. No model was trained.

**Source (on disk):** `dataset/fault_prone_srs/dataset.csv`  
(headerless two-column file: column 1 = requirement text, column 2 = integer label)

**Outputs**

| File | Role |
| --- | --- |
| `dataset/processed/fault_prone_clean.csv` | Training table after same-label dedup and conflict removal |
| `dataset/processed/conflicting_duplicates.csv` | Same text, different labels — held out, unresolved |
| `dataset/processed/suspicious_requirements.csv` | 1–2 token fragments — copied for review, **not** deleted from training |

---

## Rules applied

1. Read as headerless CSV. Columns named `requirement`, `label`.
2. `label` kept as integers **1–6**. No names (lexical, semantic, syntactic, pragmatic, etc.) were assigned; the original file has no legend.
3. Exact duplicate = identical parsed `requirement` string (CSV unquoting only; no case-folding or whitespace collapse).
4. Same text **and** same label: keep the first occurrence; drop extra copies from the training table.
5. Same text with **conflicting** labels: do not pick a label. **All** rows for those texts are removed from the training table and written to `conflicting_duplicates.csv` with `review_status=unresolved`.
6. Requirements with **1 or 2** whitespace-separated tokens: listed in `suspicious_requirements.csv` for review. They **remain** in `fault_prone_clean.csv`.

---

## Count summary

| Metric | Count |
| --- | --- |
| Original rows | **7,061** |
| Unique requirement strings | 6,810 |
| Duplicate groups (text appears more than once) | **238** |
| Rows that belong to those duplicate groups | **489** |
| Extra duplicate copies (rows beyond the first of each repeated text) | **251** |
| Same-label duplicate groups | 195 |
| Extra copies removed (same text, same label) | **204** |
| Conflicting texts | **43** |
| Conflicting rows (all instances held out) | **90** |
| Suspicious 1–2 token rows in the original file | **156** (152 unique texts) |
| Suspicious 1–2 token rows remaining in the cleaned file | **152** (20 one-token, 132 two-token) |
| Final cleaned rows | **6,767** |

Check: `7061 − 90 (conflicts) − 204 (same-label extras) = 6767`.

The cleaned file has 6,767 unique requirement strings and no overlap with the conflicting-text set.

---

## Class distribution

Labels are the original integers only.

### Before cleaning (7,061 original rows)

| label | Count | Share |
| --- | --- | --- |
| 1 | 474 | 6.71% |
| 2 | 615 | 8.71% |
| 3 | 614 | 8.70% |
| 4 | 504 | 7.14% |
| 5 | 834 | 11.81% |
| 6 | 4,020 | 56.93% |
| **Total** | **7,061** | 100% |

### After cleaning (6,767 training rows)

| label | Count | Share |
| --- | --- | --- |
| 1 | 463 | 6.84% |
| 2 | 598 | 8.84% |
| 3 | 594 | 8.78% |
| 4 | 474 | 7.00% |
| 5 | 813 | 12.01% |
| 6 | 3,825 | 56.52% |
| **Total** | **6,767** | 100% |

Label `6` remains the majority class.

---

## File contents

### `fault_prone_clean.csv`

Columns: `requirement`, `label`  
`label` is an integer in `{1,2,3,4,5,6}`.

Includes 1–2 token fragments (they were not auto-deleted). Excludes all 43 conflicting texts.

### `conflicting_duplicates.csv`

All 90 source rows for the 43 conflicting texts. Extra columns: `source_row_index`, `labels_for_this_text`, `n_distinct_labels`, `n_rows_for_this_text`, `review_status=unresolved`.

### `suspicious_requirements.csv`

The 152 unique 1–2 token requirements that are still in the training table (after same-label collapse). `still_in_training_set=yes`. Four extra original copies of those fragments were same-label duplicates and were collapsed with the rest of the same-label dedup (counted in the 204).

Examples still in training and listed for review: `Login`, `Exit`, `Signup`, `Text chat`.

---

## What was not done

- No edits to `dataset/fault_prone_srs/dataset.csv`, `featureboost.csv`, or `finalreq.csv`
- `featureboost.csv` not used
- `finalreq.csv` not merged
- No mapping of 1–6 onto the project taxonomy
- No BERT or other model training
