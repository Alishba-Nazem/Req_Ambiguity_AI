# Fault-Prone SRS Dataset Inspection

Inspection of the original Kaggle files as they sit in the project. No original file was modified. No cleaned or processed CSV was created. No model was trained. Dataset integer codes were **not** mapped to this project’s research taxonomy, and class names were **not** inferred for columns that have no legend in the files.

**Source directory (actual path on disk):** `dataset/fault_prone_srs/`

---

## 1. File names

| File | Size |
| --- | --- |
| `dataset/fault_prone_srs/dataset.csv` | 855,226 bytes |
| `dataset/fault_prone_srs/featureboost.csv` | 20,964 bytes |
| `dataset/fault_prone_srs/finalreq.csv` | 62,444 bytes |

---

## 2. Rows and columns

| File | Data rows | Columns | Header row in file? |
| --- | --- | --- | --- |
| `dataset.csv` | **7,061** | **2** | **No** — first row is a requirement, not a header |
| `featureboost.csv` | **200** | **26** | **Yes** |
| `finalreq.csv` | **756** | **2** | **No** — first row is a requirement, not a header |

The three files are not the same data at different grain:

- Sum of `featureboost.csv` `TotalRequirements` = **6,207**, which does not equal 7,061.
- Exact-text overlap between `dataset.csv` and `finalreq.csv` = **0**.

---

## 3. Column names

### `dataset.csv` and `finalreq.csv`

There are **no column names in the files**. Both are two-column CSVs:

- Column 1: text
- Column 2: integer

Using the first row as a header would be incorrect (that row is data).

### `featureboost.csv` (names as stored)

`Id`, `ClearTitle`, `TitleFrequencyInDescription`, `ClearDescriptions`, `DescriptionWordCount`, `PresenceOfIntendedUser`, `TotalRequirements`, `ClearRequirements`, `AmbiguousRequirements`, `NumberOfDetectedLexicalAmbiguity`, `NumberOfDetectedSyntacticAmbiguity`, `NumberOfDetectedSemanticAmbiguity`, `NumberOfDetectedSyntaxAmbiguity`, `NumberOfDetectedPragmaticAmbiguity`, `PercentageOfLexicalAmbiguity`, `PercentageOfSyntacticAmbiguity`, `PercentageOfSemanticAmbiguity`, `PercentageOfSyntaxAmbiguity`, `PercentageOfPragmaticAmbiguity`, `PercentageOfCleanRequirements`, `ProbabilityValueLexicalAmbiguity`, `ProbabilityValueSyntacticAmbiguity`, `ProbabilityValueSemanticAmbiguity`, `ProbabilityValueSyntaxAmbiguity`, `ProbabilityValuePragmaticAmbiguity`, `FaultProneSRS`

---

## 4. Data types (observed from values)

### `dataset.csv` / `finalreq.csv`

| Position | Observed type |
| --- | --- |
| Column 1 | string |
| Column 2 | integer (`1`–`6`) |

### `featureboost.csv`

| Column | Observed type | Notes |
| --- | --- | --- |
| `Id` | integer | 1–200, unique |
| `ClearTitle` | integer | only `0`, `1` |
| `TitleFrequencyInDescription` | integer | |
| `ClearDescriptions` | integer | only `0`, `1` |
| `DescriptionWordCount` | integer | |
| `PresenceOfIntendedUser` | integer | only `0`, `1` |
| `TotalRequirements` | integer | |
| `ClearRequirements` | integer | |
| `AmbiguousRequirements` | integer | |
| `NumberOfDetectedLexicalAmbiguity` | integer | |
| `NumberOfDetectedSyntacticAmbiguity` | integer | |
| `NumberOfDetectedSemanticAmbiguity` | integer | |
| `NumberOfDetectedSyntaxAmbiguity` | integer | |
| `NumberOfDetectedPragmaticAmbiguity` | integer | |
| `PercentageOf*` (5 type columns + clean) | float | |
| `ProbabilityValue*` (5 type columns) | float | |
| `FaultProneSRS` | integer | only `0`, `1` |

---

## 5. Which file contains individual requirement text

| File | Individual requirement text? |
| --- | --- |
| `dataset.csv` | **Yes** — unnamed first column, one string per row |
| `finalreq.csv` | **Yes** — unnamed first column, one string per row |
| `featureboost.csv` | **No** — numeric/document features only; no title, description, or requirement strings |

---

## 6. Which file contains labels

| File | Label-like columns |
| --- | --- |
| `dataset.csv` | Unnamed second column: integer `1`–`6` per row |
| `finalreq.csv` | Unnamed second column: integer `1`–`6` per row |
| `featureboost.csv` | `FaultProneSRS` (`0`/`1`), plus named count/percentage/probability columns for detected ambiguity types |

---

## 7. What each label/value means **according to the files**

### `dataset.csv` and `finalreq.csv`

The files contain **only the integers `1, 2, 3, 4, 5, 6`**. There is **no header, codebook, or legend** in either CSV that names those codes.

This inspection therefore **does not assign meanings** (for example lexical / syntactic / semantic) to those integers. Any such mapping would be an external assumption, not something the files themselves state.

Observed values: `{1, 2, 3, 4, 5, 6}`.

### `featureboost.csv`

Meanings that **are** written in the file are the **column names**:

| Column / value | What the file states |
| --- | --- |
| `ClearTitle`, `ClearDescriptions`, `PresenceOfIntendedUser` | `0` or `1` (no further legend) |
| `TotalRequirements`, `ClearRequirements`, `AmbiguousRequirements` | Integer counts per row |
| `NumberOfDetectedLexicalAmbiguity` | Count named “lexical” in the header |
| `NumberOfDetectedSyntacticAmbiguity` | Count named “syntactic” in the header |
| `NumberOfDetectedSemanticAmbiguity` | Count named “semantic” in the header |
| `NumberOfDetectedSyntaxAmbiguity` | Count named “syntax” in the header (separate from syntactic) |
| `NumberOfDetectedPragmaticAmbiguity` | Count named “pragmatic” in the header |
| `PercentageOf*` / `ProbabilityValue*` | Same type names as ratios |
| `PercentageOfCleanRequirements` | Percentage named “clean” in the header |
| `FaultProneSRS` | `0` or `1` only; the files do not define which integer is “fault-prone” vs not |

Integrity checks that follow from the column names (not from external labels):

- Type-count columns always sum to `AmbiguousRequirements` (0 mismatches).
- `ClearRequirements + AmbiguousRequirements` always equals `TotalRequirements` (0 mismatches).

---

## 8. Per-requirement vs document-level

| File | Unit of one row | Label grain |
| --- | --- | --- |
| `dataset.csv` | One text string (requirement or fragment) | Integer `1`–`6` **per row** |
| `finalreq.csv` | One text string (requirement or fragment) | Integer `1`–`6` **per row** |
| `featureboost.csv` | One `Id` (1–200); no requirement text | **Document-level** counts and `FaultProneSRS` |

There is no identifier in `dataset.csv` or `finalreq.csv` that joins a requirement to a `featureboost.csv` `Id`.

---

## 9. Class distribution

### `dataset.csv` (7,061 rows)

| Column-2 value | Count | Share |
| --- | --- | --- |
| 1 | 474 | 6.71% |
| 2 | 615 | 8.71% |
| 3 | 614 | 8.70% |
| 4 | 504 | 7.14% |
| 5 | 834 | 11.81% |
| 6 | 4,020 | 56.93% |
| **Total** | **7,061** | 100% |

Value `6` is the majority. The five other values are smaller and similar in size to each other.

### `finalreq.csv` (756 rows)

| Column-2 value | Count | Share |
| --- | --- | --- |
| 1 | 29 | 3.84% |
| 2 | 314 | 41.53% |
| 3 | 36 | 4.76% |
| 4 | 9 | 1.19% |
| 5 | 76 | 10.05% |
| 6 | 292 | 38.62% |
| **Total** | **756** | 100% |

Value `2` is the majority here; value `4` has only 9 rows. This distribution does **not** match `dataset.csv`.

### `featureboost.csv` — `FaultProneSRS` (200 rows)

| `FaultProneSRS` | Count | Share |
| --- | --- | --- |
| 0 | 48 | 24.00% |
| 1 | 152 | 76.00% |
| **Total** | **200** | 100% |

Other 0/1 columns: `ClearTitle` 1=188, 0=12; `ClearDescriptions` 1=190, 0=10; `PresenceOfIntendedUser` 1=124, 0=76.

---

## 10. Missing values

None of the three files has empty cells in any column (0 empty texts, 0 empty second-column values, 0 empty `featureboost.csv` cells).

---

## 11. Duplicate requirements

Duplicates = identical parsed text in column 1 (CSV unquoting only; no case-folding).

| File | Unique texts | Texts that appear more than once | Rows in those groups | Extra copies beyond the first |
| --- | --- | --- | --- | --- |
| `dataset.csv` | 6,810 of 7,061 | 238 groups | 489 | 251 |
| `finalreq.csv` | 736 of 756 | 20 groups | 40 | 20 |
| `featureboost.csv` | n/a (no requirement text) | duplicate `Id`s: **0** | | |

---

## 12. Conflicting duplicate labels

Same text, **more than one** distinct integer in column 2.

| File | Conflicting texts | Rows involved |
| --- | --- | --- |
| `dataset.csv` | **43** | **90** |
| `finalreq.csv` | **8** | **16** |

Examples from `dataset.csv` (text truncated):

| Text | Values seen |
| --- | --- |
| Also the connections to the servers shall be based on the attributes of the user like his location and server shall be working 24X7 times. | 5 and 2 |
| This system shall work on client-server architecture. It shall require each internet server… | 5 and 1 |
| Customer workstation shall be internet capable with only at least one internet browser available. | 6 and 3 |
| The User Interface consists of J2ME GUI components like Forms, Buttons, Canvas… | 2 and 6 |

Examples from `finalreq.csv`:

| Text | Values seen |
| --- | --- |
| Ability to deploy applications in any environment | 6 and 3 |
| High scalability and flexibility | 5 and 2 |
| Support for a wide range of programming languages | 2 and 6 |

No label was chosen for these conflicts in this inspection.

---

## 13. Suspicious / very short / fragmented text

Operational check used here (not a deletion): empty/whitespace (none), or **1–2 whitespace-separated tokens**.

### `dataset.csv`

- **156** rows, **152** unique texts, almost all with column-2 value `5`
- Length range overall: 4–2,619 characters; 1–458 tokens; mean ~18.4 tokens
- Many strings look preprocessed (unnatural repetition of “each”, extra spaces)
- Single-token examples: `Exit`, `Login`, `Signup`, `Logout`, `Submit`, `Cancel`, `About`, `area`, `Grades`, `Security`, plus heading-like tokens such as `Reliability`, `Portability`, `Maintainability`
- Two-token examples: `Text chat`, `User page`, `Add Topic`, `Login Page`

### `finalreq.csv`

- **5** two-token strings, all with value `5`: `Provide flexible`, `Multilanguage support`, `Multicurrency support`, `Userfriendly interface`, `Multiplatform compatibility`
- Text is generally closer to ordinary requirement wording (OpenFaaS, Kubernetes, etc.)
- Length range: 16–186 characters; 2–30 tokens; mean ~11.5 tokens

### `featureboost.csv`

No requirement text to assess.

---

## Sample rows (read-only)

### `dataset.csv`

| Col 1 (truncated) | Col 2 |
| --- | --- |
| The general purpose of the steam boiler system is to ensure each safe operation of the steam boiler. | 3 |
| During operation, the water level is kept within the tolerance level as long as possible… | 1 |
| Basically, the steam boiler system consists of the steam boiler itself, each measuring device… | 2 |
| The software to be designed is each program each of which can be used to maintain each address book… | 5 |
| It must be possible to add each new person to each address book… | 4 |
| Exit | 5 |

### `finalreq.csv`

| Col 1 (truncated) | Col 2 |
| --- | --- |
| Serverless: OpenFaaS should support the deployment of serverless functions… | 6 |
| Function Deployment: OpenFaaS should allow functions to be deployed quickly and easily… | 6 |
| High Availability: Kubernetes should be able to provide high availability of services… | 1 |
| Support for customizing functions with environment variables and secrets | 2 |

### `featureboost.csv` (first two rows, selected columns)

| Id | FaultProneSRS | TotalRequirements | ClearRequirements | AmbiguousRequirements | Lexical | Syntactic | Semantic | Syntax | Pragmatic |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 18 | 11 | 7 | 1 | 4 | 2 | 0 | 0 |
| 2 | 0 | 14 | 7 | 7 | 0 | 4 | 2 | 0 | 1 |

Row `Id=2` has several detected-ambiguity counts and `FaultProneSRS=0`. The `0`/`1` target is therefore not a simple “has any detected ambiguity” flag.

---

## 14. Is `featureboost.csv` useful for this ML project?

**Not as the primary training table for per-requirement ambiguity from text.**

- It has **no requirement text**, so a text model cannot be trained from this file alone.
- Rows are **200 SRS-level** records, not individual requirements.
- Ambiguity-type columns are **already aggregated counts/percentages**, not labels on a sentence.
- There is **no join key** to `dataset.csv`.
- `TotalRequirements` sum (6,207) ≠ `dataset.csv` rows (7,061), so this table is not a roll-up of `dataset.csv`.

It **could** be useful later for a **separate document-level** task (`FaultProneSRS` on 200 rows), or as context about how the source dataset authors stored document statistics. Using those precomputed type-counts as features to predict related type labels would mix labels with derived features and should not be the first experiment.

---

## 15. Is `finalreq.csv` useful for training, or should it stay separate?

**Keep it separate from `dataset.csv` for the first model.**

Reasons from the files:

- Same two-column shape and the same integer set `{1…6}`, but **no shared texts**.
- **Different class mix** (value `2` dominates here; value `6` dominates `dataset.csv`).
- Much smaller (756 vs 7,061).
- Text style differs (named systems such as OpenFaaS/Kubernetes; little of the “each …” rewriting seen in `dataset.csv`).
- It has its own 8 conflicting duplicate texts.

Mixing the two files would mix two collections without a documented join. `finalreq.csv` is better treated as a **held-out / later** set, not as extra training rows for the first model.

---

## Recommendation (not implemented)

**Use `dataset.csv` as the only training source for the first ML model.**

It is the only file that combines a large number of individual requirement strings with a per-row label.

Before training (future work, not done here):

1. Confirm what integers `1`–`6` mean from an **external codebook** if one is adopted; do not invent names from this inspection.
2. Decide how to handle **43 conflicting texts** without auto-picking a label.
3. Decide whether one- and two-token fragments belong in training.
4. Do not train on `featureboost.csv` for sentence-level classification.
5. Do not merge `finalreq.csv` into the first training set.

No files were created except this report.
