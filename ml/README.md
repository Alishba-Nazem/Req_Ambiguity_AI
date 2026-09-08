# ML experiment — BERT baseline

Six-class text classification on the Fault-Prone SRS splits.

## Data

Use only:

- `dataset/processed/train.csv`
- `dataset/processed/validation.csv`
- `dataset/processed/test.csv`

Columns: `requirement`, `label` (integers 1–6). Do not edit those files.

## Label mapping

See `docs/label-mapping.md` and `config.py`. Dataset `label` L is converted to model class `L - 1` in code only.

| label | name |
| --- | --- |
| 1 | lexical |
| 2 | syntactic |
| 3 | semantic |
| 4 | syntax |
| 5 | pragmatic |
| 6 | clean |

This is the dataset scheme. It is not the project research taxonomy.

## Commands

From `ml/`:

```text
python train.py
python evaluate.py --split test
```

`train.py` uses train + validation only. The best checkpoint is chosen by validation **macro F1**. `evaluate.py` defaults to untouched `test.csv`.

## Config

See `config.py`: `bert-base-uncased`, max length 128, batch 16, lr 2e-5, 3 epochs, seed 42.

## Status

- Dependencies listed in `requirements.txt` (installed in the local Python 3.14 environment).
- Training and evaluation scripts are implemented.
- Results belong under `ml/outputs/` after a run.
