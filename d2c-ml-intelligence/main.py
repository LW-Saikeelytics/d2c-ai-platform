from src.data_loader import MLDataLoader


def inspect_dataset(name, dataframe):

    print("\n" + "=" * 70)
    print(name.upper())
    print("=" * 70)

    print(
        f"Rows: {len(dataframe):,}"
    )

    print(
        f"Columns: {len(dataframe.columns)}"
    )

    print("\nCOLUMN DETAILS")

    for column in dataframe.columns:

        non_null = (
            dataframe[column]
            .notna()
            .sum()
        )

        unique = (
            dataframe[column]
            .nunique(
                dropna=True
            )
        )

        print(
            f"{column:<30} "
            f"| dtype={str(dataframe[column].dtype):<10} "
            f"| non_null={non_null:<8} "
            f"| unique={unique}"
        )

    print("\nSAMPLE ROW")

    print(
        dataframe
        .head(1)
        .to_dict(
            orient="records"
        )[0]
    )


def main():

    print("=" * 70)
    print("PHASE 7 - ML SOURCE DATA INSPECTION")
    print("=" * 70)

    loader = MLDataLoader()

    datasets = loader.load_all()

    for name, dataframe in datasets.items():

        inspect_dataset(
            name,
            dataframe
        )

    print("\n" + "=" * 70)
    print("ML SOURCE DATA INSPECTION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()