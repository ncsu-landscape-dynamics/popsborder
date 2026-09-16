# © 2026 The Johns Hopkins University Applied Physics Laboratory LLC

from typing import Any, Dict, Optional, Union
import ast


def get_range_key(
    d: Dict[str, Any],
    num_plants: Union[int, float],
) -> Optional[str]:
    """Return the range key for a given numeric value based on tuple-like keys.

    The dictionary ``d`` is expected to have some keys that are string
    representations of 2-tuples, e.g. ``"(0, 10)"``, ``"(10, 20)"``.
    Each such key defines a half-open interval ``(lower, upper]``. This
    function finds the range key whose interval satisfies::

        lower < num_plants <= upper

    If no such range matches, it returns the key whose interval has the
    highest upper bound. If there are no tuple-like keys at all, it
    returns None.

    Args:
        d: Dictionary whose keys may include strings that can be parsed as
            2-tuples using ``ast.literal_eval``, e.g. ``"(0, 10)"``.
        num_plants: Numeric value used to determine which range key to select.

    Returns:
        The key in ``d`` whose associated interval contains ``num_plants``, or,
        if no interval matches, the key with the highest upper bound. Returns
        None if no suitable tuple-like keys are found.
    """
    last_key: Optional[str] = None
    max_upper: float = float("-inf")

    for key in d:
        if key.startswith("(") and key.endswith(")"):
            lower, upper = ast.literal_eval(key)

            # Track the tuple with the highest upper bound
            if upper > max_upper:
                max_upper = upper
                last_key = key

            # Normal range match
            if lower < num_plants <= upper:
                return key

    # If no match found, return the tuple with highest upper bound (or None)
    return last_key