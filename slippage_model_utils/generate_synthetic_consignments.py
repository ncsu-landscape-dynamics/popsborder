# © 2026 The Johns Hopkins University Applied Physics Laboratory LLC

from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd
import sys
_repo_root = Path(__file__).resolve().parents[1]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

# Import functions from popsborder
from popsborder.inputs import load_configuration
from popsborder.generator import SyntheticConsignmentDataGenerator
from popsborder.inspections import construct_risk_units

# Import utility functions for contamination module
from slippage_model_utils.r_script_wrapper import *
from slippage_model_utils.engineered_feature_creator import  create_engineered_features
from slippage_model_utils.paths import DefaultPaths


def main():
    ### Initialize default paths
    default_paths = DefaultPaths()

    ### Set up data folder and file names
    data_dir = default_paths.slippage_data_dir()


    """Process command line parameters for generating synthetic consignment data"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--config",
                        type=str,
                        help="Configuration file name (top level of repository)",
                        default="config_rbs.yml"
                        )
    parser.add_argument("--num-consignments",
                        type=int,
                        help="Number of consignments to generate",
                        default=10,
                        )
    parser.add_argument("--synthetic-data-file-name",
                        type=str,
                        help="Name of the synthetic data output file",
                        default="Synthetic_Data_TEST.csv",
                        )
    parser.add_argument("--producer-group-mapping-path",
                        type=str,
                        help="Path to the producer grouping mapping created by the disambiguated producer processing"
                             " (i.e., entity resolution process)",
                        default=None,
                        )
    parser.add_argument("--compliance-table-path",
                        type=str,
                        help="Path to the compliance table (.csv file)",
                        default=str(data_dir / "compliance_table.csv"),
                        )
    parser.add_argument("--training-data-path",
                        type=str,
                        help="Path to data (.csv file) for building the synthetic consignments off of",
                        default=None,
                        )
    parser.add_argument("--create-engineered-features",
                        help="Flag to indicate if engineered features created by R code will be called",
                        action="store_true",
                        )
    parser.add_argument("--producer-importer-training-path",
                        type=str,
                        help="Path to data (.csv file) for building the synthetic consignments off of",
                        default=None,
                        )

    args = parser.parse_args()

    ### Extract inputs from command line arguments
    config_file = args.config
    num_consignments_to_simulate = args.num_consignments
    synthetic_data_file_name = args.synthetic_data_file_name


    # Extracting paths
    compliance_file = Path(args.compliance_table_path)


    # Load configuration and compliance table
    config = load_configuration(config_file)

    # Load producer group mapping
    if args.producer_group_mapping_path is None:
        raise ValueError("No producer group mapping path provided. Please provide a valid path (as a string)"
                         " using the CLI flag --producer-group-mapping-path <INSERT PATH>.")
    else:
        producer_group_mapping = pd.read_csv(Path(args.producer_group_mapping_path))

    # Load training data
    if args.training_data_path is None:
        raise ValueError("No training data provided. Please provide a valid path (as a string)"
                         " using the CLI flag --training-data-path <INSERT PATH>."
                         " See consignments.md for more information.")


    synthetic_data_generator = SyntheticConsignmentDataGenerator(config=config,
                                                                 producer_group_mapping=producer_group_mapping,
                                                                 input_data_file=Path(args.training_data_path))
    synth_out_path = data_dir / synthetic_data_file_name
    print(
        f'\nStarting Consignment Generation Process of {num_consignments_to_simulate} Requested Consignments...')
    synth_data = synthetic_data_generator.generate_from_input_data(
        n_consignments=num_consignments_to_simulate,
        sampling_method="sequential"
    )
    synth_data.loc[:, 'Row_ID'] = 'CR-' + (synth_data.index + 1).astype(str)

    if args.create_engineered_features:
        if args.producer_importer_training_path is None:
            # raise ValueError("No producer/importer training data provided. Please provide a valid path (as a string)"
            #                  " using the CLI flag --producer-importer-training-path <INSERT PATH>."
            #                  " See consignments.md for more information.")
            args.producer_importer_training_path = str(data_dir / "training_data_for_test_set.csv")
        try:
            ### Creating of Engineered Features ###
            # Create features from the R script using the R wrapper
            creator = RVariableCreator()

            # Read in training data used to create producer and importer top variables
            dt_train = pd.read_csv(Path(args.producer_importer_training_path))

            print(f'  Cleaning (and grouping where applicable) Categorical Names')
            print(f'      Cleaning Producer Name')
            synth_data['PRODUCER_NAME_RAW'] = synth_data['PRODUCER_NAME']
            synth_data['PRODUCER_NAME1'] = creator.batch_basic_text_preproc(text_fields=synth_data['PRODUCER_NAME_RAW'])

            producer_group_mapping = producer_group_mapping.rename(
                columns={"PRODUCER_NAME": "name", "grouping": "group"}
            )

            print(f'      Creating producer group mappings')
            synth_data = creator.entity_resolution(
                df=synth_data,
                entity_resolution_lookup_table=producer_group_mapping,
                use_parquet=False,  # or True, as you prefer
            )

            print(f'      Cleaning Importer Name')
            # Create a raw IMPORTER_NAME column with the original importer name
            synth_data['IMPORTER_NAME_RAW'] = synth_data['IMPORTER_NAME']

            # Update the IMPORTER_NAME column with the cleaned version.
            synth_data['IMPORTER_NAME1'] = creator.batch_basic_text_preproc(synth_data['IMPORTER_NAME_RAW'])

            # Reconstruct risk units based on configuration specification
            synth_data['PRODUCER_NAME'] = synth_data['PRODUCER_GROUP_NAME1']
            synth_data['IMPORTER_NAME'] = synth_data['IMPORTER_NAME1']
            synth_data = construct_risk_units(config=config, data=synth_data)

            # Pull in the VariableCreator object to use R code to create engineered columns based on created risk units
            synth_data = create_engineered_features(
                synth_data=synth_data,
                dt_train=dt_train,
                producer_group_mapping=producer_group_mapping
            )

            # Create a producer_group column
            synth_data['producer_group'] = synth_data['PRODUCER_GROUP_TOP']
            synth_data['IMPORTER_NAME'] = synth_data['IMPORTER_NAME_TOP']
        except:
            print('An error occurred while creating engineered features. Skipping.')

    synth_data.to_csv(synth_out_path)

if __name__ == "__main__":
    main()