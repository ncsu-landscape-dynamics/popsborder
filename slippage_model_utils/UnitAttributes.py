# © 2026 The Johns Hopkins University Applied Physics Laboratory LLC

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class RiskUnitConfig:
    """Configuration for mapping PIS fields into RiskUnit attributes.

    How to add an attribute:

    1. Add it to ``attribute_mapping``:
       * Key: canonical name (all-lowercase with underscores).
       * Value: column name in the synthetic/PIS data.
    2. Add a default value in ``defaults``.
    3. Add the canonical name to ``enabled_attributes`` (controls which
       attributes appear on RiskUnit instances).
    4. If the new attribute is boolean-like, add its canonical name to the
       ``boolean_attributes`` set inside :meth:`get_attributes_from_record`.
    """

    # Map RiskUnit attribute names to PIS CSV column names
    attribute_mapping: Dict[str, str] = field(default_factory=lambda: {
        "material_type": "PROPAGATIVE_MATERIAL_TYPE",
        "producer_group": "producer_group",
        "origin": "COUNTRY_OF_ORIGIN_NAME",
        "port": "INSPECTION_LOCATION_NAME",
        "pathway": "PATHWAY",
        "median_qty_lt200": "MEDIAN_QTY_LT200",
        "frac_small": "FRAC_SMALL",
        "frac_small_gt07": "FRAC_SMALL_GT07",
        "any_small": "ANY_SMALL",
        "importer": "IMPORTER_NAME",
    })

    # Default values if column is missing
    defaults: Dict[str, Any] = field(default_factory=lambda: {
        "material_type": None,
        "producer_group": None,
        "origin": None,
        "port": None,
        "pathway": None,
        "median_qty_lt200": False,
        "frac_small": None,
        "frac_small_gt07": False,
        "any_small": False,
        "importer": None
    })

    # Which attributes to include
    enabled_attributes: List[str] = field(default_factory=lambda: [
        "material_type",
        "producer_group",
        "origin",
        "port",
        "pathway",
        "median_qty_lt200",
        "frac_small",
        "frac_small_gt07",
        "any_small",
        "importer"
    ])

    def get_attributes_from_record(self, record) -> Dict[str, Any]:
        """Extract configured RiskUnit attributes from a PIS record.

        Attributes are pulled from ``record`` using ``attribute_mapping`` and
        ``enabled_attributes``. Missing fields fall back to values in
        ``defaults``. Certain attributes are treated as booleans and converted
        by :meth:`_to_boolean`.

        Special handling applies to ``producer_group``: if it is missing, blank,
        or set to ``"NO_GROUP_MATCH"``, the value falls back to
        ``record["PRODUCER_NAME"]`` if present.

        Args:
            record: Mapping-like object (e.g., a pandas Series or dict)
                containing PIS/RBS record fields.

        Returns:
            Dictionary mapping canonical RiskUnit attribute names to extracted
            values.
        """
        attributes = {}

        # Define which attributes should be treated as booleans
        boolean_attributes = {"median_qty_lt200",
                              "frac_small_gt07",
                              "any_small"}

        for attr_name in self.enabled_attributes:
            if attr_name in self.attribute_mapping:
                column_name = self.attribute_mapping[attr_name]
                value = record.get(
                    column_name,
                    self.defaults.get(attr_name)
                )

                if attr_name == "producer_group":
                    if value is None or str(value).strip() == "" or str(value).strip() == "NO_GROUP_MATCH":
                        value = record.get("PRODUCER_NAME", self.defaults.get(attr_name))

                # Handle boolean conversion for boolean attributes
                if attr_name in boolean_attributes and value is not None:
                    attributes[attr_name] = self._to_boolean(value, attr_name)
                else:
                    attributes[attr_name] = value
        return attributes

    def _to_boolean(self, value, attr_name: str) -> bool:
        """Convert a value into a boolean, with attribute-specific defaults.

        Recognizes common true/false string tokens (e.g., "true", "yes",
        "1"), numeric non-zero values, and bools. For unsupported types,
        falls back to the default defined in ``defaults`` for that attribute.

        Args:
            value: Raw value to convert (string, number, bool, etc.).
            attr_name: Canonical attribute name, used to look up a default.

        Returns:
            Boolean value appropriate for the given attribute.
        """
        if isinstance(value, bool):
            return value
        elif isinstance(value, str):
            return value.strip().lower() in ('true', 'yes', '1', 't', 'y')
        elif isinstance(value, (int, float)):
            return bool(value)
        else:
            return self.defaults.get(attr_name, False)
