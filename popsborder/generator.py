# Simulation of contaminated consignments
# Copyright (C) 2018-2022 Vaclav Petras and others (see below)
# © 2026 The Johns Hopkins University Applied Physics Laboratory LLC

"""
==========================================================================================
Johns Hopkins University Applied Physics Laboratory (JHU/APL) Extensions and Modifications
==========================================================================================

Contributors: Gary Lin, Joseph Agor (JHU/APL)
Modifications

New Classes Added:
SyntheticConsignmentDataGenerator:
    * Generates synthetic consignment data for testing and simulation purposes
    * Creates realistic consignment records with randomized attributes
    * Uses advanced sampling techniques including Gaussian copulas
    * Supports multiple sampling methods: naive, sequential, GMM
    * Integrates with real PIS data for training synthetic data generation

Sampling Methods Implemented:
----------------------------
- multinomial_sample(): Naive approach sampling each column independently
- sequential_multinomial_sample(): Sequential sampling preserving conditional dependencies
- gmm_sample(): Gaussian Mixture Model sampling for numeric columns

Data Generation Features:
------------------------
- Configurable consignment attributes (origins, ports, pathways, commodities)
- Propagative material and flower commodity support
- Contamination modeling with configurable probability and quantities
- Quality metrics calculation comparing original and synthetic data
- Multiple output formats (CSV, JSON) with comprehensive statistics

New Functions Created:
------------------------
- preprocess_producer_name()
    * Preprocess a single producer name according to specified rules.
- create_producer_mapping()
    * Create a mapping dictionary from producer names to groups.
- apply_producer_grouping()
    * Apply producer name preprocessing and grouping to input data.
"""

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.

# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.

# You should have received a copy of the GNU General Public License along with
# this program; if not, see https://www.gnu.org/licenses/gpl-2.0.html

"""
.. codeauthor:: Gary Lin <Gary.Lin jhuapl edu>
.. codeauthor:: Joseph Agor <Joseph.Agor jhuapl edu>
"""

import random

import numpy as np
from numpy.random import Generator
import pandas as pd
from pathlib import Path
from scipy.stats import norm, wasserstein_distance
from sklearn.mixture import GaussianMixture
import chardet
from scipy import stats
import warnings
import re
from typing import Optional, Union
from popsborder.inspections import construct_risk_units

DEFAULT_RANDOM_STATE = 42
DEFAULT_SAMPLING_METHOD = "sequential"
DEFAULT_TARGET_COLUMNS = [
    "INSPECTION_NUMBER",
    "COMMODITY_COMMON_NAME",
    "COUNTRY_OF_ORIGIN_NAME",
    "PRODUCER_NAME",
    "PROPAGATIVE_MATERIAL_TYPE",
    "QUANTITY",
    "BROKER_NAME",
    "INSPECTION_LOCATION_NAME",
    "PATHWAY",
    "SHIPPER_NAME",
    "TAXONOMY_ORDER",
    "TAXONOMY_FAMILY",
    "TAXONOMY_GENUS",
    "TAXONOMY_SPECIES",
    "action",
    "RISK_UNIT",
    "TOTAL_SAMPLING_UNITS_FOR_RISK_UNIT",
    "SAMPLING_UNITS_FOR_INSPECTION_UNIT",
    "REQUIRED_NUMBER_OF_BOXES",
    "IMPORTER_NAME",
    "GENUS_NAME",
    "COMMODITY_DISPLAY_NAME",
    "COMMODITY_HOST_TYPE",
]


### Support functions:

def preprocess_producer_name(name, suffix_string=None, prefix_string=None):
    """Preprocess a single producer name according to specified rules.

    This function mimics the R function ``basic_text_preproc`` by lowercasing,
    stripping punctuation and numeric tokens, removing common prefixes/suffixes,
    and truncating the resulting name.

    Args:
        name: Raw producer name value.
        suffix_string: Optional regex pattern of suffixes to remove. If None,
            a default suffix pattern is used.
        prefix_string: Optional regex pattern of prefixes to remove. If None,
            a default prefix pattern is used.

    Returns:
        Preprocessed and truncated producer name string (maximum 15 characters).
    """
    # Convert to string and lowercase FIRST
    text = str(name).lower() if pd.notna(name) else name

    # Handle NA/Not Selected - convert to "missing"
    if pd.isna(text) or text.strip() == "not selected":
        return "missing"  # Changed from 'NA/NOT SELECTED' to match R

    # Remove punctuation (this happens BEFORE box removal in R)
    text = re.sub(r'[^\w\s]', '', text)

    # Remove end of string starting with "box"
    # R code finds position of "box" and truncates there
    box_match = re.search(r'box', text)
    if box_match:
        box_position = box_match.start()
        if box_position > 0:
            text = text[:box_position]
        # If box_position == 0, keep the whole string (mimics R's if_else logic)

    # Remove stand-alone numeric sequences
    text = re.sub(r'\b\d+\b', '', text)

    # Replace multiple blanks with single blank AND strip leading/trailing
    # (str_squish in R does both)
    text = re.sub(r'\s+', ' ', text).strip()

    # Define default suffix pattern if not provided
    if suffix_string is None:
        # Note: R uses " sa| s a|sociedad" (space before "sa", no space before "|sociedad")
        suffix_string = r'( sa| s a|sociedad anonima| inc| llc| ltd| ltda| cv| rl| co| co ltd| corp| bv| b v| corporation| company| limited)$'

    # Define default prefix pattern if not provided
    if prefix_string is None:
        prefix_string = r'^(mr |m r )'

    # Remove suffixes and prefixes
    text = re.sub(suffix_string, '', text)
    text = re.sub(prefix_string, '', text)

    # Final cleanup after suffix/prefix removal
    text = re.sub(r'\s+', ' ', text).strip()

    # Truncate to first 15 characters
    text = text[:15]

    return text


def create_producer_mapping(producer_group_mapping_df, use_shortest_name=True):
    """Create a mapping dictionary from producer names to group labels.

    Producer names are preprocessed and then mapped into groups. Group labels
    can be either the shortest raw producer name per group or the numeric
    grouping identifier.

    Args:
        producer_group_mapping_df: DataFrame with columns ``'PRODUCER_NAME'``
            and ``'grouping'`` describing producer group membership.
        use_shortest_name: If True, use the shortest raw name per group as the
            group label; otherwise, use the numeric grouping value.

    Returns:
        Dictionary mapping preprocessed producer names to group labels.
    """
    # Create a copy to avoid modifying original
    mapping_df = producer_group_mapping_df.copy()

    # Preprocess all producer names in the mapping file
    mapping_df['producer_name_preprocessed'] = mapping_df['PRODUCER_NAME'].apply(preprocess_producer_name)

    # If using shortest name as group label
    if use_shortest_name:
        # For each group, find the shortest original name
        group_labels = (
            mapping_df.groupby('grouping')['PRODUCER_NAME']
            .apply(lambda x: min(x, key=len))
            .to_dict()
        )
        # Map each preprocessed name to its group's shortest name
        mapping_df['group_label'] = mapping_df['grouping'].map(group_labels)
    else:
        # Use the numeric grouping as-is
        mapping_df['group_label'] = mapping_df['grouping']

    # Create the mapping dictionary
    producer_to_group = mapping_df.set_index('producer_name_preprocessed')['group_label'].to_dict()

    return producer_to_group


def apply_producer_grouping(input_data, producer_group_mapping_df, use_shortest_name=True):
    """Apply producer name preprocessing and grouping to input data.

    Args:
        input_data: DataFrame with a ``'PRODUCER_NAME'`` column.
        producer_group_mapping_df: DataFrame with ``'PRODUCER_NAME'`` and
            ``'grouping'`` columns describing producer groups. If None, all
            producers will be assigned ``'NO_GROUP_MATCH'``.
        use_shortest_name: If True, use the shortest raw name per group as
            group label; if False, use the numeric grouping identifier.

    Returns:
        DataFrame with additional columns:
            * ``producer_name_preprocessed``: preprocessed producer name.
            * ``producer_group``: group label for each row (or
              ``'NO_GROUP_MATCH'`` when no mapping is found).
    """
    if input_data is None:
        return None

    # Create a copy to avoid modifying original
    data = input_data.copy()

    if 'PRODUCER_NAME' not in data.columns:
        return data

    if producer_group_mapping_df is None:
        data['producer_name_preprocessed'] = data['PRODUCER_NAME'].apply(preprocess_producer_name)
        data['producer_group'] = 'NO_GROUP_MATCH'
        return data

    # Preprocess producer names in input data
    data['producer_name_preprocessed'] = data['PRODUCER_NAME'].apply(preprocess_producer_name)

    # Create the mapping dictionary
    producer_to_group = create_producer_mapping(producer_group_mapping_df, use_shortest_name)

    # Apply the mapping, using 'NO_GROUP_MATCH' for unknown names
    data['producer_group'] = data['producer_name_preprocessed'].map(producer_to_group).fillna('NO_GROUP_MATCH')

    return data


def _log(message: str) -> None:
    """Log a message to stdout.

    Args:
        message: Text message to log.
    """
    print(message)


class SyntheticConsignmentDataGenerator:
    """Generate synthetic consignment data using advanced sampling techniques.

    This generator creates realistic consignment records with randomized
    attributes based on configurable parameters or input data files. It
    supports multiple sampling methods for preserving statistical relationships
    in the data.
    """

    def __init__(
            self,
            config: Optional[dict] = None,
            producer_group_mapping: Optional[pd.DataFrame] = None,
            input_data_file: Optional[Union[str, Path]] = None,
            rng: Optional[Generator] = None,
    ) -> None:
        """Initialize the synthetic data generator.

        Args:
            config: Optional generator configuration dictionary.
            producer_group_mapping: Optional producer grouping table as a DataFrame.
            input_data_file: Optional path to an input data file for training
                (CSV or Excel).
            rng: Optional numpy random Generator for reproducible sampling.
        """
        self.config = config or {}
        self.producer_group_mapping = producer_group_mapping
        self.input_data = self._load_input_data(input_data_file)

        if self.input_data is not None and 'RISK_UNIT' not in self.input_data.columns and "RISK_UNIT".lower() in self.input_data.columns:
            self.input_data.rename(columns={'risk_unit': 'RISK_UNIT'}, inplace=True)

        # Initialize random seed for reproducible results
        if rng is None:
            self.rng = np.random.default_rng()
        else:
            self.rng = rng
        # random.seed(DEFAULT_RANDOM_STATE)
        # np.random.seed(DEFAULT_RANDOM_STATE)

    @staticmethod
    def _load_input_data(
            input_file: Optional[Union[str, Path]]
    ) -> Optional[pd.DataFrame]:
        """Load input data file for training sampling models.

        Args:
            input_file: Path to input data file (.csv, .xlsx, .xls).

        Returns:
            DataFrame with loaded and cleaned data, or None if loading fails.
        """
        if input_file is None:
            return None

        try:
            # Normalize to Path and detect extension
            input_path = Path(input_file)
            ext = input_path.suffix.lower()

            # Load based on extension
            if ext == ".csv":
                # Detect encoding for CSV
                with input_path.open("rb") as f:
                    result = chardet.detect(f.read(100000))
                detected = result.get("encoding") or "utf-8"

                # Try detected encoding first, then common fallbacks.
                encodings_to_try: list[str] = []
                for enc in [detected, "utf-8-sig", "utf-8", "cp1252", "latin-1"]:
                    if enc and enc.lower() not in (e.lower() for e in encodings_to_try):
                        encodings_to_try.append(enc)

                last_error: Optional[UnicodeDecodeError] = None
                df: Optional[pd.DataFrame] = None
                for enc in encodings_to_try:
                    try:
                        df = pd.read_csv(input_path, encoding=enc)
                        break
                    except UnicodeDecodeError as e:
                        last_error = e
                        df = None
                if df is None and last_error is not None:
                    raise last_error

            elif ext in {".xlsx", ".xls"}:
                df = pd.read_excel(input_path)

            else:
                raise ValueError(
                    f"Unsupported file type '{ext}'. Supported types are .csv, .xlsx, .xls."
                )

            # Cleaning logic (unchanged) ...
            df = df.dropna(how="all")
            if df.empty:
                raise ValueError("Input data has no rows after removing empty records.")

            for col in df.columns:
                if np.issubdtype(df[col].dtype, np.number):
                    if df[col].dropna().empty:
                        df[col] = df[col].fillna(0)
                    else:
                        df[col] = df[col].fillna(df[col].median())
                else:
                    df[col] = df[col].fillna("Unknown")

            _log(f"Loaded {len(df)} records from {input_path} (after cleaning)")
            return df

        except Exception as e:
            _log(f"Error loading input data file '{input_path}': {e}")
            return None

    def _resolve_target_columns(self) -> list[str]:
        """Resolve target columns for synthetic generation based on input data.

        Returns:
            A list of column names to be used as targets when generating
            synthetic data. If DEFAULT_TARGET_COLUMNS are not present, falls
            back to all available columns.
        """
        available_cols = self.input_data.columns.tolist()
        target_cols = [col for col in available_cols if col in DEFAULT_TARGET_COLUMNS]
        return target_cols or available_cols

    def _generate_with_method(self, method: str, target_cols: list[str], n_consignments: int) -> pd.DataFrame:
        """Generate synthetic data using a specified sampling method.

        Args:
            method: Sampling method name, e.g., ``'naive'``, ``'sequential'``, ``'gmm'``.
            target_cols: List of target column names to generate.
            n_consignments: Number of synthetic consignments to generate.

        Returns:
            DataFrame containing the generated synthetic data.

        Raises:
            ValueError: If the sampling method is unknown.
        """
        method_dispatch = {
            "naive": lambda: self.multinomial_sample(
                self.input_data, target_cols, n_consignments, random_state=DEFAULT_RANDOM_STATE
            ),
            "sequential": lambda: self.sequential_multinomial_sample(
                self.input_data, target_cols, n_consignments, random_state=DEFAULT_RANDOM_STATE
            ),
            "gmm": lambda: self.gmm_sample(
                self.input_data, target_cols, n_consignments, random_state=DEFAULT_RANDOM_STATE
            ),
        }
        if method not in method_dispatch:
            raise ValueError(f"Unknown sampling method: {method}")
        generated = method_dispatch[method]()
        if self.producer_group_mapping is None:
            return generated.drop(
                columns=["producer_name_preprocessed", "producer_group"],
                errors="ignore",
            )
        return apply_producer_grouping(
            generated,
            self.producer_group_mapping,
            use_shortest_name=True,
        )

    @staticmethod
    def fit_best_continuous_distribution(data, distributions=None, criterion="aic"):
        """Fit several continuous distributions and select the best by a criterion.

        RuntimeWarnings from SciPy are suppressed during fitting. If no
        distribution can be selected, the function falls back to fitting a
        beta distribution.

        Args:
            data: One-dimensional numeric data to fit.
            distributions: Optional list of SciPy distributions to consider.
                If None, a default set is used.
            criterion: Selection criterion, either ``'aic'`` or ``'ks'``.

        Returns:
            Tuple ``(dist_name, params)`` where ``dist_name`` is the name of the
            best-fitting distribution and ``params`` are the fitted parameters.

        Raises:
            ValueError: If no valid data are available for fitting.
            ValueError: If an invalid criterion is provided.
            RuntimeError: If no distribution (including beta fallback) fits.
        """
        # --- Basic cleaning ---
        data = np.asarray(data, dtype=float)
        # Remove NaN / inf
        data = data[np.isfinite(data)]
        if data.size == 0:
            raise ValueError("No valid data to fit distribution.")

        # (Optional) clip extreme values to reduce numerical issues
        lo, hi = np.percentile(data, [0.1, 99.9])
        data = np.clip(data, lo, hi)

        if distributions is None:
            distributions = [
                stats.norm,
                stats.lognorm,
                stats.expon,
                stats.gamma,
                stats.beta,
            ]

        best_score = np.inf
        best_dist = None
        best_params = None

        for dist in distributions:
            try:
                # Suppress SciPy's runtime warnings inside this block
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=RuntimeWarning)
                    params = dist.fit(data)

                    if criterion == "aic":
                        # log-likelihood
                        ll = np.sum(dist.logpdf(data, *params))
                        k = len(params)
                        score = 2 * k - 2 * ll  # AIC
                    elif criterion == "ks":
                        ks_stat, _ = stats.kstest(data, dist.name, args=params)
                        score = ks_stat
                    else:
                        raise ValueError("criterion must be 'aic' or 'ks'")

                # If score is nan/inf, treat as bad fit
                if not np.isfinite(score):
                    continue

                if score < best_score:
                    best_score = score
                    best_dist = dist
                    best_params = params

            except Exception:
                # Any fitting failure: skip this distribution
                continue

        # Fallback: try beta if nothing else worked
        if best_dist is None:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=RuntimeWarning)
                try:
                    beta_params = stats.beta.fit(data)
                    return "beta", beta_params
                except Exception:
                    raise RuntimeError(
                        "No distribution could be fitted successfully, "
                        "including beta fallback."
                    )

        return best_dist.name, best_params

    def sample_mixed_with_inspection(self,
                                     df,
                                     columns,
                                     n_consignments,
                                     num_inspection_units,
                                     inspection_col="INSPECTION_NUMBER",
                                     random_state=None):
        """Sample rows while controlling inspection IDs and per-inspection counts.

        This method:
        - Creates ``n_consignments`` synthetic inspection IDs.
        - Repeats each inspection ID according to ``num_inspection_units``.
        - Samples numeric columns from fitted continuous distributions.
        - Samples non-numeric columns from their empirical PMF.

        Args:
            df: Source DataFrame used to estimate distributions.
            columns: Columns to sample.
            n_consignments: Number of distinct inspection IDs to create.
            num_inspection_units: Array-like counts of units per inspection.
            inspection_col: Name of the inspection ID column.
            random_state: Seed for random number generation.

        Returns:
            DataFrame with sampled rows and inspection IDs.
        """
        rng = np.random.default_rng(random_state)

        num_inspection_units = np.asarray(num_inspection_units, dtype=int)
        assert len(num_inspection_units) == n_consignments, \
            "num_inspection_units must have length n_consignments"

        total_rows = int(num_inspection_units.sum())

        sampled = {}

        # 1. Build INSPECTION_NUMBER values deterministically from num_inspection_units
        #    Example: "INS_0", "INS_1", ..., but you can change this pattern.
        inspection_ids = [f"INS_{i}" for i in range(n_consignments)]
        inspection_col_values = np.repeat(inspection_ids, num_inspection_units)

        if len(inspection_col_values) != total_rows:
            raise ValueError("Sum of num_inspection_units must equal total number of rows.")

        sampled[inspection_col] = inspection_col_values

        # 2. Sample other columns according to type
        for col in columns:
            if col == inspection_col:
                continue  # already handled

            s = df[col]

            if pd.api.types.is_numeric_dtype(s):
                # Numeric column: fit and sample continuous distribution
                numeric_data = s.astype(float).to_numpy()
                numeric_data = numeric_data[~np.isnan(numeric_data)]

                if numeric_data.size == 0:
                    sampled[col] = np.full(total_rows, np.nan)
                    continue

                dist_name, params = self.fit_best_continuous_distribution(numeric_data)
                dist = getattr(stats, dist_name)
                sampled[col] = dist.rvs(*params, size=total_rows, random_state=rng)

            else:
                # Non-numeric: empirical PMF
                values, counts = np.unique(s.to_numpy(), return_counts=True)
                probs = counts / counts.sum()
                sampled[col] = rng.choice(values, size=total_rows, p=probs)

        # 3. Return as DataFrame
        sampled_df = pd.DataFrame(sampled)

        return sampled_df

    @staticmethod
    def resolve_producer_names(
            df: pd.DataFrame,
            input_col: str = "PRODUCER_NAME",
            output_col: str = "PRODUCER_NAME_RESOLVED",
            alias_map: Optional[dict] = None,
    ) -> pd.DataFrame:
        """Perform a simple producer entity resolution.

        The function:
        - Normalizes text (strips, removes parentheses, collapses spaces).
        - Optionally applies an alias map whose keys are normalized lowercase
          strings and whose values are canonical producer names.
        - Adds a new column with resolved names.

        Args:
            df: DataFrame containing producer names.
            input_col: Name of the input column with raw producer names.
            output_col: Name of the output column to store resolved names.
            alias_map: Optional mapping from normalized lowercase names to
                canonical names.

        Returns:
            A copy of the DataFrame with the resolved-name column added.
        """

        def _normalize(name: Union[str, float]):
            if pd.isna(name):
                return name
            name = str(name)

            # Strip leading/trailing spaces
            name = name.strip()

            # Remove anything in parentheses, e.g. "Producer 1 (boxes 1-2)" -> "Producer 1"
            name = re.sub(r"\s*\(.*?\)\s*", " ", name)

            # Collapse multiple spaces
            name = re.sub(r"\s+", " ", name)

            return name

        # Step 1: basic normalization
        normalized = df[input_col].map(_normalize)

        # Step 2: optional alias mapping (for handling typos / variants)
        # alias_map keys should be *normalized & lowercased* forms.
        if alias_map is not None:
            def _apply_alias(n):
                if pd.isna(n):
                    return n
                key = str(n).lower()
                return alias_map.get(key, n)

            resolved = normalized.map(_apply_alias)
        else:
            resolved = normalized

        df[output_col] = resolved
        return df

    @staticmethod
    def identify_num_inspection_units(df, n_consignments=1):
        """Randomly sample number of inspection units per consignment from data.

        The number of inspection units per consignment is sampled uniformly
        from the observed minimum and maximum inspection size in the data.

        Args:
            df: DataFrame containing ``INSPECTION_NUMBER`` for grouping.
            n_consignments: Number of synthetic consignments to generate.

        Returns:
            Array of integer inspection-unit counts (length ``n_consignments``).
        """
        # First sample the number of inspection units per consignment uniformly based on data
        counts = df["INSPECTION_NUMBER"].value_counts()
        min_count = counts.min()
        max_count = counts.max()

        num_inspection_units = np.random.uniform(low=min_count,
                                                 high=max_count,
                                                 size=n_consignments)
        return np.round(num_inspection_units).astype(int)

    def identify_num_inspection_units_conditional(self, df, n_consignments=1,
                                                  cols=None,
                                                  producer_alias_map: Optional[dict] = None):
        """Build nested dictionaries for conditional inspection-unit sampling.

        This method constructs a nested dictionary keyed by location and
        (country, propagative material, producer) combinations to support
        conditional sampling of inspection units. The logic depends on whether
        the inspection location is "Miami PIS" or not.

        For:
            - "Miami PIS": keys are
              (COUNTRY_OF_ORIGIN_NAME, PROPAGATIVE_MATERIAL_TYPE, PRODUCER_NAME_RESOLVED)
            - other locations: keys are
              (INSPECTION_LOCATION_NAME, COUNTRY_OF_ORIGIN_NAME, PROPAGATIVE_MATERIAL_TYPE)

        Args:
            df: Source DataFrame containing inspection data.
            n_consignments: Number of consignments (unused here but retained
                for interface compatibility).
            cols: Optional list of columns used for grouping (not required).
            producer_alias_map: Optional mapping from normalized producer names
                to canonical names.

        Returns:
            A dictionary of the form:
                {
                  "Miami PIS": { key_tuple: subset_df, ... },
                  "Non-Miami PIS": { key_tuple: subset_df, ... },
                }
        """
        if cols is None:
            cols = [
                "INSPECTION_LOCATION_NAME",
                "COUNTRY_OF_ORIGIN_NAME",
                "PROPAGATIVE_MATERIAL_TYPE",
                "PRODUCER_NAME",
            ]

        df = self.resolve_producer_names(
            df,
            input_col="PRODUCER_NAME",
            output_col="PRODUCER_NAME_RESOLVED",
            alias_map=producer_alias_map,
        )

        # Top-level dict for the two cases
        result = {
            "Miami PIS": {},  # Case1
            "Non-Miami PIS": {}  # Case2
        }

        # Masks for the two cases
        miami_mask = df["INSPECTION_LOCATION_NAME"] == "Miami PIS"
        miami_df = df.loc[miami_mask]
        other_df = df.loc[~miami_mask]

        # ----- Case1: INSPECTION_LOCATION_NAME == "Miami PIS" -----
        # Keys: 3-tuples (COUNTRY_OF_ORIGIN_NAME, PROPAGATIVE_MATERIAL_TYPE, PRODUCER_NAME)
        case1_group_cols = [
            "COUNTRY_OF_ORIGIN_NAME",
            "PROPAGATIVE_MATERIAL_TYPE",
            "PRODUCER_NAME_RESOLVED",
        ]

        if not miami_df.empty:
            for key_tuple, sub_df in miami_df.groupby(case1_group_cols, dropna=False):
                # key_tuple is a 3-tuple because we grouped on 3 columns
                result["Miami PIS"][key_tuple] = sub_df

        # ----- Case2: INSPECTION_LOCATION_NAME != "Miami PIS" -----
        # Keys: 3-tuples (INSPECTION_LOCATION_NAME, COUNTRY_OF_ORIGIN_NAME, PROPAGATIVE_MATERIAL_TYPE)
        case2_group_cols = [
            "INSPECTION_LOCATION_NAME",
            "COUNTRY_OF_ORIGIN_NAME",
            "PROPAGATIVE_MATERIAL_TYPE",
        ]

        if not other_df.empty:
            for key_tuple, sub_df in other_df.groupby(case2_group_cols, dropna=False):
                result["Non-Miami PIS"][key_tuple] = sub_df

        # 3) Compute and store sampling probabilities based on row counts
        self._case_sampling_info = {}
        for case_name, case_dict in result.items():
            if not case_dict:
                continue

            keys = list(case_dict.keys())
            weights = np.array([len(case_dict[k]) for k in keys], dtype=float)
            probs = weights / weights.sum()

            self._case_sampling_info[case_name] = {
                "keys": keys,
                "probs": probs,
            }

        return result

    def sample_random_key(self, case: str = "Miami PIS"):
        """Sample a random key from a given case using precomputed probabilities.

        This method uses sampling information computed by
        :meth:`identify_num_inspection_units_conditional` to select a key
        (tuple of grouping values) for a specified case.

        Args:
            case: Case label, such as ``"Miami PIS"`` or ``"Non-Miami PIS"``.

        Returns:
            A key tuple representing a grouping combination, or None if no
            sampling information is available.
        """
        info = getattr(self, "_case_sampling_info", None)
        if not info or case not in info:
            return None

        keys = info[case]["keys"]
        probs = info[case]["probs"]

        # Make sure we have something to sample from
        if not keys:
            return None

        # Sample an index, not the tuples directly
        idx = self.rng.choice(len(keys), p=probs)
        return keys[idx]

    @staticmethod
    def compute_rowcount_pmf_for_location(
            df: pd.DataFrame,
            location_name: str,
            total_units_col: str = 'SAMPLING_UNITS_FOR_INSPECTION_UNIT',
            loc_col: str = "INSPECTION_LOCATION_NAME",
            inspection_col: str = "INSPECTION_NUMBER",
            risk_unit_col: str = "RISK_UNIT",
            count_mode: str = "rows_per_inspection",
    ) -> pd.Series:
        """Compute an empirical PMF over row counts for a given location.

        For a given inspection location, this function:
        1. Filters the DataFrame to that location.
        2. Drops rows where ``total_units_col`` is non-positive or invalid.
        3. Computes counts based on ``count_mode``.
        4. Builds an empirical PMF over these counts.

        Args:
            df: Source DataFrame.
            location_name: Name of the inspection location.
            total_units_col: Column holding total sampling units.
            loc_col: Column name for inspection location.
            inspection_col: Column name for inspection number.
            risk_unit_col: Column name for risk unit.
            count_mode: One of
                ``"rows_per_inspection"``,
                ``"risk_units_per_inspection"``,
                ``"rows_per_risk_unit"``.

        Returns:
            A Pandas Series representing the PMF, where the index is the row
            count and the values are probabilities.

        Raises:
            ValueError: If no rows, invalid counts, or unknown count_mode.
        """
        # 1) subset by location
        df_loc = df[df[loc_col] == location_name].copy()

        if df_loc.empty:
            raise ValueError(f"No rows found for location '{location_name}'.")

        # 2) filter out rows with SAMPLING_UNITS <= 0 or non-numeric/blank
        #    This handles 0, blank, None, NA by coercing to numeric.
        total_units_numeric = pd.to_numeric(df_loc[total_units_col], errors="coerce")
        valid_mask = total_units_numeric > 0
        df_valid = df_loc[valid_mask]

        if df_valid.empty:
            raise ValueError(
                f"No valid rows (SAMPLING_UNITS > 0) for location '{location_name}'."
            )

        # 3) compute counts based on mode
        if count_mode == "rows_per_inspection":
            counts = df_valid.groupby(inspection_col).size()
        elif count_mode == "risk_units_per_inspection":
            if risk_unit_col not in df_valid.columns:
                raise ValueError(
                    f"Column '{risk_unit_col}' not found for risk unit counting."
                )
            df_ru = df_valid[df_valid[risk_unit_col].notna() & (df_valid[risk_unit_col] != "")]
            counts = df_ru.groupby(inspection_col)[risk_unit_col].nunique()
        elif count_mode == "rows_per_risk_unit":
            if risk_unit_col not in df_valid.columns:
                raise ValueError(
                    f"Column '{risk_unit_col}' not found for risk unit counting."
                )
            df_ru = df_valid[df_valid[risk_unit_col].notna() & (df_valid[risk_unit_col] != "")]
            counts = df_ru.groupby([inspection_col, risk_unit_col]).size()
        else:
            raise ValueError(
                "count_mode must be one of: "
                "'rows_per_inspection', 'risk_units_per_inspection', 'rows_per_risk_unit'."
            )

        if counts.empty:
            raise ValueError(
                f"No counts available for location '{location_name}' with count_mode='{count_mode}'."
            )

        # 4) empirical PMF over these counts
        #    value_counts gives how often each count occurs
        freq_by_count = counts.value_counts().sort_index()  # index = count
        pmf = freq_by_count / freq_by_count.sum()

        return pmf

    def sample_num_rows_from_location_pmf(
            self,
            df: pd.DataFrame,
            location_name: str,
            total_units_col: str = 'SAMPLING_UNITS_FOR_INSPECTION_UNIT',
            loc_col: str = "INSPECTION_LOCATION_NAME",
            inspection_col: str = "INSPECTION_NUMBER",
            risk_unit_col: str = "RISK_UNIT",
            count_mode: str = "rows_per_inspection",
    ) -> tuple[int, pd.Series]:
        """Sample a number of rows from an empirical PMF for a given location.

        This is a convenience wrapper that:
        1. Computes the PMF via :func:`compute_rowcount_pmf_for_location`.
        2. Samples a row-count according to that PMF.

        Args:
            df: Source DataFrame.
            location_name: Inspection location name to filter data.
            total_units_col: Column name for sampling units.
            loc_col: Column name for inspection location.
            inspection_col: Column name for inspection number.
            risk_unit_col: Column name for risk unit.
            count_mode: Count mode passed to
                :func:`compute_rowcount_pmf_for_location`.

        Returns:
            A tuple ``(sampled_count, pmf)`` where:
            * ``sampled_count`` is the sampled number of rows (int).
            * ``pmf`` is the PMF used for sampling (Series).
        """
        pmf = self.compute_rowcount_pmf_for_location(
            df=df,
            location_name=location_name,
            total_units_col=total_units_col,
            loc_col=loc_col,
            inspection_col=inspection_col,
            risk_unit_col=risk_unit_col,
            count_mode=count_mode,
        )

        counts = pmf.index.to_numpy()
        probs = pmf.to_numpy()

        sampled_count = int(self.rng.choice(counts, p=probs))
        return sampled_count

    @staticmethod
    def best_fit_discrete_distribution(data, candidate_dists=None):
        """Fit multiple discrete distributions and return the best by AIC.

        This function tries several SciPy discrete distributions and returns
        the best-fitting one based on the Akaike Information Criterion (AIC).

        Args:
            data: One-dimensional integer data.
            candidate_dists: Optional mapping from distribution name to SciPy
                distribution object. If None, a default set is used.

        Returns:
            Tuple ``(best_dist_name, best_dist_obj, best_params, best_aic)``.
            If no candidate distribution fits, returns
            ``(None, None, None, np.inf)``.
        """
        if candidate_dists is None:
            candidate_dists = {
                "poisson": stats.poisson,
                "nbinom": stats.nbinom,
                "geom": stats.geom,
            }

        data = np.asarray(data, dtype=int)

        best_dist = None
        best_name = None
        best_params = None
        best_aic = np.inf

        for name, dist in candidate_dists.items():
            try:
                # Fit distribution parameters by MLE
                params = dist.fit(data)

                # log-likelihood
                loglik = np.sum(dist.logpmf(data, *params))

                # number of parameters
                k = len(params)

                # AIC
                aic = 2 * k - 2 * loglik

                if np.isfinite(aic) and aic < best_aic:
                    best_aic = aic
                    best_dist = dist
                    best_name = name
                    best_params = params

            except Exception:
                # Some distributions may fail to fit; skip them
                continue

        return best_name, best_dist, best_params, best_aic

    def sample_positive_from_discrete_best_fit(
            self,
            df: pd.DataFrame,
            inspection_location_name: str,
            country_of_origin_name: str,
            propagative_material_type: str,
            total_units_col: str = 'SAMPLING_UNITS_FOR_INSPECTION_UNIT',
            loc_col: str = "INSPECTION_LOCATION_NAME",
            country_col: str = "COUNTRY_OF_ORIGIN_NAME",
            material_col: str = "PROPAGATIVE_MATERIAL_TYPE",
    ):
        """Sample a positive integer from data subset via discrete best-fit.

        This function:
        1. Subsets the DataFrame to a given (location, country, material).
        2. Extracts strictly positive integers from ``total_units_col``.
        3. (Currently) falls back to sampling from the empirical PMF over the
           observed support (best-fit discrete distributions are not applied).

        Args:
            df: Source DataFrame.
            inspection_location_name: Inspection location name.
            country_of_origin_name: Country of origin name.
            propagative_material_type: Propagative material type.
            total_units_col: Column name for total units (numeric).
            loc_col: Column name for location.
            country_col: Column name for country of origin.
            material_col: Column name for material type.

        Returns:
            A tuple ``(sample, info)`` where:
            * ``sample`` is a sampled positive integer.
            * ``info`` is a dictionary with diagnostic information.
        """
        # ---- 1) Filter df ----
        mask = (
                (df[loc_col] == inspection_location_name) &
                (df[country_col] == country_of_origin_name) &
                (df[material_col] == propagative_material_type)
        )
        df_sub = df.loc[mask]

        if df_sub.empty:
            raise ValueError(
                "No rows found for "
                f"{loc_col}={inspection_location_name!r}, "
                f"{country_col}={country_of_origin_name!r}, "
                f"{material_col}={propagative_material_type!r}."
            )

        # ---- 2) Coerce to integer, keep strictly positive ----
        vals = pd.to_numeric(df_sub[total_units_col], errors="coerce")
        vals = vals[vals > 0].dropna().astype(int)

        if vals.empty:
            return 1, {"dist_name": "one_due_to_no_data", "params": None}

        # empirical PMF over observed support
        counts = vals.value_counts(normalize=True).sort_index()
        support = counts.index.to_numpy()
        probs = counts.to_numpy()

        sample = int(self.rng.choice(support, p=probs))
        info = {
            "dist_name": "empirical_pmf_fallback",
            "params": None,
            "aic": None,
            "n_obs": len(vals),
        }
        return sample, info

    def multinomial_sample(self, df, columns, n_consignments=1, random_state=None):
        """Sample each column independently (naive multinomial sampling).

        This method:
        - Identifies the number of inspection units per consignment.
        - Uses :meth:`sample_mixed_with_inspection` to generate synthetic rows
          with per-inspection grouping.

        Args:
            df: Source DataFrame.
            columns: List of column names to sample.
            n_consignments: Number of synthetic consignments to generate.
            random_state: Seed for NumPy random number generation.

        Returns:
            DataFrame containing multinomial-sampled synthetic data.
        """
        np.random.seed(random_state)

        num_inspection_units = self.identify_num_inspection_units(df=df, n_consignments=n_consignments)

        sampled_df = self.sample_mixed_with_inspection(
            df=df,
            columns=columns,
            n_consignments=n_consignments,
            num_inspection_units=num_inspection_units,
            inspection_col="INSPECTION_NUMBER",
            random_state=random_state,
        )

        return sampled_df

    def sequential_multinomial_sample(self,
                                      df,
                                      columns,
                                      n_consignments=1,
                                      random_state=None
                                      ):
        """Generate synthetic rows using sequential conditional multinomial sampling.

        The sampler builds each synthetic inspection in layers:

        1. Sample an inspection location.
        2. Sample how many risk units should appear in that inspection.
        3. For each risk unit, choose a conditional base subset
           (Miami vs Non-Miami logic), optionally pin a specific RISK_UNIT
           value, then sample how many rows that risk unit contributes.
        4. For each row, sample remaining columns sequentially, conditioning
           each next column on prior sampled values by filtering the working
           subset.

        Args:
            df: Source data used to estimate empirical distributions.
            columns: Requested output column names. ``INSPECTION_NUMBER`` is
                used internally and only retained in the output if explicitly
                requested.
            n_consignments: Number of synthetic inspections to generate.
            random_state: Optional random seed for NumPy random sampling.

        Returns:
            Synthetic dataset with requested columns, preserving some
            conditional structure from the observed data.
        """
        risk_unit_col = "RISK_UNIT"

        # Build cases + probabilities
        num_inspection_units_conditional = self.identify_num_inspection_units_conditional(df=df)

        # Make sure INSPECTION_NUMBER is represented
        inspection_col = "INSPECTION_NUMBER"
        include_inspection_col_in_output = inspection_col in columns
        if inspection_col not in columns:
            columns = [inspection_col] + list(columns)

        risk_unit_number_col = "RISK_UNIT_NUMBER"
        include_risk_unit_number_in_output = risk_unit_number_col in columns
        if include_risk_unit_number_in_output and risk_unit_number_col not in columns:
            columns = [risk_unit_number_col] + list(columns)

        # Empirical location sampler P(location) from observed frequencies.
        def sample_location():
            values, counts = np.unique(df['INSPECTION_LOCATION_NAME'], return_counts=True)
            probs = counts / counts.sum()
            return self.rng.choice(values, p=probs)

        # Sample a conditional key for a case, optionally constrained to one location.
        def pick_key(case, fixed_location=None):
            key = self.sample_random_key(case=case)
            if fixed_location is None:
                return key
            while key[0] != fixed_location:
                key = self.sample_random_key(case=case)
            return key

        # Build the base sample + subset that subsequent column sampling conditions on.
        def build_base(chosen_location, fixed_location):
            base_sample = {'INSPECTION_LOCATION_NAME': chosen_location}
            is_miami = chosen_location == 'Miami PIS'
            case_label = "Miami PIS" if is_miami else "Non-Miami PIS"

            cols_to_remove = [
                'INSPECTION_LOCATION_NAME',
                'COUNTRY_OF_ORIGIN_NAME',
                'PROPAGATIVE_MATERIAL_TYPE',
                'SAMPLING_UNITS_FOR_INSPECTION_UNIT',
            ]
            if is_miami:
                cols_to_remove.append('PRODUCER_NAME')

            key = pick_key(case=case_label, fixed_location=None if is_miami else fixed_location)
            if not is_miami and fixed_location is None:
                fixed_location = key[0]

            base_sample['INSPECTION_LOCATION_NAME'] = fixed_location if not is_miami else chosen_location
            base_sample['COUNTRY_OF_ORIGIN_NAME'] = key[0 if is_miami else 1]
            base_sample['PROPAGATIVE_MATERIAL_TYPE'] = key[1 if is_miami else 2]
            if is_miami:
                base_sample['PRODUCER_NAME'] = key[2]

            base_subset = num_inspection_units_conditional[case_label][key]
            return base_sample, base_subset, cols_to_remove, fixed_location

        # Create synthetic inspection IDs: INS_0, INS_1, ...
        inspection_ids = [f"INS_{i}" for i in range(n_consignments)]

        samples = []
        for ins_id in inspection_ids:
            # 1) Sample top-level inspection location.
            chosen_location = sample_location()

            # 2) Sample number of risk units in this inspection from location-specific PMF.
            num_risk_units = self.sample_num_rows_from_location_pmf(
                df,
                location_name=chosen_location,
                total_units_col="SAMPLING_UNITS_FOR_INSPECTION_UNIT",
                count_mode="risk_units_per_inspection",
                risk_unit_col="RISK_UNIT",
            )

            fixed_pis_location = None

            # 3) Generate each risk unit under this inspection.
            for risk_unit_number in range(num_risk_units):
                base_sample, base_subset, cols_to_remove, fixed_pis_location = build_base(
                    chosen_location=chosen_location,
                    fixed_location=fixed_pis_location,
                )

                # Assign a synthetic risk unit number per inspection
                if include_risk_unit_number_in_output:
                    base_sample[risk_unit_number_col] = f"RU_{ins_id}_{risk_unit_number}"
                    cols_to_remove = cols_to_remove + [risk_unit_number_col]

                # Set a consistent risk unit value for this risk unit
                if risk_unit_col in df.columns:
                    cols_to_remove = cols_to_remove + [risk_unit_col]
                    ru_values = base_subset[risk_unit_col].dropna().unique()
                    if len(ru_values) > 0:
                        risk_unit_value = self.rng.choice(ru_values)
                        base_sample[risk_unit_col] = risk_unit_value
                        base_subset = base_subset[base_subset[risk_unit_col] == risk_unit_value]

                # Sample number of rows for this risk unit
                num_rows_for_risk_unit = self.sample_num_rows_from_location_pmf(
                    df,
                    location_name=chosen_location,
                    total_units_col="SAMPLING_UNITS_FOR_INSPECTION_UNIT",
                    count_mode="rows_per_risk_unit",
                    risk_unit_col="RISK_UNIT",
                )

                # 4) Generate each row belonging to this risk unit.
                for row_id in range(num_rows_for_risk_unit):
                    subset = base_subset
                    sample = dict(base_sample)

                    # Get a random number of sampling units based on what has already been populated by the sample
                    # (i.e., the PIS station, Origin, and PM Type)
                    df_for_sampling = base_subset if not base_subset.empty else df
                    num_sample_units, info = self.sample_positive_from_discrete_best_fit(
                        df=df_for_sampling,
                        inspection_location_name=sample['INSPECTION_LOCATION_NAME'],
                        country_of_origin_name=sample['COUNTRY_OF_ORIGIN_NAME'],
                        propagative_material_type=sample['PROPAGATIVE_MATERIAL_TYPE'],
                        total_units_col="SAMPLING_UNITS_FOR_INSPECTION_UNIT",
                    )

                    sample['SAMPLING_UNITS_FOR_INSPECTION_UNIT'] = num_sample_units

                    for col in columns:
                        # Do not multinomial-sample INSPECTION_NUMBER; we set it explicitly
                        if col == inspection_col or col in cols_to_remove:
                            continue

                        values, counts = np.unique(subset[col], return_counts=True)
                        probs = counts / counts.sum()
                        sampled_value = self.rng.choice(values, p=probs)
                        sample[col] = sampled_value

                        # Condition on this choice for subsequent columns
                        subset = subset[subset[col] == sampled_value]

                        if subset.empty:
                            # If no rows left, sample remaining columns from original df marginals
                            for rem_col in columns:
                                if rem_col in sample or rem_col == inspection_col:
                                    continue
                                values, counts = np.unique(df[rem_col], return_counts=True)
                                probs = counts / counts.sum()
                                sample[rem_col] = self.rng.choice(values, p=probs)
                            break

                    # Now set inspection and row ID for this row
                    sample[inspection_col] = ins_id
                    sample['Row_ID'] = f"{ins_id}_{row_id}"

                    samples.append(sample)

        sampled_df = pd.DataFrame(samples)

        return sampled_df

    def gmm_sample(self, df, columns, n_consignments=1, random_state=None, n_components=3):
        """Sample synthetic data using GMM for numerics and a Gaussian copula for categoricals.

        This method:
        - Determines the number of inspection units via
          :meth:`identify_num_inspection_units`.
        - Samples categorical columns using a Gaussian copula.
        - Samples numeric columns using a Gaussian Mixture Model (GMM).
        - Ensures inspection IDs are grouped according to the sampled
          inspection-unit counts.

        Args:
            df: Source DataFrame to fit underlying distributions.
            columns: Column names to sample.
            n_consignments: Number of synthetic consignments to generate.
            random_state: Optional random seed.
            n_components: Number of GMM components for numeric columns.

        Returns:
            DataFrame of synthetic samples with requested columns.
        """
        rng = np.random.default_rng(random_state)
        inspection_col = "INSPECTION_NUMBER"

        # Ensure INSPECTION_NUMBER is part of columns
        if inspection_col not in columns:
            columns = [inspection_col] + list(columns)

        # ----- 1. Figure out how many rows to generate per inspection -----
        num_inspection_units = self.identify_num_inspection_units(
            df=df,
            n_consignments=n_consignments,
        )
        num_inspection_units = np.asarray(num_inspection_units, dtype=int)

        if len(num_inspection_units) != n_consignments:
            raise ValueError(
                "identify_num_inspection_units must return an array of length n_consignments"
            )

        total_rows = int(num_inspection_units.sum())

        # Create synthetic inspection IDs; change format if you want real IDs
        inspection_ids = np.array([f"INS_{i}" for i in range(n_consignments)])
        inspection_values = np.repeat(inspection_ids, num_inspection_units)
        if len(inspection_values) != total_rows:
            raise ValueError("Sum of num_inspection_units must equal total_rows.")

        # ----- 2. Split columns into numeric vs categorical -----
        numeric_cols = [
            c for c in columns
            if c != inspection_col and np.issubdtype(df[c].dtype, np.number)
        ]
        cat_cols = [c for c in columns if c not in numeric_cols]

        # We will *not* sample INSPECTION_NUMBER via copula; we assign it manually
        cat_cols_no_ins = [c for c in cat_cols if c != inspection_col]

        # ----- 3. Sample categorical columns via Gaussian copula sampler -----
        if cat_cols_no_ins:
            # gaussian_copula_sample returns a DataFrame with these columns
            sampled_cat = self.gaussian_copula_sample(
                df=df,
                columns=cat_cols_no_ins,
                n_samples=total_rows,
                random_state=random_state,
            )
        else:
            sampled_cat = pd.DataFrame(index=range(total_rows))

        # Add INSPECTION_NUMBER column explicitly
        sampled_cat[inspection_col] = inspection_values

        # ----- 4. Fit and sample GMM for numeric columns -----
        if numeric_cols:
            gmm = GaussianMixture(
                n_components=n_components,
                random_state=random_state
            )
            gmm.fit(df[numeric_cols])

            sampled_numeric, _ = gmm.sample(total_rows)
            sampled_numeric = pd.DataFrame(sampled_numeric, columns=numeric_cols)

            # Optional: round and clip like original
            for col in numeric_cols:
                # If your numeric cols are not all integer-like, you can relax this
                sampled_numeric[col] = np.round(sampled_numeric[col]).astype(int)
                sampled_numeric[col] = sampled_numeric[col].clip(
                    df[col].min(),
                    df[col].max()
                )
        else:
            sampled_numeric = pd.DataFrame(index=range(total_rows))

        # ----- 5. Combine categorical + numeric samples -----
        if not sampled_cat.empty and not sampled_numeric.empty:
            sampled = pd.concat(
                [sampled_cat.reset_index(drop=True),
                 sampled_numeric.reset_index(drop=True)],
                axis=1,
            )
        elif not sampled_cat.empty:
            sampled = sampled_cat
        else:
            sampled = sampled_numeric

        # Enforce requested column order
        sampled = sampled[[c for c in columns if c in sampled.columns]]

        return sampled

    @staticmethod
    def _make_psd(s):
        """Ensure a symmetric matrix is positive semi-definite (PSD).

        Very small negative eigenvalues are clipped to a small positive value.

        Args:
            s: Symmetric matrix.

        Returns:
            A PSD-adjusted matrix.
        """
        w, V = np.linalg.eigh(s)
        w = np.maximum(w, 1e-8)
        return (V * w) @ V.T

    @staticmethod
    def _rank_to_z(mat):
        """Transform columns to latent normals via empirical CDF.

        Each column is ranked and mapped through the normal quantile function,
        resulting in an approximate Gaussian representation of the data.

        Args:
            mat: 2D numpy array with shape (n_samples, n_features).

        Returns:
            2D numpy array of the same shape with latent normal values.
        """
        eps = 1e-6
        n, m = mat.shape
        Z = np.empty_like(mat, dtype=float)
        for j in range(m):
            x = mat[:, j]
            ranks = pd.Series(x).rank(method='average').to_numpy()
            u = (ranks - 0.5) / n
            u = np.clip(u, eps, 1 - eps)
            Z[:, j] = norm.ppf(u)
        return Z

    def gaussian_copula_sample(self, df, columns, n_samples=1, random_state=None, min_group_corr_rows=20):
        """Sample using a category-conditional Gaussian copula.

        This sampler preserves both marginal category probabilities P(C) and
        conditional numeric distributions P(X|C). It can also fall back to a
        global correlation structure for small groups.

        Args:
            df: Source DataFrame with columns to model.
            columns: List of column names to include in the copula model.
            n_samples: Number of samples to draw.
            random_state: Optional random seed.
            min_group_corr_rows: Minimum rows needed in a group to estimate a
                group-specific correlation matrix. Otherwise the global
                correlation is used.

        Returns:
            DataFrame with sampled values for the requested columns.
        """
        rng = np.random.default_rng(random_state)
        X = df[columns].copy()

        # Split columns
        numeric_cols = [c for c in columns if np.issubdtype(X[c].dtype, np.number)]
        cat_cols = [c for c in columns if c not in numeric_cols]
        m = len(numeric_cols)

        # If no categoricals, revert to a plain Gaussian copula on numeric
        if len(cat_cols) == 0:
            if m == 0:
                return pd.DataFrame(index=range(n_samples), columns=columns)

            num_complete = X[numeric_cols].dropna()
            if len(num_complete) < 2:
                raise ValueError("Not enough non-missing numeric rows to fit copula.")

            Z = self._rank_to_z(num_complete.to_numpy())
            Sigma_global = self._make_psd(np.corrcoef(Z, rowvar=False))
            Z_samp = rng.multivariate_normal(np.zeros(m), Sigma_global, size=n_samples)
            U = norm.cdf(Z_samp)

            out = pd.DataFrame(index=range(n_samples), columns=columns)
            for j, c in enumerate(numeric_cols):
                vals = np.sort(X[c].dropna().to_numpy())
                if len(vals) == 0:
                    out[c] = np.nan
                    continue
                idx = np.floor(U[:, j] * len(vals)).astype(int).clip(0, len(vals) - 1)
                x = vals[idx]
                if np.issubdtype(X[c].dtype, np.integer):
                    x = np.round(x).astype(int)
                out[c] = x
            return out[columns]

        # Handle missing categories
        C = X[cat_cols].astype("object").fillna("__NA__")

        # Empirical joint over C
        counts = C.value_counts(dropna=False, sort=False)
        keys = counts.index.tolist()
        probs = (counts / counts.sum()).to_numpy()

        # Precompute global numeric marginals + global correlation as fallback
        global_sorted = {}
        for c in numeric_cols:
            vals = np.sort(X[c].dropna().to_numpy())
            global_sorted[c] = vals

        if m >= 2:
            num_complete = X[numeric_cols].dropna()
            if len(num_complete) >= 2:
                Zg = self._rank_to_z(num_complete.to_numpy())
                Sigma_global = self._make_psd(np.corrcoef(Zg, rowvar=False))
            else:
                Sigma_global = np.eye(m)
        elif m == 1:
            Sigma_global = np.array([[1.0]])
        else:
            Sigma_global = None

        # Build per-group info
        group_info = {}
        X_aug = X.copy()
        for c in cat_cols:
            X_aug[c] = C[c]

        grouped = X_aug.groupby(cat_cols, sort=False, dropna=False)
        for key, gdf in grouped:
            key = key if isinstance(key, tuple) else (key,)

            info = {}

            # Group-specific numeric marginals
            marginals = {}
            intlike = {}
            gmins, gmaxs = {}, {}

            for c in numeric_cols:
                vals = np.sort(gdf[c].dropna().to_numpy())
                marginals[c] = vals
                intlike[c] = np.issubdtype(X[c].dtype, np.integer)
                if len(vals) > 0:
                    gmins[c], gmaxs[c] = vals[0], vals[-1]
                else:
                    g = global_sorted[c]
                    gmins[c] = g[0] if len(g) else np.nan
                    gmaxs[c] = g[-1] if len(g) else np.nan

            info["marginals"] = marginals
            info["intlike"] = intlike
            info["mins"] = gmins
            info["maxs"] = gmaxs

            # Group-specific numeric copula correlation
            if m >= 2:
                num_complete_g = gdf[numeric_cols].dropna()
                if len(num_complete_g) >= max(2, min_group_corr_rows):
                    Zg = self._rank_to_z(num_complete_g.to_numpy())
                    Sg = np.corrcoef(Zg, rowvar=False)
                    if np.all(np.isfinite(Sg)):
                        info["Sigma"] = self._make_psd(Sg)
                    else:
                        info["Sigma"] = Sigma_global
                else:
                    info["Sigma"] = Sigma_global
            elif m == 1:
                info["Sigma"] = np.array([[1.0]])
            else:
                info["Sigma"] = None

            group_info[key] = info

        # Sampling
        out = pd.DataFrame(index=range(n_samples), columns=columns)

        # Sample category choices
        key_indices = np.arange(len(keys))
        chosen_idx = rng.choice(key_indices, size=n_samples, p=probs)
        chosen_keys = [keys[i] for i in chosen_idx]

        # Fill categorical columns
        for i, key in enumerate(chosen_keys):
            key = key if isinstance(key, tuple) else (key,)
            for col, val in zip(cat_cols, key):
                out.at[i, col] = (np.nan if val == "__NA__" else val)

        # Fill numeric columns conditional on chosen categories
        if m > 0:
            for i, key in enumerate(chosen_keys):
                key = key if isinstance(key, tuple) else (key,)
                info = group_info[key]
                Sigma = info["Sigma"]

                # Draw latent Z and convert to U
                z = rng.multivariate_normal(np.zeros(m), Sigma)
                u = norm.cdf(z)

                # Map through group-specific inverse CDFs
                for j, c in enumerate(numeric_cols):
                    vals = info["marginals"][c]
                    if len(vals) == 0:
                        vals = global_sorted[c]
                    if len(vals) == 0:
                        out.at[i, c] = np.nan
                        continue

                    idx = int(np.floor(u[j] * len(vals)))
                    if idx == len(vals):
                        idx -= 1
                    x = vals[idx]

                    if info["intlike"][c]:
                        x = int(np.round(x))
                        x = int(np.clip(x, info["mins"][c], info["maxs"][c]))
                    else:
                        x = float(np.clip(x, info["mins"][c], info["maxs"][c]))
                    out.at[i, c] = x

        return out[columns]

    def generate_from_input_data(self, n_consignments=1000, sampling_method=None):
        """Generate synthetic data based on input data using a selected method.

        Args:
            n_consignments: Number of unique consignments/shipments to generate.
            sampling_method: Sampling method to use (``'naive'``, ``'sequential'``,
                or ``'gmm'``). If None, the default method is used.

        Returns:
            DataFrame containing synthetic consignment records.

        Raises:
            ValueError: If no input data are loaded.
        """
        if self.input_data is None or len(self.input_data) == 0:
            raise ValueError("No usable input data loaded. Please provide a non-empty input_data_file.")

        method = sampling_method or DEFAULT_SAMPLING_METHOD
        target_cols = self._resolve_target_columns()
        return self._generate_with_method(method, target_cols, n_consignments)

    @staticmethod
    def calculate_quality_metrics(original_df, synthetic_df):
        """Calculate quality metrics comparing original and synthetic data.

        Metrics are based on the Wasserstein distance between marginal
        distributions for each common column.

        Args:
            original_df: Original DataFrame used as reference.
            synthetic_df: Synthetic DataFrame to be evaluated.

        Returns:
            Dictionary of quality metrics (e.g., ``'wasserstein_<col>'``).
        """
        if original_df is None:
            return {}

        metrics = {}

        # Get common columns
        common_cols = set(original_df.columns) & set(synthetic_df.columns)

        for col in common_cols:
            if col in original_df.columns and col in synthetic_df.columns:
                orig_vals = original_df[col].dropna()
                synth_vals = synthetic_df[col].dropna()

                if len(orig_vals) > 0 and len(synth_vals) > 0:
                    if np.issubdtype(orig_vals.dtype, np.number):
                        # For numeric columns, use Wasserstein distance
                        distance = wasserstein_distance(
                            orig_vals.astype(float).to_numpy(),
                            synth_vals.astype(float).to_numpy()
                        )
                    else:
                        # For categorical columns, use alphabetical ordering
                        # Get unique categories from both datasets
                        all_vals = pd.concat([
                            orig_vals.astype(str),
                            synth_vals.astype(str)
                        ])
                        unique_vals = all_vals.drop_duplicates().values
                        cats = pd.Index(unique_vals).sort_values()

                        enc = lambda s: pd.Categorical(s.astype(str), categories=cats, ordered=True).codes
                        oa, sa = map(enc, (orig_vals, synth_vals))

                        va, vs = map(pd.Series, (oa, sa))
                        orig_support, orig_weights = va.value_counts().sort_index().index.to_numpy(), va.value_counts().sort_index().values.astype(
                            float)
                        synth_support, synth_weights = vs.value_counts().sort_index().index.to_numpy(), vs.value_counts().sort_index().values.astype(
                            float)

                        distance = wasserstein_distance(
                            orig_support, synth_support,
                            u_weights=orig_weights, v_weights=synth_weights
                        )

                    metrics[f"wasserstein_{col}"] = distance

        return metrics

    @staticmethod
    def generate_statistics(dataset):
        """Generate simple summary statistics about a dataset.

        Args:
            dataset: DataFrame to analyze.

        Returns:
            Dictionary of dataset statistics including:
            * total record count,
            * list of columns,
            * list of numeric and categorical columns,
            * unique value counts for categoricals, and
            * basic statistics (mean, std, min, max) for numeric columns.
        """
        if dataset.empty:
            return {}

        stats = {
            "total_records": len(dataset),
            "columns": list(dataset.columns),
            "numeric_columns": [col for col in dataset.columns if np.issubdtype(dataset[col].dtype, np.number)],
            "categorical_columns": [col for col in dataset.columns if not np.issubdtype(dataset[col].dtype, np.number)],
        }

        # Add unique value counts for categorical columns
        for col in stats["categorical_columns"]:
            stats[f"unique_{col}"] = dataset[col].nunique()

        # Add basic statistics for numeric columns
        for col in stats["numeric_columns"]:
            stats[f"{col}_mean"] = dataset[col].mean()
            stats[f"{col}_std"] = dataset[col].std()
            stats[f"{col}_min"] = dataset[col].min()
            stats[f"{col}_max"] = dataset[col].max()

        return stats


def save_to_csv(dataset: pd.DataFrame, filename: Union[str, Path]) -> None:
    """Save a dataset to a CSV file.

    Args:
        dataset: DataFrame to save.
        filename: Output CSV filename or path.
    """
    path = Path(filename)
    dataset.to_csv(path, index=False)
    _log(f"Saved {len(dataset)} records to {path}")


def save_to_json(dataset: pd.DataFrame, filename: Union[str, Path]) -> None:
    """Save a dataset to a JSON file.

    Args:
        dataset: DataFrame to save.
        filename: Output JSON filename or path.
    """
    path = Path(filename)
    dataset.to_json(path, orient="records", indent=2)
    _log(f"Saved {len(dataset)} records to {path}")
