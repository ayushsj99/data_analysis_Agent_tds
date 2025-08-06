def generate_duckdb_sql(schema: str, user_query: str, llm_call) -> str:
    prompt = f"""
    Given the dataset structure:
    {schema}
    and user query:
    {user_query}
    generate a DuckDB SQL query that best answers it.
    """
    return llm_call(prompt)
