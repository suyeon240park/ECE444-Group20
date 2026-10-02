# What's in My Food? — Requirements

## Project goal

**What's in My Food?** is a responsive web application that helps consumers understand packaged food without requiring specialized nutrition knowledge. A user can take or upload a photo of a packaged product, use its barcode to retrieve available product information, and receive evidence-backed explanations of its nutrition and ingredients. When database nutrition information is incomplete, the application can use OCR on an additional Nutrition Facts photo as a fallback.

The application addresses three recurring problems:

1. nutrition information is often difficult for non-experts to interpret;
2. Nutrition Facts are presented on a serving basis even when a package contains multiple servings; and
3. ingredient names and regulatory evidence can be difficult to interpret quickly while shopping.

The application therefore helps users understand the information already available about a product rather than assigning a universal health score or providing individualized medical advice.

---

## Stakeholders

### Primary Users — Consumers of Packaged Food

| Stakeholder | Needs | Evidence |
|---|---|---|
| **Everyday consumers and non-expert shoppers who want help understanding packaged-food information** | Identify a product without manually transcribing unfamiliar information; understand serving and whole-package nutrition; understand nutrients and unfamiliar ingredients in plain language; and see credible sources and uncertainty rather than unsupported health claims. | A 2016 survey of 2,665 Canadians aged 16–30 found low knowledge of Health Canada's %DV interpretation thresholds: only 7.2% knew that 5% DV means "a little," 4.3% knew that 15% DV means "a lot," and 4.0% knew both ([Canadian Journal of Dietetic Practice and Research](https://doi.org/10.3148/cjdpr-2019-010)). A systematic review found that consumers perform worse as nutrition-label interpretation tasks become more complex and that interpretive aids such as verbal descriptors and reference values can improve understanding ([Cowburn & Stockley, 2005](https://ora.ox.ac.uk/objects/uuid:96041254-ce96-414d-a509-f5dbc7feb626)). Health Canada also states that Nutrition Facts information is based on a labelled serving size and that a person's actual portion may differ ([Health Canada](https://www.canada.ca/en/health-canada/services/food-nutrition/nutrition-labelling/nutrition-facts-tables.html)). |
| **Busy shoppers making food-selection decisions** | Access the most relevant nutrition and ingredient information quickly without reading a full label or researching unfamiliar terms individually. | A 2009 purposive study of 100 Canadian food labels found substantial legibility problems in mandatory label information, including ingredient lists ([Mackey & Metz](https://www.researchgate.net/publication/229648350_Ease_of_reading_of_mandatory_information_on_Canadian_food_product_labels)). Registered dietitians interviewed by Global News also noted that ingredient lists contain many unfamiliar terms and that technical-sounding names do not by themselves indicate whether an ingredient is concerning ([Global News](https://globalnews.ca/news/2036179/making-informed-food-decisions-understanding-ingredient-lists/)). |
| **Consumers who may eat more than one labelled serving** | Understand the nutritional content of the amount they may actually consume without manually multiplying serving-based values. | Pelletier et al. found that 90% of participants correctly identified calories per serving, but only 37% recognized that the snack packages used in the study contained multiple servings ([PubMed](https://pubmed.ncbi.nlm.nih.gov/15355944/)). Canadian research has also examined how package size affects consumers' recognition and use of serving-size information ([CJDPR, 2018](https://doi.org/10.3148/cjdpr-2018-020)). |

### Secondary / Affected Stakeholders

#### 1. Food manufacturers and brands

Food manufacturers are not direct users of the application, but they are affected by how their identifiable products, ingredients, and nutrition information are represented.

**Needs:**
- Product data should be reproduced accurately.
- Ingredient and nutrition explanations should distinguish evidence from interpretation.
- The application should avoid unsupported or misleading claims about a product or ingredient.
- Conflicting evidence should be presented transparently rather than converted into an unsupported universal verdict.

Comparable food-scanning applications demonstrate that consumer-facing product interpretations can affect manufacturers. Yuka, for example, has been reported to influence product reformulation decisions, while disputes over negative ingredient or product characterizations illustrate the reputational consequences of inaccurate or oversimplified explanations. These effects reinforce the importance of the project's accuracy, source-transparency, and uncertainty requirements.

This stakeholder is therefore particularly relevant to requirements for:
- nutrition-data accuracy;
- product-data provenance;
- sourced ingredient explanations; and
- neutral presentation of disagreement between recognized authorities.

#### 2. Public-health and food-labelling authorities

Organizations such as **Health Canada and the Canadian Food Inspection Agency (CFIA)** are external domain stakeholders. They are not users of the application, but their published definitions, Daily Values, labelling rules, and consumer guidance are interpreted or reproduced by the system.

**Needs:**
- Official guidance should be represented accurately and attributed correctly.
- The application should not extend an official rule beyond what the source supports.
- Calculated values should be distinguished from values printed on the official Nutrition Facts label.
- The system should use current Canadian labelling guidance consistently.

Health Canada already addresses a closely related consumer need. Its Nutrition Facts guidance defines the 5% and 15% DV interpretation thresholds, while Canada's front-of-package nutrition symbol is intended to help consumers identify foods high in saturated fat, sugars, or sodium more quickly. These policies provide domain evidence that consumers benefit from concise interpretive nutrition information and also establish constraints on how the application should describe Canadian food-label information.

Sources:
- [Health Canada — Nutrition Facts table](https://www.canada.ca/en/health-canada/services/food-nutrition/nutrition-labelling/nutrition-facts-tables.html)
- [Health Canada — Front-of-package nutrition labelling](https://www.canada.ca/en/health-canada/services/food-nutrition/nutrition-labelling/front-package.html)
- [CFIA — Front-of-package nutrition symbol](https://inspection.canada.ca/en/food-labels/labelling/industry/nutrition-labelling/fop-nutrition-symbol)

### Potential Future Users — Deferred Scope

Consumers managing **food allergies, intolerances, or condition-specific dietary restrictions** are important potential users, but they are not treated as a core stakeholder group for the selected semester scope because personalized allergen detection and condition-specific recommendations are deferred.

There is evidence supporting these needs. Food allergy affects a substantial number of people, and ingredient-label interpretation can be important for this group. However, supporting these users safely would require additional requirements for allergen taxonomy, precautionary statements, missing ingredient information, synonym matching, personalization, and much stronger validation.

Relevant sources:
- [Health Canada — Food allergen labelling](https://www.canada.ca/en/health-canada/services/food-nutrition/food-labelling/allergen-labelling.html)
- [JAMA Network Open — Food allergy prevalence in U.S. adults](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6324316/)
- [PubMed — Ingredient-label obstacles for consumers with food allergies](https://pubmed.ncbi.nlm.nih.gov/17451802/)

These users therefore motivate the deferred allergen stories, but the current application should not present itself as personalized medical, allergy-safety, or condition-specific decision support.

---

## Initial scope

### Selected for the semester

The selected scope covers one coherent end-to-end workflow:

1. **Identify and retrieve product information** from a barcode using a product database, with Nutrition Facts OCR as a fallback when nutrition data is missing.
2. **Calculate whole-package nutrition** when the serving/package relationship is sufficiently known.
3. **Explain nutrients in plain language** using reviewed sources.
4. **Summarize notable ingredients** using a reviewed ingredient knowledge base and explicit evidence rules.
5. Meet measurable quality requirements for:
   - **nutrition extraction accuracy**;
   - **product-identification response time**; and
   - **usability/comprehension for non-experts**.

### Selected requirements

| ID | GitHub issue | Type | Priority |
|---|---|---|---|
| F1 | [#10 — Identify a packaged food from an uploaded photo and retrieve its food information](https://github.com/suyeon240park/ECE444-Group20/issues/10) | Functional | High |
| F2 | [#2 — Display calories and nutrients for the entire package](https://github.com/suyeon240park/ECE444-Group20/issues/2) | Functional | High |
| F3 | [#3 — Explain each nutrient on a product in plain language with a credible source](https://github.com/suyeon240park/ECE444-Group20/issues/3) | Functional | High |
| F4 | [#9 — Quick ingredient summary for busy shoppers](https://github.com/suyeon240park/ECE444-Group20/issues/9) | Functional | Medium |
| Q1 | [#4 — Nutrition values extracted from a label photo must match the printed label](https://github.com/suyeon240park/ECE444-Group20/issues/4) | Quality — Accuracy | High |
| Q2 | [#5 — Identify uploaded food products within an acceptable response time](https://github.com/suyeon240park/ECE444-Group20/issues/5) | Quality — Performance | High |
| Q3 | [#11 — Present food analysis that non-experts can understand and navigate without help](https://github.com/suyeon240park/ECE444-Group20/issues/11) | Quality — Usability | High |

### Deferred

#### Issue #7 — Flag ingredients that match a user's specified allergens
https://github.com/suyeon240park/ECE444-Group20/issues/7

**Decision:** Deferred.

**Rationale:** Personalized allergen detection has strong stakeholder value but requires a defined Canadian allergen taxonomy, precautionary-statement handling, synonym/derivative matching, missing-data handling, and stronger safety validation. These requirements add substantial implementation and verification effort beyond the semester's core educational workflow.

#### Issue #8 — Allergen detection accuracy
https://github.com/suyeon240park/ECE444-Group20/issues/8

**Decision:** Deferred.

**Rationale:** This quality requirement validates the functionality in issue #7. Because #7 is deferred, its accuracy requirement is also deferred.

### Rejected

#### Issue #6 — Explain a product's ingredients and nutrition facts in plain language from a photo
https://github.com/suyeon240park/ECE444-Group20/issues/6

**Decision:** Rejected.

**Rationale:** This candidate combines capture, identification, extraction, nutrient explanation, and ingredient explanation in one story. These concerns are now represented by separate, independently testable selected requirements: #10 for product retrieval/OCR fallback, #3 for nutrient explanation, and #9 for ingredient explanation. Selecting #6 as well would duplicate the accepted requirements and make implementation/test boundaries unclear.

---

## Questions to Clarify

Most requirement-level questions were resolved during story review. The following uncertainties remain and could affect the selected requirements.

### 1. Is Open Food Facts sufficiently complete for Canadian products?

**Question:** Does Open Food Facts provide adequate coverage of Canadian packaged foods, including ingredients, nutrition information, serving size, and net package quantity?

**How to clarify:** Test a representative sample of approximately 30 Canadian packaged products and record the lookup success rate and completeness of the required fields.

**Why it matters:** Product identification and ingredient analysis depend on database coverage, while whole-package nutrition requires a reliable package quantity or servings-per-package value. If coverage is insufficient, the fallback behavior or project scope may need to change.

### 2. How will net package quantity be obtained when it is missing?

**Question:** If a product is identified but the database does not provide a reliable package quantity or servings-per-package value, should the application request another source of that information or simply omit whole-package nutrition?

**How to clarify:** Measure how often package quantity is available during the Open Food Facts coverage test. If it is frequently unavailable, evaluate the simplest feasible fallback before final implementation.

**Current rule:** Until a reliable source is available, the application must not estimate whole-package nutrition from unsupported package information.

### 3. Which OCR approach can meet the extraction-accuracy requirement?

**Question:** Which OCR/extraction approach provides sufficient field accuracy and usable confidence information for Nutrition Facts photos?

**How to clarify:** Compare candidate approaches on a small set of representative label photos before running the full Q1 benchmark. Record field accuracy, latency, cost, and whether per-field confidence is available.

**Why it matters:** If the selected approach cannot reliably identify uncertain fields, the application may need stronger user-confirmation behavior.

### 4. Are uploaded product photos retained?

**Question:** Does the application store uploaded product or Nutrition Facts photos after processing?

**How to clarify:** Make an explicit team privacy decision before implementation.

**Preferred default:** Delete user-uploaded photos after extraction unless the user explicitly agrees to contribute an image to a test/benchmark dataset. Any retained benchmark images should not contain unnecessary personal information.

---

# Selected functional requirements

## F1 — Identify a packaged food by barcode and retrieve its food information

**Source issue:** [#10](https://github.com/suyeon240park/ECE444-Group20/issues/10)  
**Priority:** High

### User story

**As a consumer with little knowledge of food ingredients and chemicals, I want the app to identify a packaged food from its barcode and retrieve its ingredient and nutrition information so that I can have the product analyzed without needing to read, recognize, or type unfamiliar ingredient names or nutrition values myself.**

### Source and rationale

Ingredient lists often contain technical or unfamiliar names. A qualitative article quoting registered dietitians notes that many ingredient terms are unfamiliar to consumers and that names can sound more or less concerning than the evidence supports.

Source:  
https://globalnews.ca/news/2036179/making-informed-food-decisions-understanding-ingredient-lists/

A 2009 purposive study of 100 Canadian labels also documented legibility problems in mandatory food-label information.

Source:  
https://www.researchgate.net/publication/229648350_Ease_of_reading_of_mandatory_information_on_Canadian_food_product_labels

A nationally representative US study also found difficulty with several Nutrition Facts interpretation tasks, supporting the broader need to reduce manual interpretation burden.

Source:  
https://www.cdc.gov/pcd/issues/2017/17_0066.htm

Barcode-based retrieval is technically feasible using Open Food Facts, whose API can return product identity, ingredients, nutrition information, and package metadata when those fields are present.

Source:  
https://openfoodfacts.github.io/openfoodfacts-server/api/tutorial-off-api/

**Recorded limitation:** Open Food Facts is crowd-sourced, so individual entries can be incomplete or outdated. For the semester scope, the application treats a complete database result as the primary source and clearly identifies that source to the user. Nutrition Facts OCR is used as a fallback only when nutrition data required by the selected analysis is missing or incomplete.

**Assumption:** Avoiding manual transcription of unfamiliar ingredient names and nutrition values improves usability for non-expert consumers. This assumption is evaluated by Q3.

### Acceptance criteria

#### Primary path: barcode lookup

- The user can take a photo with the device camera or upload an existing image.
- The application attempts to detect a barcode from the submitted product image.
- When a barcode is detected, the application queries Open Food Facts for that barcode.
- A product lookup is considered sufficient for a **full product analysis** when it provides:
  - product identity;
  - an ingredient list; and
  - the nutrition fields required by the selected nutrient-analysis features.
- For this semester, the required nutrition fields are:
  - serving size;
  - calories;
  - total fat;
  - saturated fat;
  - sodium;
  - carbohydrate;
  - sugars;
  - fibre; and
  - protein,
  
  when the field is applicable to the product and represented by the selected Canadian Nutrition Facts model.
- Optional nutrition fields that are not used by the selected analysis do not by themselves trigger OCR.
- If the product is found with all required data, the application displays:
  - product name;
  - brand;
  - package quantity when available;
  - ingredient list;
  - available Nutrition Facts values; and
  - the data source.
- A complete database result does **not** require OCR verification as part of this semester scope.
- The application clearly identifies information retrieved from Open Food Facts as database-derived information.

#### Partial database nutrition data

- If product identity and ingredients are available but one or more required nutrition fields are missing, the application asks the user for an additional photo of the **Nutrition Facts table**.
- OCR fills only missing nutrition fields when the OCR serving basis matches the database serving basis.
- Database fields that are already present remain in use when both sources use the same serving basis.
- If the database serving size is missing or differs from the serving size read from the label, the application must not combine nutrition values from different serving bases. In this case, the OCR Nutrition Facts dataset becomes the nutrition source for that result.
- Each nutrition value indicates whether it came from:
  - the database; or
  - the Nutrition Facts label photo.

#### Nutrition-only fallback

- If no barcode is detected or the barcode is not found in the product database, the application offers to read a Nutrition Facts table from a photo.
- A Nutrition Facts-only result must be labelled **"Nutrition-only result"**.
- The application must not claim that the exact commercial product has been identified when barcode lookup failed.
- When product lookup fails:
  - the ingredient list is shown as **"Not available"**;
  - ingredient analysis under F4 is unavailable; and
  - ingredient-list OCR is not attempted.

#### Uncertain OCR values

- OCR-derived nutrition values that do not satisfy Q1's confidence/validation rules are marked as uncertain.
- Uncertain values are not used for nutrient explanations or whole-package calculations.
- The user is offered a **Retake photo** action.
- If a value still cannot be read sufficiently after another image, it is shown as **"Not available"** rather than guessed, inferred, or set to zero.
- OCR accuracy and validation requirements are defined by Q1.

#### Package quantity and F2

- When the product database provides net package quantity or servings-per-package, the application retrieves and retains that field and its source for possible use by F2.
- If neither a reliable servings-per-package value nor a reliable net package quantity is available, the application does not fabricate one and F2 must not calculate whole-package nutrition from an unsupported value.

#### No manual nutrition/ingredient transcription

- No step in the selected workflow requires the user to type an ingredient name or manually transcribe a Nutrition Facts value.

#### Failure and boundary cases

- If neither barcode lookup nor Nutrition Facts OCR can provide usable information, the application displays a clear next-step message such as:  
  **"We couldn't read this product. Try a clearer photo of the barcode or the Nutrition Facts table."**
- If a supported image cannot be processed, the application reports the failure instead of silently returning partial or fabricated information.

---

## F2 — Display calories and nutrients for the entire package

**Source issue:** [#2](https://github.com/suyeon240park/ECE444-Group20/issues/2)  
**Priority:** High

### User story

**As a consumer, I want to see the total calories and nutrients in the entire food package so that I can understand how much I would actually consume if I ate the whole product without manually calculating from the serving size.**

### Source and rationale

Health Canada states that the Nutrition Facts table is based on a serving size and that a person's actual portion may differ from the labelled serving size.

Source:  
https://www.canada.ca/en/health-canada/services/food-nutrition/nutrition-labelling/nutrition-facts-tables.html

Pelletier et al. found that 90% of participants in a 90-person study identified calories in one serving correctly but only 37% recognized that the snack packages contained multiple servings.

Source:  
https://pubmed.ncbi.nlm.nih.gov/15355944/

Canadian research has also examined how package size affects consumers' recognition and use of serving-size information.

Source:  
https://doi.org/10.3148/cjdpr-2018-020

The application therefore provides whole-package values as an additional interpretation layer while retaining the manufacturer's serving-based information for context.

### Acceptance criteria

- When sufficient nutrition and package/serving information is available, the application calculates nutrition values for the entire package.
- The application displays both:
  - the labelled **per-serving** nutrition values; and
  - the calculated **whole-package** nutrition values.
- Each basis is clearly labelled so that users cannot confuse per-serving and whole-package values.
- Whole-package values are calculated only from nutrition fields that are available and sufficiently reliable under F1/Q1.
- For a nutrient with an applicable current Health Canada Daily Value, the application may calculate a whole-package numeric %DV from the whole-package nutrient amount.
- A whole-package %DV must be labelled **"Calculated for whole package"** and must not reuse a per-serving %DV.
- The application does not invent a %DV where the applicable Health Canada labelling rules do not provide one.
- Calories are displayed as an energy amount and are not assigned a %DV.

#### Serving multiplier

The whole-package multiplier is determined in the following order:

1. use a reliable **servings-per-package/container** value when available;
2. otherwise, when a reliable net package quantity and serving size are available in compatible units, calculate:

   `number of servings = net package quantity / serving size`

- A derived multiplier uses the unrounded value internally.
- Only final displayed nutrition values are rounded.
- When the multiplier is derived rather than explicitly supplied, the whole-package result is labelled **"Approximate"**.

#### Source of package information

- Net package quantity is obtained from the verified product-data path in F1 when available.
- Q1 covers Nutrition Facts OCR fields; it does not treat net package quantity as part of the Nutrition Facts OCR benchmark.
- If neither reliable servings-per-package nor reliable net package quantity is available, the application does not calculate whole-package nutrition.

#### Failure and boundary cases

- If serving size and package quantity cannot be related using compatible units, no whole-package estimate is produced.
- The application displays:  
  **"Whole-package nutrition could not be calculated from the available serving and package information."**
- An OCR-derived serving-size or servings-per-package field that requires confirmation under Q1 must be confirmed before it is used in a whole-package calculation.
- A multi-serving product such as a large bottle or jar still displays the labelled per-serving values alongside whole-package values rather than replacing the serving view.

---

## F3 — Explain each nutrient in plain language with a credible source

**Source issue:** [#3](https://github.com/suyeon240park/ECE444-Group20/issues/3)  
**Priority:** High

### User story

**As a shopper without a nutrition background, I want each nutrient shown for a scanned product explained in plain language with a link to a credible source, so that I can understand what the numbers mean for my diet instead of guessing.**

### Source and rationale

A 2016 survey of 2,665 Canadians aged 16–30 found low knowledge of Health Canada's 5% and 15% DV interpretation thresholds.

Source:  
https://doi.org/10.3148/cjdpr-2019-010

A systematic review found that nutrition-label interpretation becomes less accurate as tasks become more complex and that interpretive aids can help consumers.

Source:  
https://ora.ox.ac.uk/objects/uuid:96041254-ce96-414d-a509-f5dbc7feb626

Health Canada explains that:

- 5% DV or less is "a little"; and
- 15% DV or more is "a lot"

for interpretation of Nutrition Facts information.

Source:  
https://www.canada.ca/en/health-canada/services/food-nutrition/nutrition-labelling/nutrition-facts-tables.html

The application deliberately avoids a single overall health score because the selected scope is educational: it explains individual nutrition information and its source rather than producing a universal verdict.

**Assumption:** Users prefer nutrient-by-nutrient explanations over a single overall product score. The usability/comprehension implications are evaluated in Q3.

### Acceptance criteria

#### Nutrient display

- For each supported nutrient available in the underlying data, the application displays its amount on the applicable serving basis.
- When an applicable %DV is supplied by the label/database or can be calculated from the Health Canada reference defined below, the application displays that %DV.
- When no applicable %DV is available under that reference, the application displays the nutrient amount without inventing a %DV.
- Calculated %DV values are explicitly labelled **"Calculated"**.
- Calculated %DV values use **Health Canada's Table of Daily Values for foods for adults and children 4 years of age or older**, using the version adopted by the team when this requirement is finalized.
- The exact Health Canada Daily Values table URL and effective version used by the application are stored with the calculation rules so that expected test results remain reproducible.
- If the team adopts a newer Daily Values table during the semester, that constitutes a requirements change and must be recorded and reviewed before the new values are used.
- Calculations use full precision internally and round only the final displayed %DV.

#### Per-serving interpretation

For the labelled per-serving basis:

- 5% DV or less is labelled **"a little"**;
- 15% DV or more is labelled **"a lot"**;
- values between those thresholds display their numeric %DV without attributing an additional category such as "moderate" to Health Canada.

The application distinguishes the context of nutrients users may want to limit from nutrients users may want more of, so the words "a little" and "a lot" are not presented as universal good/bad judgements.

#### Whole-package values

- Whole-package values from F2 may show a calculated numeric %DV where applicable.
- The official per-serving **"a little"/"a lot"** interpretation is not presented as though it were an official Health Canada classification of the calculated whole-package amount.
- Whole-package results are clearly labelled as calculated whole-package information.

#### Plain-language explanation

- Each supported nutrient has a concise explanation describing:
  - what the nutrient is or does, where relevant; and
  - how to interpret the displayed amount/reference information.
- Technical terms such as `%DV` have an inline definition or glossary link.
- Usability, comprehension, and readability of the explanations are evaluated under Q3 rather than through subjective wording alone in this functional requirement.

#### Source policy

- Every displayed health/nutrition explanation is backed by at least one reviewed source stored with the explanation.
- Initial approved source categories are:
  - Health Canada;
  - Canada's Food Guide;
  - WHO or another named international public-health authority explicitly approved by the team; and
  - specific peer-reviewed sources individually reviewed and stored with the explanation.
- The application does not dynamically invent an unsourced health claim.
- If no reviewed source supports an explanation, the application shows the numeric value and:  
  **"No verified explanation available yet."**
- Each explanation provides a visible source link.

#### Missing/uncertain information

- A nutrient value marked uncertain under Q1 is not explained as verified information until it is confirmed or replaced by a sufficiently reliable value.
- If a nutrient amount is unavailable, the application displays **"Not available"** rather than inferring it.
- If no usable nutrition information is available, the application explains that nutrient analysis cannot be produced.
- The result page displays no overall health score, letter grade, or universal "good/bad" verdict.

---

## F4 — Provide a quick, sourced ingredient summary for busy shoppers

**Source issue:** [#9](https://github.com/suyeon240park/ECE444-Group20/issues/9)  
**Priority:** Medium

### User story

**As a busy shopper, I want to see at a glance which ingredients in a product are of potential concern, with the option to read a sourced explanation only if I want to, so that I can make a quick decision without reading the full ingredient list or researching unfamiliar terms.**

### Source and rationale

A 2009 purposive study of 100 Canadian food labels found substantial legibility problems in ingredient lists and other mandatory label information.

Source:  
https://www.researchgate.net/publication/229648350_Ease_of_reading_of_mandatory_information_on_Canadian_food_product_labels

Registered dietitians quoted by Global News also noted that ingredient lists contain unfamiliar terminology and that an unfamiliar-sounding name does not itself establish whether an ingredient is concerning.

Source:  
https://globalnews.ca/news/2036179/making-informed-food-decisions-understanding-ingredient-lists/

The selected design therefore does not flag ingredients merely because their names sound technical. A flag must have an explicit evidence-backed reason stored in the reviewed ingredient knowledge base.

A useful example of why source transparency matters is titanium dioxide (E171), for which recognized authorities have published differing assessments.

EFSA assessment:  
https://www.efsa.europa.eu/en/news/titanium-dioxide-e171-no-longer-considered-safe-when-used-food-additive

Health Canada assessment:  
https://www.canada.ca/en/health-canada/services/food-nutrition/reports-publications/food-safety/titanium-dioxide-food-additive-science-report.html

The application presents materially differing positions with their sources rather than silently converting them into a universal "safe/unsafe" verdict.

**Assumption:** Busy shoppers benefit from seeing a short summary first and detailed evidence on request. This is evaluated through Q3.

### Ingredient knowledge policy

For the selected semester scope, the recognized food-safety/public-health authorities are:

- **Health Canada**;
- **European Food Safety Authority (EFSA)**;
- **U.S. Food and Drug Administration (FDA)**; and
- **WHO/JECFA**.

The reviewed ingredient knowledge base stores the authority and supporting source for each relevant claim. Adding or removing an authority from this set requires updating the reviewed ingredient-source policy.

An ingredient may be marked **flagged only if at least one of the following conditions applies**:

1. a recognized authority currently prohibits, restricts, withdraws authorization for, or publishes a formal food-safety warning concerning the ingredient's relevant food use; or
2. two or more recognized authorities have materially conflicting current safety assessments relevant to that food use.

Each flagged ingredient entry must contain:

- a non-empty `flag_reason`;
- the applicable flagging category;
- at least one directly supporting source for the flag; and
- the date the entry was last reviewed.

An ingredient is **not** flagged merely because its name is unfamiliar, technical, or chemical-sounding.

### Acceptance criteria

#### Ingredient-data source

- Ingredient analysis is performed only when F1 retrieves an ingredient list from the product database.
- Ingredient-list OCR is outside the selected semester scope.
- If no ingredient list is available, the application displays **"Ingredient information not available"** and does not claim to have checked the product's ingredients.

#### Coverage

- The result clearly shows ingredient-analysis coverage in the form:  
  **"Checked X of Y ingredients against our reviewed ingredient database."**
- Ingredients that are not represented in the reviewed knowledge base are listed under **"Not in our database yet."**
- A low-coverage result must not use language implying that the product as a whole has been found safe.
- If zero ingredients can be checked, the application states that no verified ingredient analysis is available.

#### Matching

- Reviewed ingredient entries have a canonical identifier.
- Matching may use:
  - canonical/common names;
  - explicitly stored aliases/synonyms; and
  - E-numbers or equivalent identifiers explicitly stored in the entry.
- Matching is case-insensitive and ignores surrounding punctuation.
- Bilingual or synonymous forms that resolve to the same canonical ingredient are counted once.
- Matching does not use uncontrolled substring rules that cause one ingredient name to match unrelated compounds.

#### Summary

- The result page shows a concise ingredient summary near the top of the analysis.
- For each flagged ingredient shown in the summary, display:
  - ingredient name; and
  - a one-line evidence-based reason.
- On a supported phone viewport, the summary displays up to the first three flagged ingredients without expanding the section.
- If more than three ingredients are flagged, the interface provides a **"Show N more"** control.
- If no reviewed ingredient is flagged, the summary states:  
  **"No flagged ingredients found among the ingredients checked."**
- The same summary must display coverage so that "no flagged ingredients" cannot be interpreted as "all ingredients were checked and proven safe."

#### Ingredient detail

For every ingredient represented in the reviewed knowledge base, whether flagged or not, the user can open a detail view containing:

- what the ingredient is;
- why it is used, when supported by a reviewed source;
- a concise evidence-backed explanation;
- at least one source link; and
- the date the entry was last reviewed.

For a flagged ingredient, the detail view additionally shows:

- the stored `flag_reason`; and
- which of the defined flagging categories applies.

#### Conflicting evidence

- When recognized authorities materially disagree, the application states each relevant position separately.
- Each stated position has its own source.
- The application does not describe the ingredient with a universal "safe" or "unsafe" verdict when the reviewed authorities materially disagree.

#### Failure and boundary cases

- Unknown ingredients are never labelled safe.
- Recognized-but-unflagged ingredients remain accessible in the full ingredient list with their reviewed neutral explanation.
- If a database ingredient list contains duplicate synonymous/bilingual entries that map to the same canonical ingredient, the UI does not count them as separate checked ingredients.

---

# Selected quality requirements

## Q1 — Nutrition values extracted from a label photo must match the printed label

**Source issue:** [#4](https://github.com/suyeon240park/ECE444-Group20/issues/4)  
**Quality attribute:** Accuracy  
**Priority:** High

### User story

**As a shopper who photographs a product label, I want the nutrition values the app reads from my photo to match what is printed on the label, so that the explanation I receive is about what I am actually eating.**

### Source and rationale

Health Canada uses %DV as an interpretation aid for Nutrition Facts information. A single OCR error can therefore materially change the information displayed to the user or propagate into F2's whole-package calculation.

Health Canada source:  
https://www.canada.ca/en/health-canada/services/food-nutrition/nutrition-labelling/nutrition-facts-tables.html

OCR on real food packaging is difficult because of effects such as glare, curved surfaces, dense layouts, and varied fonts.

Source referenced by the candidate issue:  
https://arxiv.org/abs/2510.03570

**Provisional assumption:** At least 95% aggregate field-level accuracy is achievable on human-readable phone photos with the selected extraction approach. The threshold is validated against the first benchmark and may be changed only through an explicit reviewed requirements revision.

### Acceptance criteria

#### Measure

1. **Aggregate field-level accuracy** of extracted Nutrition Facts values against manually verified ground truth.
2. **Critical-field accuracy/safe-use** for values that can change F2's serving multiplier.

An atomic field is one value used by the application after normalization, such as:

- serving-size household quantity;
- serving-size metric quantity;
- servings per package, when printed;
- calories;
- nutrient amount; or
- printed %DV.

For a compound serving statement such as `6 crackers (30 g)`:

- `6 crackers` is one field; and
- `30 g` is a separate field.

A field genuinely absent from the printed label is excluded from the accuracy denominator rather than counted as an extraction error.

A field is correct when its extracted semantic value matches the manually verified label value after allowed normalization such as whitespace/unit formatting.

#### Target

- At least **95% aggregate field-level accuracy** across the benchmark set.
- **100% safe-use compliance for critical multiplier fields:** an OCR-derived serving-size metric value or printed servings-per-package value must not be used in F2 unless:
  - it satisfies the team's validated confidence rule; and
  - when the UI requires confirmation under that rule, the user confirms it before use.
- Any field that falls below the configured confidence threshold is presented as uncertain and is not used as verified nutrition information.
- If the Nutrition Facts table cannot be found, the application returns **"Table not found"** rather than silently producing partial verified-looking values.

The 95% accuracy target and OCR confidence threshold are **provisional assumptions** until the first benchmark is run.

#### Conditions

- At least **50 distinct prepackaged products sold in Canada**.
- At least five product categories, such as:
  - snacks;
  - beverages;
  - dairy;
  - cereal/bread; and
  - frozen or packaged meals.
- Photos are taken with a phone camera under normal indoor lighting.
- The Nutrition Facts table is sufficiently in frame for a human reviewer to read.
- At least 10 benchmark images contain mild real-world difficulty such as glare or a curved package surface.
- Images that a human reviewer cannot read are excluded from the accuracy denominator and tracked separately as unsupported input.
- The OCR confidence threshold is selected and documented **before** final benchmark results are evaluated.
- Net package quantity is not part of this Nutrition Facts OCR benchmark; F1 supplies package metadata for F2 when available.

#### Verification method

1. Store the benchmark images in the test fixtures.
2. Manually transcribe ground truth.
3. Have a second teammate independently check the ground truth.
4. Run the extraction pipeline on every image.
5. Produce:
   - aggregate field accuracy;
   - per-field accuracy;
   - mismatch list;
   - critical-field safe-use results.
6. Run the benchmark in CI for changes that affect Nutrition Facts extraction.
7. A result below the accepted target fails the requirement.
8. If the target or confidence policy must change, revise this requirement explicitly and obtain reviewer confirmation before adopting the new target.

### Failure/boundary cases

- A missing printed field is not counted as an OCR failure.
- A compound serving-size statement is scored as separate atomic values.
- Low-confidence values are never silently converted into zero or treated as verified.
- A high aggregate score cannot override the safe-use rule for critical serving fields.

---

## Q2 — Identify uploaded food products within an acceptable response time

**Source issue:** [#5](https://github.com/suyeon240park/ECE444-Group20/issues/5)  
**Quality attribute:** Performance  
**Priority:** High

### User story

**As a consumer, I want product identification to complete quickly so that scanning a food product does not interrupt my shopping or food-selection experience.**

### Source and rationale

Product identification blocks the user from reaching the rest of the analysis. Nielsen Norman Group's response-time guidance identifies approximately 10 seconds as an important upper bound for maintaining user attention on an interaction.

Source:  
https://www.nngroup.com/articles/response-times-3-important-limits/

The shorter target is a **provisional project assumption** that must be validated against the actual barcode-detection and external product-data path.

### Acceptance criteria

#### Measure

**Server-side product-identification latency**, measured from the time the server has received the complete valid request/image to the time the application obtains either:

- a barcode/product-identification result; or
- an explicit identification-failure result.

This metric covers the **identification and primary product lookup stage only**.

It does not include:

- client-side upload time;
- optional Nutrition Facts OCR;
- nutrient explanation generation/rendering; or
- ingredient explanation rendering.

If identification succeeds while later analysis is still processing, the interface must visibly indicate that analysis is continuing.

#### Target

- At least **95% of primary barcode/product lookup requests complete within 5 seconds** under the conditions below.
- No valid identification request remains without either a result or an explicit timeout/failure state for more than **10 seconds**.
- If an implementation-level cache is used, cached results should be reported separately; a provisional target of **95% within 1 second** may be used for that optional path.

The 5-second target, optional 1-second cached target, and 20-concurrent-request workload are provisional assumptions until the selected service is benchmarked.

#### Conditions

- JPEG or PNG input.
- Image size of **10 MB or less**.
- Team's deployed test environment.
- Up to **20 concurrent product-identification requests**.
- External product service operating within its documented normal behavior and rate limits.
- The performance test reports external lookup and any optional cache path separately.

#### Verification method

1. Prepare a representative set of product images containing valid barcodes and defined failure cases.
2. Measure the external service's normal response behavior before configuring any controlled stub.
3. Run an automated load test at the specified concurrency.
4. Record:
   - percentage meeting the target;
   - p95 latency;
   - timeout/failure rate.
5. For controlled concurrency testing, a stub may model the measured normal latency of the external service.
6. Run a separate integration test against the real external service within its documented rate limits.
7. If a provisional target proves infeasible, explicitly revise the requirement and obtain reviewer confirmation before accepting a different target.

### Failure/boundary cases

- An unprocessable supported-size image returns a clear failure instead of waiting indefinitely.
- If the external service times out, the application returns an explicit failure within the 10-second maximum.
- An image larger than 10 MB is rejected before identification begins with instructions to provide a smaller image.
- If product identification succeeds while nutrition processing remains incomplete, the UI shows a loading/progress state for the remaining work.

---

## Q3 — Present food analysis that non-experts can understand and navigate without help

**Source issue:** [#11](https://github.com/suyeon240park/ECE444-Group20/issues/11)  
**Quality attribute:** Usability / Comprehensibility  
**Priority:** High

### User story

**As a consumer without a nutrition background, I want the food analysis to be easy to understand and navigate, so that I can find and interpret the information I need without outside assistance.**

### Source and rationale

The application is intended to reduce the interpretation burden of existing packaged-food information. Evidence already cited in the stakeholder section shows low knowledge of %DV thresholds among a Canadian youth/young-adult sample and supports the use of interpretation aids.

Additional target justification:

- Small formative tests with approximately five users are commonly used to identify major usability problems.  
  Source: https://www.nngroup.com/articles/why-you-only-need-to-test-with-5-users/

- The candidate issue uses an 80% task-success target, informed by a reported average task-completion benchmark of approximately 78% across a large set of usability tasks.  
  Source: https://measuringu.com/task-completion/

- A SUS score of 68 is used as a conventional average benchmark in the candidate rationale.  
  Source: https://www.lyssna.com/blog/system-usability-scale/

- The candidate rationale uses grade 8 as a readability target by analogy to guidance discussed in health/patient-material readability research.  
  Source: https://journals.sagepub.com/doi/pdf/10.1177/2374373521998847

**Provisional assumptions:**

- five participants are sufficient for the milestone's initial formative usability check;
- 80% overall unassisted task success is an appropriate initial pass target;
- a SUS mean of 68 is an appropriate initial benchmark;
- grade 8 or below is an appropriate target for the explanatory prose corpus.

These targets are revisited after the first usability test only through an explicit reviewed requirements change.

### Acceptance criteria

#### Measure

Three usability measures are evaluated.

##### 1. Unassisted task success

The percentage of participant-task attempts completed correctly without facilitator help.

The four tasks correspond directly to selected functional requirements:

- **T1 — F1:** scan/upload a product image and reach the product or nutrition-only result.
- **T2 — F2:** find the whole-package calorie value for a product for which F2 can calculate it.
- **T3 — F3:** find the sodium information and explain what the displayed amount/%DV means.
- **T4 — F4:** find a reviewed ingredient's explanation and source.

A participant response is correct only when it satisfies a written answer rubric prepared before testing.

For open-ended T3/T4 responses, the rubric lists the concepts that must be present. Two teammates independently score the response notes; disagreements are resolved before final success rates are calculated.

"Help" means:

- a navigation or interpretation hint from the facilitator;
- asking a team member for the answer; or
- leaving the application to search for the information elsewhere.

Giving up counts as failure.

##### 2. Perceived usability

Mean **System Usability Scale (SUS)** score after participants complete the tasks.

##### 3. Readability

Flesch-Kincaid grade level of the application's explanatory prose corpus for the products used in the test.

Before scoring:

- product and ingredient proper names are excluded;
- source citations/URLs are excluded; and
- technical terms that are separately defined in the UI may be excluded from the prose score.

Readability is evaluated across a sufficiently long combined prose sample rather than treating a one-sentence ingredient name/explanation as a statistically reliable standalone passage.

#### Target

- **Overall unassisted task success:** at least **80%** of all participant-task attempts.
- **Per-task floor:** each task is completed successfully by at least **3 of 5 participants**.
- **SUS:** mean score of at least **68**.
- **Readability:** mean Flesch-Kincaid grade of **8 or below** across the evaluated explanatory prose corpus.

These are provisional initial targets.

#### Conditions

- At least **5 participants**.
- Participants are outside the development team.
- Participants answer **no** when asked whether they have professional or formal academic training in nutrition or food science.
- Test products cover at least **3 packaged-food categories**.
- Testing uses the team's deployed responsive web application.
- At least:
  - 3 participants use a phone-size browser; and
  - 2 participants use a desktop/laptop-size browser.
- Participants use a normal network connection.
- The facilitator provides no hints after each task begins.
- Each task ends when the participant:
  - completes it;
  - gives up; or
  - asks for help.
- Time-on-task may be recorded for information but is not a pass/fail target in this requirement.
- If an identification request violates Q2's accepted 10-second maximum because of a system-performance failure, that event is recorded against Q2 and the usability task is re-run rather than being counted as an interpretation/navigation failure.

#### Verification method

1. Write the usability-test script and answer rubric before testing.
2. Use the same defined task wording for all participants.
3. Record task outcomes in an anonymized table without names or unnecessary personal information.
4. Have two teammates independently score open-ended T3/T4 answers using the predefined rubric.
5. Calculate:
   - overall task-success rate;
   - per-task success rate.
6. After the tasks, administer the standard SUS questionnaire and calculate the mean SUS score.
7. Run a reproducible readability script over the selected explanatory prose corpus using the preprocessing rules defined above.
8. Record the mean Flesch-Kincaid grade.
9. If a target is missed:
   - identify the observed usability problem;
   - revise the interface or requirement as appropriate; and
   - retest with new participants.
10. Any change to an accepted target must be recorded as a requirements revision and checked by a reviewer before acceptance.

### Failure/boundary cases

Functional failure behavior is owned by the corresponding functional requirement:

- scan/product lookup failure → F1;
- unavailable whole-package calculation → F2;
- missing/uncertain nutrient data → F3/Q1;
- missing ingredient data/coverage → F4.

Q3 evaluates whether users can understand and navigate the supported outcomes defined by those functional requirements.
