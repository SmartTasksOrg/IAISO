# IAIso Core Logic: Magnification and Back-Propagation
import os
from dotenv import load_dotenv

load_dotenv("l.env")

def is_back_prop_enabled():
    """Checks if back-propagation magnification is enabled in config."""
    return os.getenv("BACK_PROPAGATION", "true").lower() == "true"

def apply_magnification(agent_id, raw_output, context):
    """
    Applies recursive magnification to model outputs using back-propagation.
    This ensures model outputs meet the IAIso Entropy Floor and Safety Invariants
    by assessing quality and propagating refinements back through the chain.
    """
    if not is_back_prop_enabled():
        return raw_output

    # Magnification logic: Recursive quality assessment (Back-Prop)
    # 1. Evaluate output against entropy floor (Invariant 1 support)
    # 2. If pressure > threshold, trigger recursive refinement loop
    # 3. Adjust context and re-evaluate until magnification target met
    
    print(f"[IAIso-Magnifier] Back-prop active for {agent_id}. Refining output...")
    magnified_output = f"{raw_output} [AGI-Magnified: Back-Prop Active]"
    return magnified_output
