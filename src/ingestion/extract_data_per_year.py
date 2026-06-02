import pandas as pd
from pathlib import Path

PROJECT_FOLDER = Path(
    "D:/CompanyLaptop/Trainings/Databricks/Projects/"
    "Canadian-Political-Contributions-Analytics-Platform"
)
SOURCE_FILE = PROJECT_FOLDER / "od_cntrbtn_de_e.csv"


def extract_by_year(source: Path, output_folder: Path, chunksize: int = 200_000):
    year_state = {}
    rescue_first_chunk = True
    rescue_rows = 0

    for i, chunk in enumerate(pd.read_csv(
        source,
        chunksize=chunksize,
        encoding="latin-1",
        dtype=str
    )):
        chunk["_parsed_date"] = pd.to_datetime(
            chunk["Fiscal/Election date"],
            format="%Y-%m-%d",
            errors="coerce"
        )
        chunk["_year"] = chunk["_parsed_date"].dt.year

        # ── Rescue: rows where date could not be parsed ──────────────────
        rescue = chunk[chunk["_parsed_date"].isna()].drop(columns=["_parsed_date", "_year"])
        if not rescue.empty:
            rescue.to_csv(
                output_folder / "rescue.csv",
                mode="w" if rescue_first_chunk else "a",
                header=rescue_first_chunk,
                index=False,
                encoding="utf-8"
            )
            rescue_rows += len(rescue)
            rescue_first_chunk = False

        # ── One file per year ─────────────────────────────────────────────
        for year in chunk["_year"].dropna().unique():
            year = int(year)
            output_file = output_folder / f"od_cntrbtn_de_e_{year}.csv"
            filtered = chunk[chunk["_year"] == year].drop(columns=["_parsed_date", "_year"])

            if year not in year_state:
                year_state[year] = {"first_chunk": True, "rows": 0}

            filtered.to_csv(
                output_file,
                mode="w" if year_state[year]["first_chunk"] else "a",
                header=year_state[year]["first_chunk"],
                index=False,
                encoding="utf-8"
            )
            year_state[year]["rows"] += len(filtered)
            year_state[year]["first_chunk"] = False

        if (i + 1) % 5 == 0:
            total = sum(s["rows"] for s in year_state.values())
            print(f"  Processed {(i + 1) * chunksize:,} rows... ({total:,} matched so far)")

    # ── Summary ───────────────────────────────────────────────────────────
    print("\n=== Done ===")
    for year in sorted(year_state.keys()):
        print(f"  {year}: {year_state[year]['rows']:,} rows  →  od_cntrbtn_de_e_{year}.csv")
    print(f"  rescue: {rescue_rows:,} rows  →  rescue.csv")


if __name__ == "__main__":
    extract_by_year(
        source=SOURCE_FILE,
        output_folder=PROJECT_FOLDER
    )