# Nutrition Facts label photos (benchmark fixtures)

This folder holds the benchmark set required by requirement **Q1** (issue #4) and built in issue #17: at least 50 phone photos of Canadian Nutrition Facts tables plus a manually transcribed ground truth.

Layout, once populated:

```
tests/fixtures/nutrition_labels/
├── README.md
├── ground_truth.csv      one row per field: image, field, expected value, unit
└── images/
    ├── 001_chips.jpg
    └── ...
```

Rules:

- Photos must not contain personal information. Crop to the package.
- Name files `NNN_short-description.jpg`. Keep images under 2 MB.
- Every value in `ground_truth.csv` is transcribed by one teammate and checked by a second, as Q1 requires.
- Do not put user-uploaded photos here. Only photos taken by the team for this purpose.
