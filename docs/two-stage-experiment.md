# Two-stage BERT experiment

Binary **clean vs ambiguous** first, then a 5-way **ambiguity-type** classifier on rows predicted as ambiguous.

Trained on Google Colab GPU. Dataset CSVs were not modified. `test.csv` was not used for training or checkpoint selection. Baseline and weighted outputs were not overwritten.

Checkpoints: `ml/outputs_two_stage/stage_a/best_model` and `ml/outputs_two_stage/stage_b/best_model`.

Scripts: `ml/train_two_stage.py`, `ml/evaluate_two_stage.py`. Seed **42**. Model `bert-base-uncased`. Same hyperparameters as the previous BERT runs (3 epochs, batch 16, lr 2e-5, max length 128). Best checkpoint per stage: validation **macro F1**.

---

## Label conversion

Dataset files still store integers **1–6**. Conversion happens only in memory.

**Stage A (binary)**

| Dataset `label` | Stage A index | Name |
| --- | --- | --- |
| 6 | 0 | clean |
| 1, 2, 3, 4, 5 | 1 | ambiguous |

Train rows: 5,412 (3,060 clean / 2,352 ambiguous). Validation: 676 (383 / 293).

**Stage B (5-way, clean excluded)**

| Dataset `label` | Stage B index | Name |
| --- | --- | --- |
| 1 | 0 | lexical |
| 2 | 1 | syntactic |
| 3 | 2 | semantic |
| 4 | 3 | syntax |
| 5 | 4 | pragmatic |
| 6 | — | dropped |

Train rows: 2,352. Validation: 293.

**Final pipeline (test/val)**

1. Stage A predicts clean or ambiguous.
2. If clean → dataset label **6**.
3. If ambiguous → Stage B predicts 0–4 → dataset labels **1–5**.

---

## 1. Stage A (clean vs ambiguous)

Selected checkpoint: **epoch 2** (val macro F1 0.7788). Epoch 3 was slightly worse (0.777).

| Split | Accuracy | Macro P | Macro R | Macro F1 | clean F1 | ambiguous F1 |
| --- | --- | --- | --- | --- | --- | --- |
| Validation | 0.7840 | 0.7810 | 0.7773 | **0.7788** | 0.8128 | 0.7448 |
| Test | 0.7953 | 0.7942 | 0.7877 | **0.7900** | 0.8234 | 0.7566 |

Test: clean recall 0.848, ambiguous recall 0.727. Stage A still misses some true-ambiguous rows (those become `ambiguous → clean` in the pipeline).

---

## 2. Stage B (ambiguity type, gold-ambiguous rows only)

This is **oracle Stage B**: only rows whose gold label is 1–5. It is not the full pipeline.

Selected checkpoint: **epoch 2** (val macro F1 0.6082).

| Split | Accuracy | Macro P | Macro R | Macro F1 |
| --- | --- | --- | --- | --- |
| Validation | 0.6348 | 0.6303 | 0.6150 | **0.6082** |
| Test | 0.6128 | 0.6322 | 0.5982 | **0.6003** |

Test per-class F1: pragmatic 0.716, syntax 0.691, syntactic 0.610, semantic 0.569, **lexical 0.416**. Lexical recall is still the weak type class (0.340).

---

## 3. Full two-stage pipeline (6-class)

| Split | Accuracy | Macro P | Macro R | Macro F1 | clean→amb | amb→clean |
| --- | --- | --- | --- | --- | --- | --- |
| Validation | 0.6775 | 0.5614 | 0.5177 | 0.5238 | 66 | 80 |
| **Test** | **0.6834** | **0.5680** | **0.5198** | **0.5354** | **58** | **81** |

Test per-class:

| Class | Precision | Recall | F1 | Support |
| --- | --- | --- | --- | --- |
| lexical | 0.517 | 0.319 | 0.395 | 47 |
| syntactic | 0.421 | 0.533 | 0.471 | 60 |
| semantic | 0.371 | 0.383 | 0.377 | 60 |
| syntax | 0.636 | 0.438 | 0.519 | 48 |
| pragmatic | 0.662 | 0.598 | 0.628 | 82 |
| clean | 0.800 | 0.848 | 0.823 | 382 |

Pipeline F1 is lower than oracle Stage B because Stage A errors are irreversible: an ambiguous row sent to `clean` never reaches Stage B; a clean row sent to Stage B gets an ambiguity type.

---

## 4. Comparison on held-out test.csv (679 rows)

| Experiment | Accuracy | Macro P | Macro R | **Macro F1** | clean→amb | amb→clean |
| --- | --- | --- | --- | --- | --- | --- |
| 1. Unweighted BERT | 64.5% | 0.577 | 0.335 | 0.358 | (majority `clean`) | high |
| 2. Class-weighted BERT | 43.2% | 0.426 | 0.507 | 0.415 | **253** | 24 |
| **3. Two-stage BERT** | **68.3%** | 0.568 | **0.520** | **0.535** | **58** | 81 |

Per-class F1 on test:

| Class | Baseline | Weighted | **Two-stage** |
| --- | --- | --- | --- |
| lexical | 0.000 | 0.341 | **0.395** |
| syntactic | 0.125 | 0.320 | **0.471** |
| semantic | 0.176 | 0.359 | **0.377** |
| syntax | 0.455 | 0.462 | **0.519** |
| pragmatic | 0.615 | 0.525 | **0.628** |
| clean | 0.775 | 0.482 | **0.823** |

---

## 5. Did two-stage help?

**Yes.**

- **Macro F1:** 0.358 → 0.415 → **0.535**. Best of the three.
- **Accuracy:** 64.5% → 43.2% → **68.3%**. Recovers (and beats) the baseline without going back to “always clean”.
- **Clean vs ambiguous:** Stage A test macro F1 **0.790**. False alarms on clean dropped from **253** (weighted) to **58**. That was the point of this experiment.
- **Minority types:** every ambiguity class F1 is at least as high as weighted; syntactic and pragmatic improved clearly.

Trade-off: **ambiguous → clean rose** (24 → 81). Stage A still under-calls ambiguity (ambiguous recall 0.727). Those 81 rows never reach Stage B.

Stage B is now the bottleneck for type quality (test macro F1 0.600 on gold-ambiguous rows; lexical remains weakest).

---

## 6. Recommended next experiment

Do **not** retune on test.

**Next: class-weighted Stage B only**, same splits/seed, selected on validation macro F1.

Stage A is already useful. Stage B still collapses `lexical` (and to a lesser extent `semantic`) into other types. Inverse-frequency weights on the 5-way head should raise lexical recall without reopening the clean→ambiguous flood, because clean rows never enter Stage B.

Keep Stage A frozen. Save under `ml/outputs_two_stage/stage_b_weighted/` and compare the same 6-class pipeline on validation first, then test once.
