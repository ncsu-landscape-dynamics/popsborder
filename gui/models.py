# © 2026 The Johns Hopkins University Applied Physics Laboratory LLC

from dataclasses import dataclass
import streamlit as st


@dataclass
class Scenario:
    """Container for high-level shipment scenario parameters.

    Attributes:
        title: Human-readable title for the scenario.
        seed: Random seed used for reproducible simulations.
        runs: Number of simulation runs to perform.
        unit_type: Type of shipment unit (e.g., "Boxes", "Crates", "Pallets").
        units_in_shipment: Total number of units in the shipment.
        items_per_unit: Number of items (e.g., fruit) per unit.
        packaging_type: Type of packaging (e.g., "Cardboard").
        contamination_prevalence_pct: Mean contamination prevalence (%) at the
            item or plant level.
        contamination_arrangement: Spatial contamination pattern
            (e.g., "Random", "Clustered", "Edge-loaded").
        contamination_cv: Coefficient of variation for contamination rate
            (controls heterogeneity).
        notes: Free-text notes about the scenario.
    """

    title: str = "Demo fruit shipment - port of entry"
    seed: int = 42
    runs: int = 500
    unit_type: str = "Boxes"  # Boxes / Crates / Pallets
    units_in_shipment: int = 1200
    items_per_unit: int = 100
    packaging_type: str = "Cardboard"
    contamination_prevalence_pct: float = 2.0
    contamination_arrangement: str = "Random"  # Random / Clustered / Edge-loaded
    contamination_cv: float = 1.0
    notes: str = ""


@dataclass
class Inspection:
    """Container for inspection plan parameters.

    Attributes:
        method: Sampling method (e.g., "random", "convenience", "cluster").
        sample_units: Number of primary units (e.g., boxes) to inspect.
        sample_items_per_unit: Number of items per sampled unit.
        acceptance_number: Maximum allowed number of contaminated units/items
            before rejecting the lot.
    """

    method: str = "random"  # random / convenience / cluster
    sample_units: int = 60
    sample_items_per_unit: int = 10
    acceptance_number: int = 0


def init_state():
    """Initialize Streamlit session state with default scenario and inspection.

    Sets ``st.session_state.scenario`` and ``st.session_state.inspection``
    if they are not already present.
    """
    if "scenario" not in st.session_state:
        st.session_state.scenario = Scenario()
    if "inspection" not in st.session_state:
        st.session_state.inspection = Inspection()


def set_scenario(**kwargs):
    """Update fields on the current Scenario stored in session state.

    Any keyword arguments provided must correspond to attributes of
    :class:`Scenario`; they are set in-place on
    ``st.session_state.scenario``.

    Args:
        **kwargs: Attribute name/value pairs to update on the Scenario.
    """
    scenario = st.session_state.scenario
    for key, value in kwargs.items():
        setattr(scenario, key, value)


def set_inspection(**kwargs):
    """Update fields on the current Inspection stored in session state.

    Any keyword arguments provided must correspond to attributes of
    :class:`Inspection`; they are set in-place on
    ``st.session_state.inspection``.

    Args:
        **kwargs: Attribute name/value pairs to update on the Inspection.
    """
    inspection = st.session_state.inspection
    for key, value in kwargs.items():
        setattr(inspection, key, value)
