# © 2026 The Johns Hopkins University Applied Physics Laboratory LLC

import os
import re
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from scipy.optimize import minimize_scalar
from scipy import stats
import pandas as pd
from collections import defaultdict
from dataclasses import dataclass, asdict
from slippage_model_utils.references import REQUIRED_FIELDS_CLARK_INPUT_GENERATION


@dataclass
class ClarkeModelInputs:
    """Container for inputs to the Clarke beta-binomial (BB) group model.

    Attributes:
        ty: Unique counts of groups testing positive.
        freq: Frequencies corresponding to each entry in ``ty``.
        b: Number of groups per consignment (e.g., boxes per inspection).
        B: Number of consignments (inspections).
        Nbar: Average items per group (e.g., plants per sampling unit).
        theta: Clustering hyperparameter for the beta distribution.
        lambda_test: Extra tuning or tracking parameter.
        R: Number of Monte Carlo / sensitivity runs.
        start_val: Optimizer start values as (log-alpha, log-beta).
        se: If True, request standard errors from the optimizer/model.
    """

    # required by the BB model
    ty: List[int]                  # unique counts of groups testing positive
    freq: List[int]                # frequency per ty
    b: int                         # groups per consignment (boxes per inspection)
    B: int                         # number of consignments (inspections)
    Nbar: int                      # items per group
    theta: float                   # clustering hyperparameter
    lambda_test: float             # extra param you track
    R: int                         # MC / sensitivity runs
    start_val: Tuple[float, float]  # optimizer start (log-alpha, log-beta)
    se: bool                       # request standard errors

    def to_kwargs(self) -> dict:
        """Return a kwargs dict suitable for calling the BB model.

        This converts the dataclass to a dictionary and removes any extra
        keys (e.g., internal-only attributes) that the BB model does not
        expect.

        Returns:
            Dictionary of keyword arguments for the model call.
        """
        d = asdict(self)
        d.pop("action_summary", None)
        return d

    @staticmethod
    def default() -> 'ClarkeModelInputs':
        """Return a ClarkeModelInputs instance with default values.

        The defaults include empty ``ty`` and ``freq``, and generic values for
        group counts, clustering, and optimizer settings.

        Returns:
            A ClarkeModelInputs instance initialized with defaults.
        """
        return ClarkeModelInputs(
            ty=[],
            freq=[],
            b=25,
            B=100,
            Nbar=200,
            theta=np.inf,
            lambda_test=1.0,
            R=1000,
            start_val=(0.0, 0.0),
            se=False,
        )


def get_inputs(df_pis_data_filtered: pd.DataFrame):
    """Compute ClarkeModelInputs grouped by quantity deciles from PIS data.

    This function:

    1. Validates required columns.
    2. Filters outliers in ``TOTAL_SAMPLING_UNITS_FOR_RISK_UNIT``,
       ``REQUIRED_NUMBER_OF_BOXES``, and ``QUANTITY`` using an IQR rule.
    3. Bins consignments into deciles by ``QUANTITY``.
    4. For each decile, computes:

       * ``b``: groups per consignment (max required boxes).
       * ``B``: mean total sampling units per risk unit (rounded).
       * ``Nbar``: average items per group (plants per sampling unit).
       * ``ty`` and ``freq``: unique counts of groups testing positive and
         their frequencies.

    The result is a mapping whose keys are decile intervals (as tuples) and
    whose values are ClarkeModelInputs instances.

    Args:
        df_pis_data_filtered: PIS DataFrame already filtered to records of
            interest; must contain the fields listed in
            ``REQUIRED_FIELDS_CLARK_INPUT_GENERATION``.

    Returns:
        Dictionary mapping quantity-decile intervals to ClarkeModelInputs
        instances.

    Raises:
        KeyError: If any required columns are missing.
    """
    print("   Determining Inputs 'b', 'B', 'Nbar', 'ty, and 'freq'")

    # ---- Required columns ----
    required_cols = REQUIRED_FIELDS_CLARK_INPUT_GENERATION
    missing = [c for c in required_cols if c not in df_pis_data_filtered.columns]
    if missing:
        raise KeyError(f"Missing required columns: {missing}")
    # Filter upper bound of outliers from IQR method
    Q1 = df_pis_data_filtered["TOTAL_SAMPLING_UNITS_FOR_RISK_UNIT"].quantile(0.25)
    Q3 = df_pis_data_filtered["TOTAL_SAMPLING_UNITS_FOR_RISK_UNIT"].quantile(0.75)
    IQR = Q3 - Q1
    upper_bound = Q3 + 1.5 * IQR
    df_pis_data_filtered = df_pis_data_filtered[
        (df_pis_data_filtered["TOTAL_SAMPLING_UNITS_FOR_RISK_UNIT"] >= 0.0) &
        (df_pis_data_filtered["TOTAL_SAMPLING_UNITS_FOR_RISK_UNIT"] <= upper_bound)]
    Q1 = df_pis_data_filtered["REQUIRED_NUMBER_OF_BOXES"].quantile(0.25)
    Q3 = df_pis_data_filtered["REQUIRED_NUMBER_OF_BOXES"].quantile(0.75)
    IQR = Q3 - Q1
    upper_bound = Q3 + 1.5 * IQR
    df_pis_data_filtered = df_pis_data_filtered[
        (df_pis_data_filtered["REQUIRED_NUMBER_OF_BOXES"] >= 0.0) &
        (df_pis_data_filtered[
             "REQUIRED_NUMBER_OF_BOXES"] <= upper_bound)]
    Q1 = df_pis_data_filtered["QUANTITY"].quantile(0.25)
    Q3 = df_pis_data_filtered["QUANTITY"].quantile(0.75)
    IQR = Q3 - Q1
    upper_bound = Q3 + 1.5 * IQR
    df_pis_data_filtered_no_outliers = df_pis_data_filtered[(df_pis_data_filtered["QUANTITY"] >= 0.0) &
                                                                (df_pis_data_filtered["QUANTITY"] <= upper_bound)]
    # Ensure numeric where needed
    df = df_pis_data_filtered_no_outliers.copy()
    df["TOTAL_SAMPLING_UNITS_FOR_RISK_UNIT"] = pd.to_numeric(
        df["TOTAL_SAMPLING_UNITS_FOR_RISK_UNIT"], errors="coerce"
    )
    df["REQUIRED_NUMBER_OF_BOXES"] = pd.to_numeric(
        df["REQUIRED_NUMBER_OF_BOXES"], errors="coerce"
    )
    df["QUANTITY"] = pd.to_numeric(df["QUANTITY"], errors="coerce")

    bins = pd.qcut(df["QUANTITY"], q=10)
    labels = [
        (float(interval.left), float(interval.right))
        for interval in bins.cat.categories
    ]
    df["sampling_unit_decile_quantity"] = pd.qcut(
        df["QUANTITY"],
        q=10,
        labels=labels
    )
    grouped_pairs_quantity = df.groupby("sampling_unit_decile_quantity", observed=True)

    num_groups = grouped_pairs_quantity.ngroups
    clarke_inputs_by_quantity = {}
    count = 1
    for q, g in grouped_pairs_quantity:
        if count == round(num_groups*0.2,0):
            print(f'   20% Complete')
        elif count == round(num_groups*0.4,0):
            print(f'   40% Complete')
        elif count == round(num_groups*0.6,0):
            print(f'   60% Complete')
        elif count == round(num_groups*0.8,0):
            print(f'   80% Complete')
        elif count == round(num_groups*1,0):
            print(f'   100% Complete')
        count+=1

        clarke_inputs = ClarkeModelInputs.default()
        g_unique = g.drop_duplicates(subset=["INSPECTION_NUMBER", "RISK_UNIT"], keep="first")
        # Get B and b for the quantile group
        B = round(g_unique['TOTAL_SAMPLING_UNITS_FOR_RISK_UNIT'].mean(), 0)
        b = round(g_unique['REQUIRED_NUMBER_OF_BOXES'].max(), 0)

        # Get Nbar for the quantile group
        result = (
            g
            .groupby(["INSPECTION_NUMBER", "RISK_UNIT"], as_index=False)
            .agg(
                total_quantity=("QUANTITY", "sum"),
                total_sampling_units=("TOTAL_SAMPLING_UNITS_FOR_RISK_UNIT", "first"),
            )
        )

        result["quantity_fraction"] = (
                result["total_quantity"] / result["total_sampling_units"]
        )

        Nbar = round(result["quantity_fraction"].mean(), 0)

        # Calulcate ty and freq
        groups_having_action = []
        for (insp_id, ru), g_sub in g.groupby(["INSPECTION_NUMBER", "RISK_UNIT"], sort=False):
            action_vals = g_sub["action"].dropna().unique()
            if len(action_vals) == 1:
                action_out = int(action_vals[0])
                if action_vals[0] == 1:
                    groups_having_action.append(float(g_sub.iloc[0]["REQUIRED_NUMBER_OF_BOXES"]))
                else:
                    groups_having_action.append(0.0)
            else:
                temp_sub = g_sub[g_sub["action"] == 1]
                groups_having_action.append(float(temp_sub.iloc[0]["REQUIRED_NUMBER_OF_BOXES"]))

        counts = (
            pd.Series(groups_having_action)
            .value_counts()
            .sort_index()
        )

        ty = counts.index.tolist()
        freq = counts.values.tolist()

        # Check that B >= b > max(ty).  If not, then enforce it
        if b < max(ty):
            b = max(ty)
        if B < b:
            B = b

        clarke_inputs.b = b
        clarke_inputs.Nbar = Nbar
        clarke_inputs.ty = ty
        clarke_inputs.freq = freq
        clarke_inputs.B = B
        clarke_inputs_by_quantity[q] = clarke_inputs
    # Return the calculated parameters
    return clarke_inputs_by_quantity


def gen_clarke_model_inputs(
    df_pis_data: pd.DataFrame
) -> dict[Any, Any]:
    """Construct ClarkeModelInputs for the Clarke/BB group model.

    This is a wrapper that logs progress and calls :func:`get_inputs` to
    build inputs for all quantity decile groups.

    The resulting dictionary maps quantity-decile intervals to
    ClarkeModelInputs instances, where each instance includes:

    * ``ty``: unique counts of groups testing positive,
    * ``freq``: frequency per ``ty``,
    * ``b``: groups per consignment (boxes per inspection),
    * ``B``: number of consignments (inspections),
    * ``Nbar``: items per group,
    * ``theta``: clustering hyperparameter,
    * ``lambda_test``: extra tuning parameter,
    * ``R``: number of Monte Carlo runs,
    * ``start_val``: optimizer start values,
    * ``se``: whether to request standard errors.

    Args:
        df_pis_data: PIS DataFrame with at least the columns:
            * ``INSPECTION_NUMBER``
            * ``RISK_UNIT``
            * ``action`` (0/1 per inspection unit/commodity line)
            * ``TOTAL_SAMPLING_UNITS_FOR_RISK_UNIT``
            * ``QUANTITY``
            * ``REQUIRED_NUMBER_OF_BOXES``.

    Returns:
        Dictionary mapping quantity-decile intervals to ClarkeModelInputs
        instances, as produced by :func:`get_inputs`.
    """
    # Function to generate b, B, and Nbar input parameters
    print(f"Determining All Clarke Model Required Inputs")
    clarke_inputs_by_quantity = get_inputs(df_pis_data)

    return clarke_inputs_by_quantity
