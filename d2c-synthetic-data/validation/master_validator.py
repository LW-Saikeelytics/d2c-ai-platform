import json
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "config"
SCHEMA_DIR = ROOT_DIR / "schema"


CONFIG_FILES = [
    "company_config.json",
    "product_master.json",
    "variant_master.json",
    "city_master.json",
    "warehouse_master.json",
    "carrier_master.json",
    "customer_segments.json",
    "channels.json",
    "payment_methods.json",
    "promotions.json",
    "support_categories.json",
    "return_reasons.json",
]

SCHEMA_FILES = [
    "order_schema.json",
    "generation_rules.json",
    "validation_rules.json",
    "simulation_dataset_schemas.json",
]

def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def check_json_files():
    print("\n[1] Checking JSON files...")

    errors = []

    for filename in CONFIG_FILES:
        path = CONFIG_DIR / filename

        if not path.exists():
            errors.append(f"Missing config file: {filename}")
            continue

        try:
            load_json(path)
            print(f"  [OK] {filename}")
        except json.JSONDecodeError as error:
            errors.append(
                f"Invalid JSON in {filename}: {error}"
            )

    for filename in SCHEMA_FILES:
        path = SCHEMA_DIR / filename

        if not path.exists():
            errors.append(f"Missing schema file: {filename}")
            continue

        try:
            load_json(path)
            print(f"  [OK] {filename}")
        except json.JSONDecodeError as error:
            errors.append(
                f"Invalid JSON in {filename}: {error}"
            )

    return errors


def check_unique_ids(data, id_field, entity_name):
    errors = []

    ids = [
        item.get(id_field)
        for item in data
        if isinstance(item, dict)
    ]

    missing = [
        str(index)
        for index, item in enumerate(data)
        if id_field not in item
    ]

    duplicates = {
        value
        for value in ids
        if value is not None and ids.count(value) > 1
    }

    if missing:
        errors.append(
            f"{entity_name}: missing {id_field} at rows {missing}"
        )

    if duplicates:
        errors.append(
            f"{entity_name}: duplicate {id_field}: "
            f"{sorted(duplicates)}"
        )

    return errors


def validate_master_data(config):
    errors = []

    products = config["products"]
    variants = config["variants"]
    cities = config["cities"]
    warehouses = config["warehouses"]
    carriers = config["carriers"]

    # -----------------------------------
    # Unique IDs
    # -----------------------------------

    errors += check_unique_ids(
        products,
        "product_id",
        "Products"
    )

    errors += check_unique_ids(
        variants,
        "variant_id",
        "Variants"
    )

    errors += check_unique_ids(
        cities,
        "city_id",
        "Cities"
    )

    errors += check_unique_ids(
        warehouses,
        "warehouse_id",
        "Warehouses"
    )

    errors += check_unique_ids(
        carriers,
        "carrier_id",
        "Carriers"
    )

    # -----------------------------------
    # Build reference sets
    # -----------------------------------

    product_ids = {
        item["product_id"]
        for item in products
    }

    city_ids = {
        item["city_id"]
        for item in cities
    }

    warehouse_ids = {
        item["warehouse_id"]
        for item in warehouses
    }

    carrier_ids = {
        item["carrier_id"]
        for item in carriers
    }

    # -----------------------------------
    # Variant -> Product
    # -----------------------------------

    for variant in variants:

        product_id = variant.get("product_id")

        if product_id not in product_ids:
            errors.append(
                f"Variant {variant.get('variant_id')} "
                f"references unknown product {product_id}"
            )

    # -----------------------------------
    # Warehouse -> City
    # -----------------------------------

    for warehouse in warehouses:

        city_id = warehouse.get("city_id")

        if city_id not in city_ids:
            errors.append(
                f"Warehouse {warehouse.get('warehouse_id')} "
                f"references unknown city {city_id}"
            )

    # -----------------------------------
    # Carrier -> Region
    # -----------------------------------

    for carrier in carriers:

        service_regions = carrier.get(
            "service_regions",
            []
        )

        if not service_regions:
            errors.append(
                f"Carrier {carrier.get('carrier_id')} "
                f"has no service regions"
            )

    # -----------------------------------
    # Warehouse -> Region consistency
    # -----------------------------------

    city_lookup = {
        city["city_id"]: city
        for city in cities
    }

    for warehouse in warehouses:

        city = city_lookup.get(
            warehouse.get("city_id")
        )

        if city is None:
            continue

        warehouse_region = warehouse.get("region")
        city_region = city.get("region")

        if warehouse_region != city_region:
            errors.append(
                f"Warehouse {warehouse.get('warehouse_id')} "
                f"region mismatch: "
                f"warehouse={warehouse_region}, "
                f"city={city_region}"
            )

    return errors


def main():

    print("=" * 65)
    print("D2C SYNTHETIC DATA - FOUNDATION VALIDATOR")
    print("=" * 65)

    errors = check_json_files()

    if errors:
        print("\nVALIDATION FAILED\n")

        for error in errors:
            print(f"[ERROR] {error}")

        raise SystemExit(1)

    # -----------------------------------
    # Load configuration
    # -----------------------------------

    config = {
        "company": load_json(
            CONFIG_DIR / "company_config.json"
        ),
        "products": load_json(
            CONFIG_DIR / "product_master.json"
        ),
        "variants": load_json(
            CONFIG_DIR / "variant_master.json"
        ),
        "cities": load_json(
            CONFIG_DIR / "city_master.json"
        ),
        "warehouses": load_json(
            CONFIG_DIR / "warehouse_master.json"
        ),
        "carriers": load_json(
            CONFIG_DIR / "carrier_master.json"
        ),
        "customer_segments": load_json(
            CONFIG_DIR / "customer_segments.json"
        ),
        "channels": load_json(
            CONFIG_DIR / "channels.json"
        ),
        "payment_methods": load_json(
            CONFIG_DIR / "payment_methods.json"
        ),
        "promotions": load_json(
            CONFIG_DIR / "promotions.json"
        ),
        "support_categories": load_json(
            CONFIG_DIR / "support_categories.json"
        ),
        "return_reasons": load_json(
            CONFIG_DIR / "return_reasons.json"
        ),
    }

    print("\n[2] Checking master-data relationships...")

    errors = validate_master_data(config)

    if errors:
        print("\nMASTER DATA VALIDATION FAILED\n")

        for error in errors:
            print(f"[ERROR] {error}")

        raise SystemExit(1)

    print("  [OK] IDs are unique")
    print("  [OK] Variant -> Product references valid")
    print("  [OK] Warehouse -> City references valid")
    print("  [OK] Warehouse -> City regions consistent") 
    print("  [OK] Carrier definitions present")

    print("\n" + "=" * 65)
    print("FOUNDATION VALIDATION PASSED")
    print("=" * 65)


if __name__ == "__main__":
    main()