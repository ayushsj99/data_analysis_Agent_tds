import pandas as pd
import duckdb


def extract_schema_from_dataframe(df: pd.DataFrame) -> str:
    return "\n".join([f"{col}: {str(dtype)}" for col, dtype in df.dtypes.items()])


def extract_schema_from_parquet(path: str) -> str:
    df = duckdb.query(f"SELECT * FROM read_parquet('{path}') LIMIT 1").to_df()
    return extract_schema_from_dataframe(df)
