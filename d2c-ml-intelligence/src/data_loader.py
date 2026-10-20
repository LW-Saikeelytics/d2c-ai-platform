import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "ml_config.json"


class MLDataLoader:

    def __init__(self):

        self.config = self._load_config()

        relative_path = self.config[
            "dataset"
        ][
            "base_path"
        ]

        self.dataset_path = (
            PROJECT_ROOT / relative_path
        ).resolve()

    def _load_config(self):

        if not CONFIG_PATH.exists():
            raise FileNotFoundError(
                f"ML config not found: {CONFIG_PATH}"
            )

        with CONFIG_PATH.open(
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    def _load_csv(self, filename):

        file_path = (
            self.dataset_path
            / filename
        )

        if not file_path.exists():

            raise FileNotFoundError(
                f"Dataset file not found: {file_path}"
            )

        return pd.read_csv(
            file_path
        )

    def load_customers(self):
        return self._load_csv(
            "customers.csv"
        )

    def load_orders(self):
        return self._load_csv(
            "orders.csv"
        )

    def load_events(self):
        return self._load_csv(
            "events.csv"
        )

    def load_behavior_history(self):
        return self._load_csv(
            "behavior_history.csv"
        )

    def load_conversion_history(self):
        return self._load_csv(
            "conversion_history.csv"
        )

    def load_daily_metrics(self):
        return self._load_csv(
            "daily_metrics.csv"
        )

    def load_all(self):

        return {
            "customers":
                self.load_customers(),

            "orders":
                self.load_orders(),

            "events":
                self.load_events(),

            "behavior_history":
                self.load_behavior_history(),

            "conversion_history":
                self.load_conversion_history(),

            "daily_metrics":
                self.load_daily_metrics()
        }

    def load_product_master(self):

        relative_path = self.config[
            "reference_data"
        ][
            "product_master"
        ]

        file_path = (
            PROJECT_ROOT
            / relative_path
        ).resolve()

        if not file_path.exists():

            raise FileNotFoundError(
                f"Product master not found: "
                f"{file_path}"
            )

        with file_path.open(
            "r",
            encoding="utf-8"
        ) as file:

            records = json.load(file)

        return pd.DataFrame(
            records
        )

    def _filter_prelaunch_records(
        self,
        dataframe
    ):

        product_master = (
            self.load_product_master()[
                [
                    "product_id",
                    "launch_day"
                ]
            ]
        )

        filtered = (
            dataframe.merge(
                product_master,
                on="product_id",
                how="left",
                validate="many_to_one"
            )
        )

        missing_launch = (
            filtered[
                "launch_day"
            ]
            .isna()
        )

        if missing_launch.any():

            unknown_products = (
                filtered.loc[
                    missing_launch,
                    "product_id"
                ]
                .dropna()
                .unique()
                .tolist()
            )

            raise ValueError(
                "Missing launch metadata for "
                f"products: {unknown_products}"
            )

        filtered = (
            filtered[
                filtered[
                    "simulation_day"
                ]
                >=
                filtered[
                    "launch_day"
                ]
            ]
            .drop(
                columns=[
                    "launch_day"
                ]
            )
            .reset_index(
                drop=True
            )
        )

        return filtered


    def load_ml_orders(self):

        return self._filter_prelaunch_records(
            self.load_orders()
        )


    def load_ml_behavior_history(self):

        return self._filter_prelaunch_records(
            self.load_behavior_history()
        )


    def load_ml_events(self):

        return self._filter_prelaunch_records(
            self.load_events()
        )

if __name__ == "__main__":

    print("=" * 60)
    print("PHASE 7 - ML DATA LOADER TEST")
    print("=" * 60)

    loader = MLDataLoader()

    print(
        f"\nDataset path:\n"
        f"{loader.dataset_path}"
    )

    datasets = loader.load_all()

    print("\nLoaded datasets:")

    for name, dataframe in datasets.items():

        print(
            f"{name}: "
            f"{len(dataframe):,} rows x "
            f"{len(dataframe.columns)} columns"
        )

    print(
        "\nML DATA LOADER TEST PASSED."
    )