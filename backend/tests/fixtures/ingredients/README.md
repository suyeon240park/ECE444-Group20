# Synthetic ingredient fixtures

`entries.json` contains **synthetic test content**, not reviewed food guidance.
The source URLs are placeholders on allowed hosts. Statements, flags, and dates
exist to exercise validation and must never be copied into production content.

Production content lives in `backend/content/ingredients/entries/`; its loader
never reads this directory. Issues #34 and #35 supply reviewed entries.

The parser scenarios in `test_ingredient_analysis.py` are hand-authored expected
cases informed by Canadian ingredient-list structures and the #28 investigation.
They are not a measured 30-product benchmark. A frozen, manually annotated
30-product corpus and content coverage reports belong to #34/#35.
