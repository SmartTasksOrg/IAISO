def simulated_call(complexity: int) -> dict:
    """
    Deterministic simulation of LLM behavior.
    Tokens and tool calls scale with complexity.
    """
    tokens = complexity * 220
    tools = complexity // 2
    return {
        "tokens": tokens,
        "tools": tools,
        "output": f"Simulated response at complexity {complexity}"
    }
