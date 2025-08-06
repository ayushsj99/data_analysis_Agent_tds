def summarize_findings(findings: str, llm_call) -> str:
    prompt = f"""
    Summarize the following findings for a non-technical audience:

    {findings}
    """
    return llm_call(prompt)