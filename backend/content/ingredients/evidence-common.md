# Common-ingredient evidence and selection (#34)

Author research and wording check: **2026-10-14**, performed by the coding agent.
**Alex's independent source and wording approval: pending; required before merge.**
No automated check or date below represents that approval.

The 25 schema-version-1 files in [entries/](entries/) contain English explanations
and explicit French aliases. Each sourced field points to sources in its own file.
`accessed_on` and `last_reviewed` record this author's actual access/review date.
`published_on` is null except for the pasta paper's explicit 2021-03-11 date:
a page's modification or migration date is not assumed to be its original
publication date. This is common-ingredient education, not a
four-authority safety review. Empty authority positions mean none recorded;
`flag: null` does not mean an authority has declared the ingredient safe.

## Selection method

Start with the frozen [#28 sample](../../tests/fixtures/ingredients/off_sample_issue28.json):
30 products, 29 found, 21 with selected ingredient text. Count each canonical
identity **once per distinct product**, including components; combine only the
explicit aliases in these files. The replay's `production.distinct_product_frequency`
makes the count reproducible. Counts reflect recognized names in the frozen OFF
text, not package-verified prevalence. Malformed source text and parser limits
can hide or invent candidates. Repeated bilingual/variety-pack occurrences do
not increase frequency.

This is a frequency-led selection supplemented by the agreed ingredient families,
not a claim that these are Canada's 25 most frequent ingredients. Salt, water,
natural flavour, modified corn starch, oils, dairy, and produce recur in #28.
Corn syrup and soy lecithin are explicit #34 examples despite zero exact matches
in this sample; sunflower oil completes the agreed common-oil family. The
Hardbite sunflower/canola oils are qualified as non-hydrogenated and remain
unmatched; Lipton's malformed “dry extracts of corn syrup” is not an alias for
corn syrup. No candidate needed replacement for lack of basic identity/use evidence.

Other frequent candidates include nutrients and colour additives whose authority
assessment belongs to #35. General spices and source-unspecified ingredients
need broader, separately researched entries. No coverage target drove aliases.

## Claim and alias matrix

Counts below use the final #34 aliases. Source keys link to the catalogue below;
section names identify the evidence to check. “Function” also covers the short
`explanation` field. The JSON records contain the exact wording and source IDs.

| Entry | Products / 30 | Identity evidence | Function / explanation evidence | Alias evidence and limits |
| --- | ---: | --- | --- | --- |
| [water](entries/water.json) | 8 | [labels](#source-labels): Ingredients / Components | [enchiladas](#source-enchiladas): Directions 4 (consistency) | [labels_fr](#source-labels-fr): Constituants (`eau`) |
| [salt](entries/salt.json) | 9 | [standards](#source-standards): 14.1 | [seasonings](#source-seasonings): Background (seasoning mixtures) | [standards_fr](#source-standards-fr): Volume 14 (`sel`) |
| [sugar](entries/sugar.json) | 2 | [fda_types](#source-fda-types): Sweeteners | [fda_types](#source-fda-types): Sweeteners; [names](#source-names): Table 2, item 16 | [labels_fr](#source-labels-fr): sugar examples (`sucre`); [labels](#source-labels): Annex 1 (`sucrose`/`saccharose`) |
| [brown_sugar](entries/brown_sugar.json) | 2 | [standards](#source-standards): 15.1.6 | [standards](#source-standards): Volume 15; [fda_types](#source-fda-types): Sweeteners | [standards](#source-standards) / [standards_fr](#source-standards-fr): 15.1.6 (`golden sugar`, `cassonade`, `sucre brun`); golden sugar observed in Cheerios 065633132832 |
| [corn_syrup](entries/corn_syrup.json) | 0 | [fda_syrup](#source-fda-syrup): Where does HFCS come from? | [fda_types](#source-fda-types): Sweeteners; [fda_syrup](#source-fda-syrup): production distinction | [labels_fr](#source-labels-fr): Pretzel example (`sirop de maïs`); explicit unaccented spelling |
| [glucose_fructose](entries/glucose_fructose.json) | 1 | [names](#source-names): Table 2, item 17 | [names](#source-names): item 17; [fda_types](#source-fda-types): Sweeteners | [names_fr](#source-names-fr): Table 2, item 17; same spelling in both languages |
| [vegetable_oil](entries/vegetable_oil.json) | 4 | [standards](#source-standards): 8.1.1 | [fats](#source-fats): food preparation; [chowder](#source-chowder): Directions 1 | [labels_fr](#source-labels-fr): allergen example (`huile végétale`); explicit unaccented spelling |
| [canola_oil](entries/canola_oil.json) | 2 | [oils](#source-oils): Canola-quality oil derived from Brassica juncea | [fats](#source-fats): food preparation / cooking swaps | [fats_fr](#source-fats-fr): food preparation (`huile de canola`) |
| [sunflower_oil](entries/sunflower_oil.json) | 0 | [standards](#source-standards): 8.1.8 | [fats](#source-fats): food preparation | [standards](#source-standards) / [standards_fr](#source-standards-fr): 8.1.8 (sunflower seed / tournesol) |
| [corn_oil](entries/corn_oil.json) | 1 | [standards](#source-standards): 8.1.5 | [standards](#source-standards): vegetable-oil classification; [fats](#source-fats): general food preparation | [standards](#source-standards) / [standards_fr](#source-standards-fr): 8.1.5 (maize / maïs); explicit unaccented spelling |
| [soybean_oil](entries/soybean_oil.json) | 1 | [standards](#source-standards): 8.1.7 | [fats](#source-fats): food preparation / cooking swaps | [standards](#source-standards) / [standards_fr](#source-standards-fr): 8.1.7 (soya / soja / soya) |
| [coconut_oil](entries/coconut_oil.json) | 1 | [standards](#source-standards): 8.1.1 (named plant source) | [fats](#source-fats): [oils](#source-oils) and [fats](#source-fats) used in food preparation | [fats_fr](#source-fats-fr): saturated [oils](#source-oils) list (`huile de noix de coco`); shorter `huile de coco` [names](#source-names) the same source |
| [wheat_flour](entries/wheat_flour.json) | 2 | [standards](#source-standards): 12.1.1 | [chowder](#source-chowder): Ingredients and Directions 1–2 | [standards_fr](#source-standards-fr): 12.1.1 (farine / blé), explicit source retained; unaccented spelling |
| [durum_wheat_semolina](entries/durum_wheat_semolina.json) | 1 | [durum](#source-durum): B1 General description, cultivation and use | [pasta_paper](#source-pasta-paper): section 2.1 and semolina control; [durum](#source-durum): B1 | [durum_fr](#source-durum-fr): B1 (semoule / blé dur); shortened English `durum semolina` |
| [whole_grain_oats](entries/whole_grain_oats.json) | 1 | [grains](#source-grains): Whole grain foods are good for you | [grains](#source-grains): Choosing and preparing / oatmeal snack example | [grains_fr](#source-grains-fr): Choisissez et préparez (`avoine à [grains](#source-grains) entiers`); English hyphen/space variant |
| [corn_starch](entries/corn_starch.json) | 4 | [starch](#source-starch): Policy | [mapo](#source-mapo): Directions 4 | [labels_fr](#source-labels-fr): sugar-grouping examples (`amidon de maïs`); cornstarch spelling in [starch](#source-starch); maize/corn terminology in [standards](#source-standards) 8.1.5; unaccented spelling |
| [modified_corn_starch](entries/modified_corn_starch.json) | 5 | [names](#source-names): Table 1, item 21; [labels](#source-labels): mandatory common [names](#source-names) | [fda_types](#source-fda-types): Fat replacers | [labels](#source-labels) / [labels_fr](#source-labels-fr): Components examples; spacing and explicit unaccented variants |
| [soy_lecithin](entries/soy_lecithin.json) | 0 | [labels](#source-labels): Mandatory common [names](#source-names) | [fda_types](#source-fda-types): Emulsifiers | [labels_fr](#source-labels-fr): `lécithine de soja`; soybean/soya naming in [standards](#source-standards) 8.1.7 supports plant-name variants |
| [skim_milk](entries/skim_milk.json) | 4 | [standards](#source-standards): 7.1.2 | [chowder](#source-chowder): Ingredients and Directions 2 | [standards_fr](#source-standards-fr): 7.1.2 (`lait écrémé`); skim/skimmed wording and explicit unaccented spelling |
| [cream](entries/cream.json) | 4 | [standards](#source-standards): 7.2.1 | [standards](#source-standards): 7.1.2 vs 7.2.1; [fats](#source-fats): dairy fat comparison | [standards_fr](#source-standards-fr): 7.2.1 (`crème`); explicit unaccented spelling |
| [potatoes](entries/potatoes.json) | 3 | [potato](#source-potato): morphology / tubers | [potato](#source-potato): 4.3 Cultivation and use; [pie](#source-pie): Ingredients, Directions 1 and 5 | Frozen Lay's 060410047019 bilingual list establishes `pommes de terre` and both specially-selected phrases; singular/plural variants retain the identity |
| [tomato_paste](entries/tomato_paste.json) | 2 | [canned](#source-canned): item 7; [standards](#source-standards): 10.2.5 | [canned](#source-canned): item 7 | [standards_fr](#source-standards-fr): 10.2.5 (`pâte de tomates`); singular tomato variant |
| [onion_powder](entries/onion_powder.json) | 3 | [seasonings](#source-seasonings): Background | [seasonings](#source-seasonings): Background; [enchiladas](#source-enchiladas): Directions 3 | [enchiladas_fr](#source-enchiladas-fr): Ingredients / Directions 3 (`poudre d’oignon`); straight/curly apostrophes |
| [garlic](entries/garlic.json) | 2 | [labels](#source-labels): Definitions, spices/herbs/[seasonings](#source-seasonings) | [fats](#source-fats): Ideas for meals and snacks (dressings) | [chowder_fr](#source-chowder-fr): Ingredients (`ail`) |
| [natural_flavour](entries/natural_flavour.json) | 7 | [names](#source-names): Table 2, item 4 | [fda_types](#source-fda-types): Flavors and spices; [names](#source-names): collective name | [labels_fr](#source-labels-fr): sugar-grouping examples (`arôme naturel`); [fda_types](#source-fda-types): natural flavoring; English spelling/plural and explicit unaccented French variants |

## Evidence interpretation and boundaries

Recipes from Health Canada demonstrate specific culinary uses; they do not
establish the intent of a packaged-food manufacturer. Statements therefore use
“can,” “such as,” or general uses. For corn oil, the preparation-fat description
is an inference from its official classification as a vegetable oil and the
Food Guide's general oil-use guidance, not a claim about a particular frying
temperature. CFIA sources establish composition and terminology, not safety
endorsements. The FDA starch naming rule is US-specific: it is **not** used to
map a Canadian generic “starch” label to corn starch.

Only exact, listed variants are matched. Accent omission, pluralization and
apostrophe variants are explicitly authored spelling variants, not automatic
translation rules. Alex must review these equivalences as well as the prose.
The frozen bilingual Lay's text supports its potato aliases; a teammate has
not yet checked that OFF transcription against a physical package.

Keep these boundaries:

- No generic starch, modified starch, lecithin, E322 or INS 322 aliases to a
  plant-specific entry. No additive identifiers are assigned in this batch.
- No generic milk, powdered skim milk or modified milk ingredients mapped to
  skim milk or cream; no enriched/whole-wheat flour mapped to plain wheat flour.
- No hydrogenated or high-oleic oil grades, sea salt, or whole-grain rolled oats
  silently collapsed into an unqualified name. These qualified forms remain
  candidates for separately reviewed content/alias decisions.
- Brown sugar's “golden sugar” alias is explicitly supported by the same Canadian
  standard (15.1.6). Golden syrup is distinct. Cane-source sugar and the “Sugars”
  grouping heading are not aliases in this batch.
- Canada's glucose-fructose common name is broader than corn-derived HFCS;
  source and exact proportions cannot be inferred. No HFCS or generic glucose
  syrup alias is added to that entry.
- Flavour without “natural,” artificial flavour, and named flavours such as
  natural vanilla flavour are not mapped to this generic natural-flavour entry.
- Potato starch, tomato purée, onion salt, garlic powder, and source-unspecified
  semolina remain distinct. “Patates” is deferred rather than inferred here.

There is no parser, counting-policy, schema or public API change. Named compound
parents and their named components continue to count. Flag-focused authority
assessment remains #35; HTTP/UI integration remains #43/#40.

## Source catalogue

All links below were accessed on 2026-10-14. The exact host `mdpi-res.com` is
added for the publisher-hosted pasta paper PDF, which was accessible when the
article landing page returned HTTP 429. The paper was individually read for its
ingredient/use evidence (section 2.1 and the semolina control); no health-benefit
claims are imported. It supplements CFIA's crop terminology. This addition does
not change flagging-authority hosts or approve every paper on that host; new
papers still need individual evidence review. Alex's review remains pending.


<a id="source-pasta-paper"></a>

- **pasta_paper** — Messia et al., [Nutritional and Technological Quality of High Protein Pasta](https://mdpi-res.com/d_attachment/foods/foods-10-00589/article_deploy/foods-10-00589.pdf), *Foods* 10(3), 589, DOI 10.3390/foods10030589, published 2021-03-11. Section 2.1 documents durum semolina used in pasta; the introduction describes the 100% semolina control. Supports semolina's `why_used` and `explanation` alongside the CFIA identity source.


<a id="source-canned"></a>

- **canned** — [Eight canned foods to keep on hand](https://www.canada.ca/en/health-canada/services/food-guide/eating-support/kitchen/cooking-skills/eight-canned-foods-keep-hand.html) (Health Canada).

<a id="source-chowder"></a>

- **chowder** — [Creamy clam chowder](https://www.canada.ca/en/health-canada/services/food-guide/eating-support/kitchen/recipes/creamy-clam-chowder.html) (Health Canada).

<a id="source-chowder-fr"></a>

- **chowder_fr** — [Chaudrée de palourdes crémeuse](https://www.canada.ca/fr/sante-canada/services/guide-alimentaire/manger-favoriser/cuisine/recettes/chaudree-palourdes-cremeuse.html) (Santé Canada).

<a id="source-durum"></a>

- **durum** — [The biology of Triticum turgidum ssp. durum (durum wheat)](https://inspection.canada.ca/en/plant-varieties/plants-novel-traits/applicants/directive-94-08/biology-documents/triticum-turgidum-ssp-durum) (Canadian Food Inspection Agency).

<a id="source-durum-fr"></a>

- **durum_fr** — [La biologie du Triticum turgidum ssp. durum (blé dur)](https://inspection.canada.ca/fr/varietes-vegetales/vegetaux-caracteres-nouveaux/demandeurs/directive-94-08/documents-biologie/triticum-turgidum-ssp-durum) (Agence canadienne d'inspection des aliments).

<a id="source-enchiladas"></a>

- **enchiladas** — [Black bean enchiladas](https://www.canada.ca/en/health-canada/services/food-guide/eating-support/kitchen/recipes/black-bean-enchiladas.html) (Health Canada).

<a id="source-enchiladas-fr"></a>

- **enchiladas_fr** — [Enchiladas aux haricots noirs](https://www.canada.ca/fr/sante-canada/services/guide-alimentaire/manger-favoriser/cuisine/recettes/enchiladas-haricots-noirs.html) (Santé Canada).

<a id="source-fats"></a>

- **fats** — [Choose foods with healthy fats](https://www.canada.ca/en/health-canada/services/food-guide/explore/healthy-eating-recommendations/eat-variety/choosing-healthy-fats.html) (Health Canada).

<a id="source-fats-fr"></a>

- **fats_fr** — [Choisissez des aliments contenant de bons gras](https://www.canada.ca/fr/sante-canada/services/guide-alimentaire/explorez/recommandations-matiere-alimentation-saine/savourez-variete/choisir-bons-gras.html) (Santé Canada).

<a id="source-fda-syrup"></a>

- **fda_syrup** — [High Fructose Corn Syrup Questions and Answers](https://www.fda.gov/food/food-additives-petitions/high-fructose-corn-syrup-questions-and-answers) (FDA).

<a id="source-fda-types"></a>

- **fda_types** — [Types of Food Ingredients](https://www.fda.gov/food/food-additives-and-gras-ingredients-information-consumers/types-food-ingredients) (FDA).

<a id="source-grains"></a>

- **grains** — [Eat whole grain foods](https://www.canada.ca/en/health-canada/services/food-guide/explore/healthy-eating-recommendations/eat-variety/eat-whole-grains.html) (Health Canada).

<a id="source-grains-fr"></a>

- **grains_fr** — [Mangez des aliments à grains entiers](https://www.canada.ca/fr/sante-canada/services/guide-alimentaire/explorez/recommandations-matiere-alimentation-saine/savourez-variete/mangez-grains-entiers.html) (Santé Canada).

<a id="source-labels"></a>

- **labels** — [List of ingredients and allergens on food labels](https://inspection.canada.ca/en/food-labels/labelling/industry/list-ingredients-and-allergens) (Canadian Food Inspection Agency).

<a id="source-labels-fr"></a>

- **labels_fr** — [Liste d'ingrédients et allergènes sur les étiquettes des aliments](https://inspection.canada.ca/fr/etiquetage-aliment/etiquetage/industrie/liste-dingredients-allergenes) (Agence canadienne d'inspection des aliments).

<a id="source-mapo"></a>

- **mapo** — [Mapo tofu with chicken](https://www.canada.ca/en/health-canada/services/food-guide/eating-support/kitchen/recipes/mapo-tofu-chicken.html) (Health Canada).

<a id="source-names"></a>

- **names** — [Common Names for Ingredients and Components](https://inspection.canada.ca/en/about-cfia/acts-and-regulations/list-acts-and-regulations/documents-incorporated-reference/common-names-ingredients-and-components) (Canadian Food Inspection Agency).

<a id="source-names-fr"></a>

- **names_fr** — [Noms usuels d'ingrédients et de constituants](https://inspection.canada.ca/fr/propos-lacia/lois-reglements/liste-lois-reglements/documents-incorpores-renvoi/noms-usuels-dingredients-constituants) (Agence canadienne d'inspection des aliments).

<a id="source-oils"></a>

- **oils** — [Labelling requirements for fats and oils](https://inspection.canada.ca/en/food-labels/labelling/industry/fats-and-oils) (Canadian Food Inspection Agency).

<a id="source-pie"></a>

- **pie** — [Turkey and lentil shepherd's pie](https://www.canada.ca/en/health-canada/services/food-guide/eating-support/kitchen/recipes/turkey-lentil-shepherds-pie.html) (Health Canada).

<a id="source-potato"></a>

- **potato** — [The Biology of Solanum tuberosum (L.) (Potatoes)](https://inspection.canada.ca/en/plant-health/plant-varieties/novel-traits/applicants/directive-94-08/biology-documents/solanum-tuberosum) (Canadian Food Inspection Agency).

<a id="source-seasonings"></a>

- **seasonings** — [CPG Sec 525.650 Labeling of Seasonings](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/cpg-sec-525650-labeling-seasonings) (FDA).

<a id="source-standards"></a>

- **standards** — [Canadian Food Compositional Standards](https://inspection.canada.ca/en/about-cfia/acts-and-regulations/list-acts-and-regulations/documents-incorporated-reference/canadian-food-compositional-standards-0) (Canadian Food Inspection Agency).

<a id="source-standards-fr"></a>

- **standards_fr** — [Normes canadiennes de composition des aliments](https://inspection.canada.ca/fr/propos-lacia/lois-reglements/liste-lois-reglements/documents-incorpores-renvoi/normes-canadiennes-composition-aliments-0) (Agence canadienne d'inspection des aliments).

<a id="source-starch"></a>

- **starch** — [CPG Sec 578.100 Starches - Common or Usual Names](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/cpg-sec-578100-starches-common-or-usual-names) (FDA).

## Review handoff

Alex should check each source section against the JSON wording, confirm alias
equivalence and selection exceptions, and record approval in the PR review.
Review is pending for **all 25 entries**. Any ingredient requiring a substantive
authority-action/conflicting-assessment investigation should be handed to #35,
not given an unsupported flag in this batch. The author must address review
findings before merge.

Validation and remaining limitations are in the
[replay summary](../../../docs/validation/issue34-common-entries.md).
