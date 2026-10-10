from datetime import datetime, timedelta, timezone

import pytest

from app.models.product import (
    ALL_NUTRIENTS,
    CANONICAL_UNITS,
    REQUIRED_NUTRIENTS,
    ApiError,
    Certainty,
    Completeness,
    DataSource,
    ErrorCode,
    NutrientValue,
    Nutrition,
    NutritionBasis,
    Package,
    Product,
    ProductResult,
    ResultType,
    Serving,
    Source,
    compute_missing_fields,
    is_valid_barcode,
)

RETRIEVED_AT = datetime(2026, 10, 8, 14, 0, tzinfo=timezone.utc)
OFF = Source.OPEN_FOOD_FACTS
PHOTO = Source.NUTRITION_LABEL_PHOTO


def off_value(name: str, amount: float = 1) -> NutrientValue:
    return NutrientValue(amount, CANONICAL_UNITS[name], OFF, Certainty.REPORTED)


def full_nutrition(**overrides: NutrientValue | None) -> Nutrition:
    nutrients = {name: off_value(name) for name in REQUIRED_NUTRIENTS}
    nutrients.update(overrides)
    return Nutrition(NutritionBasis.SERVING, nutrients)


def complete_product(**overrides) -> Product:
    fields = dict(
        source=DataSource(
            OFF, RETRIEVED_AT, url="https://world.openfoodfacts.org/product/0012345678905"
        ),
        barcode="0012345678905",
        name="Whole Wheat Crackers",
        brand="Example Foods",
        ingredients_text="Whole wheat flour, salt.",
        serving=Serving("6 crackers (30 g)", 30, "g", OFF),
        package=Package("300 g", 300, "g", None, OFF),
        nutrition=full_nutrition(),
    )
    fields.update(overrides)
    return Product(**fields)


def photo_source() -> DataSource:
    return DataSource(PHOTO, RETRIEVED_AT)


# --- serialization -------------------------------------------------------------------------------


def test_empty_product_emits_every_key_as_null():
    body = Product(source=DataSource(OFF, RETRIEVED_AT)).to_dict()

    assert body["barcode"] is None
    assert body["name"] is None
    assert body["brand"] is None
    assert body["ingredients_text"] is None
    assert body["serving"] == {"size_text": None, "quantity": None, "unit": None, "source": None}
    assert body["package"] == {
        "quantity_text": None,
        "quantity": None,
        "unit": None,
        "servings_per_package": None,
        "source": None,
    }
    assert body["nutrition"]["basis"] is None
    assert body["nutrition"]["nutrients"] == {name: None for name in ALL_NUTRIENTS}


def test_nutrition_fills_every_unpassed_nutrient_with_none():
    nutrition = Nutrition(NutritionBasis.SERVING, {"calories": off_value("calories", 140)})

    assert list(nutrition.nutrients) == list(ALL_NUTRIENTS)
    assert nutrition.nutrients["fibre"] is None
    assert nutrition.to_dict()["nutrients"]["calories"] == {
        "amount": 140,
        "unit": "kcal",
        "daily_value_percent": None,
        "source": "open_food_facts",
        "certainty": "reported",
    }


def test_zero_amount_is_kept_and_distinct_from_missing():
    nutrition = Nutrition(NutritionBasis.SERVING, {"trans_fat": off_value("trans_fat", 0)})

    nutrients = nutrition.to_dict()["nutrients"]
    assert nutrients["trans_fat"]["amount"] == 0
    assert nutrients["cholesterol"] is None


def test_enums_serialize_to_contract_strings():
    assert [s.value for s in Source] == ["open_food_facts", "nutrition_label_photo"]
    assert [c.value for c in Certainty] == ["reported", "confident", "uncertain"]
    assert [b.value for b in NutritionBasis] == ["serving", "100g", "100ml"]
    assert [r.value for r in ResultType] == ["product", "nutrition_only"]
    assert [c.value for c in Completeness] == ["complete", "incomplete"]


def test_datasource_serializes_datetimes_as_utc_iso():
    toronto = timezone(timedelta(hours=-4))
    source = DataSource(
        OFF,
        datetime(2026, 10, 8, 10, 0, tzinfo=toronto),
        last_modified_at=datetime(2026, 3, 20, 9, 30, tzinfo=timezone.utc),
    )

    assert source.to_dict() == {
        "provider": "open_food_facts",
        "url": None,
        "retrieved_at": "2026-10-08T14:00:00Z",
        "last_modified_at": "2026-03-20T09:30:00Z",
    }


@pytest.mark.parametrize("field", ["retrieved_at", "last_modified_at"])
def test_datasource_rejects_naive_datetimes(field):
    kwargs = {"retrieved_at": RETRIEVED_AT, field: datetime(2026, 10, 8, 14, 0)}
    with pytest.raises(ValueError, match="timezone-aware"):
        DataSource(OFF, **kwargs)


# --- validation ----------------------------------------------------------------------------------


def test_nutrient_rejects_negative_amount():
    with pytest.raises(ValueError, match="negative"):
        NutrientValue(-1, "g", OFF, Certainty.REPORTED)


def test_nutrient_rejects_negative_daily_value():
    with pytest.raises(ValueError, match="daily_value_percent"):
        NutrientValue(1, "g", PHOTO, Certainty.CONFIDENT, daily_value_percent=-5)


@pytest.mark.parametrize("certainty", [Certainty.CONFIDENT, Certainty.UNCERTAIN])
def test_database_values_must_be_reported(certainty):
    with pytest.raises(ValueError, match="reported"):
        NutrientValue(1, "g", OFF, certainty)


def test_photo_values_cannot_be_reported():
    with pytest.raises(ValueError, match="confident"):
        NutrientValue(1, "g", PHOTO, Certainty.REPORTED)


def test_nutrition_rejects_wrong_unit():
    grams_of_sodium = NutrientValue(0.043, "g", OFF, Certainty.REPORTED)
    with pytest.raises(ValueError, match="sodium must be in 'mg'"):
        Nutrition(NutritionBasis.PER_100G, {"sodium": grams_of_sodium})


def test_nutrition_rejects_unknown_nutrient():
    with pytest.raises(ValueError, match="unknown nutrients"):
        Nutrition(NutritionBasis.SERVING, {"vitamin_z": off_value("protein")})


def test_nutrition_with_values_requires_basis():
    with pytest.raises(ValueError, match="no basis"):
        Nutrition(None, {"protein": off_value("protein")})


@pytest.mark.parametrize("cls", [Serving, Package])
def test_values_without_source_are_rejected(cls):
    with pytest.raises(ValueError, match="no source"):
        cls(quantity=30, unit="g")


@pytest.mark.parametrize("cls", [Serving, Package])
def test_source_without_values_is_rejected(cls):
    with pytest.raises(ValueError, match="no values"):
        cls(source=OFF)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"quantity": 0},
        {"quantity": -30},
        {"servings_per_package": 0},
    ],
)
def test_package_quantities_must_be_positive(kwargs):
    with pytest.raises(ValueError, match="positive"):
        Package(source=OFF, **kwargs)


def test_serving_rejects_unknown_unit():
    with pytest.raises(ValueError, match="serving.unit"):
        Serving("1 cup", 1, "cup", OFF)


@pytest.mark.parametrize("barcode", ["3017624010701", "12345678", "12345678901234"])
def test_valid_barcodes(barcode):
    assert is_valid_barcode(barcode)
    assert complete_product(barcode=barcode).barcode == barcode


@pytest.mark.parametrize(
    "barcode", ["1234567", "123456789012345", "30176240107O1", " 3017624010701", ""]
)
def test_invalid_barcodes(barcode):
    assert not is_valid_barcode(barcode)
    with pytest.raises(ValueError, match="barcode"):
        complete_product(barcode=barcode)


@pytest.mark.parametrize("field", ["name", "brand", "ingredients_text"])
@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_text_must_be_none(field, blank):
    with pytest.raises(ValueError, match="blank"):
        complete_product(**{field: blank})


# --- completeness --------------------------------------------------------------------------------


def test_complete_product_has_no_missing_fields():
    result = ProductResult(ResultType.PRODUCT, complete_product())

    assert result.missing_fields == []
    assert result.completeness is Completeness.COMPLETE
    body = result.to_dict()
    assert body["completeness"] == "complete"
    assert body["missing_fields"] == []
    assert body["result"] == "product"


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"name": None}, ["name"]),
        ({"ingredients_text": None}, ["ingredients_text"]),
        ({"serving": Serving(quantity=30, unit="g", source=OFF)}, ["serving.size_text"]),
        (
            {"nutrition": Nutrition(NutritionBasis.PER_100G, full_nutrition().nutrients)},
            ["nutrition.basis"],
        ),
    ],
)
def test_each_missing_required_item_is_reported(overrides, expected):
    result = ProductResult(ResultType.PRODUCT, complete_product(**overrides))

    assert result.missing_fields == expected
    assert result.to_dict()["completeness"] == "incomplete"


@pytest.mark.parametrize("nutrient", REQUIRED_NUTRIENTS)
def test_each_missing_required_nutrient_is_reported(nutrient):
    product = complete_product(nutrition=full_nutrition(**{nutrient: None}))

    assert compute_missing_fields(product) == [f"nutrition.nutrients.{nutrient}"]


def test_missing_optional_nutrients_do_not_affect_completeness():
    product = complete_product()

    assert product.nutrition.nutrients["trans_fat"] is None
    assert product.nutrition.nutrients["cholesterol"] is None
    assert compute_missing_fields(product) == []


def test_uncertain_value_counts_as_missing_and_is_not_usable():
    uncertain = NutrientValue(22, "g", PHOTO, Certainty.UNCERTAIN)
    product = complete_product(nutrition=full_nutrition(sugars=uncertain))

    assert not uncertain.is_usable
    assert compute_missing_fields(product) == ["nutrition.nutrients.sugars"]


def test_empty_product_reports_everything_missing_in_contract_order():
    product = Product(source=DataSource(OFF, RETRIEVED_AT), barcode="3017624010701")

    assert compute_missing_fields(product) == [
        "name",
        "ingredients_text",
        "serving.size_text",
        "nutrition.basis",
        *(f"nutrition.nutrients.{name}" for name in REQUIRED_NUTRIENTS),
    ]


# --- result types --------------------------------------------------------------------------------


def nutrition_only_product(**overrides) -> Product:
    confident = {
        name: NutrientValue(1, CANONICAL_UNITS[name], PHOTO, Certainty.CONFIDENT)
        for name in REQUIRED_NUTRIENTS
    }
    fields = dict(
        source=photo_source(),
        serving=Serving("1 cup (250 mL)", 250, "ml", PHOTO),
        nutrition=Nutrition(NutritionBasis.SERVING, confident),
    )
    fields.update(overrides)
    return Product(**fields)


def test_nutrition_only_is_judged_on_nutrition_alone():
    result = ProductResult(ResultType.NUTRITION_ONLY, nutrition_only_product())

    assert result.missing_fields == []
    body = result.to_dict()
    assert body["result"] == "nutrition_only"
    assert body["product"]["name"] is None
    assert body["product"]["ingredients_text"] is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"barcode": "3017624010701"},
        {"name": "Nutella"},
        {"brand": "Ferrero"},
        {"ingredients_text": "sugar"},
    ],
)
def test_nutrition_only_must_not_identify_a_product(overrides):
    with pytest.raises(ValueError, match="must not identify"):
        ProductResult(ResultType.NUTRITION_ONLY, nutrition_only_product(**overrides))


def test_nutrition_only_must_come_from_a_label_photo():
    product = nutrition_only_product(source=DataSource(OFF, RETRIEVED_AT))
    with pytest.raises(ValueError, match="label photo"):
        ProductResult(ResultType.NUTRITION_ONLY, product)


def test_product_result_requires_a_barcode():
    with pytest.raises(ValueError, match="barcode"):
        ProductResult(ResultType.PRODUCT, complete_product(barcode=None))


# --- errors --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "status"),
    [
        (ErrorCode.INVALID_BARCODE, 400),
        (ErrorCode.PRODUCT_NOT_FOUND, 404),
        (ErrorCode.UPSTREAM_UNAVAILABLE, 502),
        (ErrorCode.UPSTREAM_TIMEOUT, 504),
    ],
)
def test_api_error_status_and_body(code, status):
    error = ApiError(code, "something happened")

    assert error.http_status == status
    assert error.to_dict() == {"error": {"code": code.value, "message": "something happened"}}


@pytest.mark.parametrize("barcode", ["3017624010701\n", "٣٠١٧٦٢٤٠١٠٧٠١"])
def test_barcode_must_be_exactly_ascii_digits(barcode):
    # A trailing newline and non-ASCII digits both slipped past an earlier regex.
    assert not is_valid_barcode(barcode)
