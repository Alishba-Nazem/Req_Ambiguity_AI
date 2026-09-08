# Error analysis — class-weighted BERT

This report analyzes the **class-weighted** BERT checkpoint (`ml/outputs_weighted/best_model`) on the untouched **test** split (`dataset/processed/test.csv`, 679 rows). The model was not retrained. Train, validation, and test files were not modified. Baseline artifacts under `ml/outputs/` were not modified.

Machine-readable outputs: `ml/outputs_weighted/error_analysis/`.

Script: `ml/error_analysis.py` (seed 42, same tokenizer and label mapping as `ml/config.py`).

---

## 1. Overall picture

| Metric | Baseline (unweighted) | Weighted (this analysis) |
| --- | --- | --- |
| Accuracy | 64.5% | 43.2% |
| Macro precision | 0.577 | 0.426 |
| Macro recall | 0.335 | **0.507** |
| Macro F1 | 0.358 | **0.415** |
| Correct / 679 | 438 | 293 |
| Misclassified | 241 | 386 |

Class weighting improved the metric that matters for ambiguity **type** detection (macro F1 / recall). It did that by stopping the model from dumping almost everything into `clean`. The cost is a large rise in false alarms on truly clean requirements.

---

## 2. What the model gets right

Per-class results on test (weighted model):

| Label | Class | Precision | Recall | F1 | Support | Correct |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | lexical | 0.366 | 0.319 | 0.341 | 47 | 15 |
| 2 | syntactic | 0.231 | 0.517 | 0.320 | 60 | 31 |
| 3 | semantic | 0.238 | 0.733 | 0.359 | 60 | 44 |
| 4 | syntax | 0.391 | 0.563 | 0.462 | 48 | 27 |
| 5 | pragmatic | 0.485 | 0.573 | **0.525** | 82 | 47 |
| 6 | clean | **0.844** | 0.338 | 0.482 | 382 | 129 |

**Strengths**

- **`pragmatic` is the strongest ambiguity class** (F1 0.525). The model is very confident on short, fragment-like requirements (`Download Project File`, `Search option`, `Date range`, confidence ≈ 0.97). That is useful, but it also reveals a dataset cue: many pragmatic labels are 2–3 token stubs.
- **`syntax` is the next-best ambiguity class** (F1 0.462). Grammatically broken but still readable sentences are often caught (`The system shall allow the users to make changes to the password if the user not remember the password`, confidence 0.89).
- **`semantic` has the highest ambiguity recall** (0.733). The model frequently fires on “each …” quantification patterns (`The user can view each tasks in the middle of the screen`).
- When the model predicts `clean`, it is usually right (**precision 0.844**). The problem is that it rarely predicts `clean` (recall 0.338).

Compared with the unweighted baseline, weighting **did help minority classes**:

| Class | Baseline F1 | Weighted F1 |
| --- | --- | --- |
| lexical | 0.000 | **0.341** |
| syntactic | 0.125 | **0.320** |
| semantic | 0.176 | **0.359** |
| syntax | 0.455 | 0.462 |
| pragmatic | 0.615 | 0.525 |
| clean | 0.775 | 0.482 |

`lexical` went from never predicted to a usable class. That is the main success of experiment 2.

---

## 3. Hardest classes

Hardest by F1 (lowest first):

1. **`syntactic` (0.320)** — highest among-ambiguity error rate in the other direction: it is over-predicted onto `clean` (83 false positives). Precision is only 0.231.
2. **`lexical` (0.341)** — still the weakest genuine ambiguity class after weighting. Recall is only 0.319; many lexical items are absorbed by `semantic`.
3. **`semantic` (0.359)** — high recall, low precision. The model treats “each / only by / only at” wording as a semantic cue and applies it too broadly.

`clean` F1 (0.482) is higher than those three, but it is the **largest source of errors by count** because 253 of 382 clean rows are mislabeled as some ambiguity class.

---

## 4. Confusion matrix

Rows = true label, columns = predicted label.

| true \ pred | lexical | syntactic | semantic | syntax | pragmatic | clean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| lexical | 15 | 8 | 14 | 2 | 4 | 4 |
| syntactic | 5 | 31 | 9 | 2 | 4 | 9 |
| semantic | 4 | 4 | 44 | 1 | 3 | 4 |
| syntax | 2 | 1 | 8 | 27 | 10 | 0 |
| pragmatic | 7 | 7 | 12 | 2 | 47 | 7 |
| clean | 8 | 83 | 98 | 35 | 29 | 129 |

### Focused pairs requested

| Pair | Count | Share of 386 errors | Verdict |
| --- | ---: | ---: | --- |
| **clean → ambiguous** | **253** | **65.5%** | Dominant failure |
| ambiguous → clean | 24 | 6.2% | Rare after weighting |
| lexical ↔ syntactic | 13 | 3.4% | Present, not dominant |
| semantic ↔ syntax | 9 | 2.3% | Small |
| syntactic ↔ syntax | 3 | 0.8% | Almost none |

The names `syntactic` and `syntax` look confusable, but the model barely mixes them. The real collapse is **clean vs ambiguous**, then **semantic absorbing other ambiguity types**.

### Top directed pairs

| True → Pred | Count | % of errors |
| --- | ---: | ---: |
| clean → semantic | 98 | 25.4% |
| clean → syntactic | 83 | 21.5% |
| clean → syntax | 35 | 9.1% |
| clean → pragmatic | 29 | 7.5% |
| lexical → semantic | 14 | 3.6% |
| pragmatic → semantic | 12 | 3.1% |
| syntax → pragmatic | 10 | 2.6% |

`clean → semantic` plus `clean → syntactic` alone are **46.9% of all errors**.

---

## 5. Representative examples

Confidence is the softmax probability of the predicted class. `P(true)` is the probability the model assigned to the gold label.

### Correct examples (what it learned)

| True | Example | Confidence |
| --- | --- | ---: |
| lexical | This web part shall be added to the default page in Statistics section and shall display the latest 5 or must read 5 releases… | 0.70 |
| syntactic | Ability to perform edits to previous pay periods and recalculate pay and leave accruals from previous pay period forward. | 0.59 |
| semantic | The user can view each tasks in the middle of the screen. | 0.75 |
| syntax | The system shall allow the users to make changes to the password if the user not remember the password | 0.89 |
| pragmatic | Download Project File | 0.97 |
| clean | The software shall record the history of version-controlled documents | 0.58 |

Pattern: `syntax` and `pragmatic` wins are high-confidence and often surface-level (broken grammar, or a 2-word stub). `clean` wins are lower-confidence even when correct.

### Misclassified examples (weaknesses)

1. **clean → pragmatic, very high confidence (dataset cue)**  
   `User defined fields` — true `clean`, pred `pragmatic`, conf **0.96**, P(true)=0.01.  
   Same pattern: `CUSTOMER DATA RECORD`, `Trigger each harvesting job`. Short noun phrases labeled `pragmatic` in training taught the model “fragment = pragmatic”.

2. **clean → semantic (largest error pair)**  
   `The user shall be provided with the functionality to post each reply to each particular person who is the part of each of which discussion thread.` — true `clean`, pred `semantic`, conf 0.60.  
   Repeated `each` / `each of which` is a surface cue the model treats as semantic ambiguity, even when the gold label is clean.

3. **clean → syntactic**  
   `Accept credit and debit card payments only at accounts desks, self check-out stations, and only through the public web interface…` — true `clean`, pred `syntactic`.  
   `only at` / `only through` look like the injected-ambiguity markers used elsewhere in this corpus.

4. **lexical → semantic (minority-class collapse)**  
   `Each display shall reflect the level of access and the privileges of the user (security aware).` — true `lexical`, pred `semantic`, conf 0.62, P(true)=0.16.  
   Lexical items are often absorbed by the more frequent “quantifier / each” semantic pattern.

5. **lexical → syntactic**  
   `Generates standard or custom inspection failure/correction notices.` — true `lexical`, pred `syntactic`, conf 0.55, P(true)=0.10.

6. **syntactic ↔ syntax (rare, still exists)**  
   `Ability to access GIS mapping data for road/street locations` — true `syntactic`, pred `syntax`, conf 0.61, P(true)=0.12.

7. **syntax → semantic**  
   `The software must incorporate each license key authentication process.` — true `syntax`, pred `semantic`, conf 0.67, P(true)=0.01.  
   Again the word `each` overrides the grammar-error signal.

8. **syntax → pragmatic, high confidence**  
   `Personnel Action Reports` — true `syntax`, pred `pragmatic`, conf **0.96**.  
   Another short-title / fragment cue.

9. **ambiguous → clean (under-calling ambiguity)**  
   `The system must allow user both to edit and modify operation runtime. (only business hours).` — true `semantic`, pred `clean`, conf 0.50, P(true)=0.08.

10. **pragmatic → clean**  
    `System shall not view the users who do not want to show themselves only at search results.` — true `pragmatic`, pred `clean`, conf 0.44.

These examples point to **dataset artifacts** as much as model failure: injected words (`each`, `only at`, `only by`, `only through`), near-duplicate class names (`syntactic` vs `syntax`), and very short “requirements” that are titles rather than sentences.

---

## 6. Did class weighting help?

Yes, for the intended goal (detect *which* ambiguity type).

- Minority F1 for `lexical`, `syntactic`, and `semantic` all rose sharply.
- Ambiguous → clean errors are only 24 (6% of errors). The baseline’s problem of hiding ambiguity inside `clean` is largely gone.
- The new problem is the opposite: **over-calling ambiguity**. 253 clean test rows (66% of clean support) are predicted as an ambiguity class.

Weighting did not create a `syntactic`/`syntax` identity crisis. That pair is almost unused as an error mode.

---

## 7. Recommended next ML experiment

**Do not tune on test.** The next change should be trained on `train.csv` and selected on `validation.csv` only.

**Recommended experiment: two-stage classifier**

1. **Stage A — binary `clean` vs `ambiguous`.**  
   Collapse labels 1–5 into one positive class. This directly attacks the 253 clean→ambiguous errors that dominate the weighted model, without throwing away the minority-class gains.
2. **Stage B — 5-way type classifier, trained only on ambiguous rows.**  
   `lexical` / `syntactic` / `semantic` / `syntax` / `pragmatic`. Stage B never sees the 3,060 clean majority rows, so it can learn type distinctions (especially `lexical` vs `semantic`) without being pulled toward `clean` or over-firing on `each`.

Why this, and not more of the same:

- More epochs or stronger weights will likely worsen clean→ambiguous.
- Softer weights would probably restore the baseline’s “always say clean” behavior.
- Intra-ambiguity pairs (`syntactic`↔`syntax`) are too rare to justify a specialized loss for them first.

Keep the same seed (42), tokenizer, and splits. Save outputs under a new directory (for example `ml/outputs_twostage/`) so baseline and weighted results stay untouched. Evaluate the two-stage pipeline on `test.csv` only after model selection on validation.

Optional later checks, not the next experiment: review short 1–3 token “requirements” in `suspicious_requirements.csv`, and inspect whether `each` / `only at` injections are consistently labeled.
