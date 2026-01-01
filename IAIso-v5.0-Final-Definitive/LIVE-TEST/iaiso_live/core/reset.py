def atomic_reset(state: dict) -> dict:
    """
    Atomic, lossy reset: volatile state is destroyed.
    """
    state.clear()
    return {"status": "RESET_COMPLETE", "persistent_state": "NONE"}
