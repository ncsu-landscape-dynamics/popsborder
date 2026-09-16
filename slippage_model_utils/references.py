# © 2026 The Johns Hopkins University Applied Physics Laboratory LLC


"""Reference definitions and naming conventions for the slippage model.

Contributors:
    Gary Lin, Joseph Agor (Johns Hopkins University Applied Physics Laboratory)

This module centralizes:

* Column name aliases for PIS / RBS data.
* Required fields for specific model inputs.
* Domain-specific alias sets for RiskUnit attributes (origin, material type,
  port, etc.).
* Helper functions for fuzzy column-name resolution.
"""

from difflib import get_close_matches
from typing import List, Dict, Set



#####################################################
######## SYNTHETIC DATA GENERATOR REFERENCES ########
#####################################################

GENERATOR_TARGET_COLUMNS = [
    "INSPECTION_ID",
    "COUNTRY_OF_ORIGIN_NAME",
    "IMPORTER_NAME",
    "PRODUCER_NAME",
    "PROPAGATIVE_MATERIAL_TYPE",
    "QUANTITY",
    "BROKER_NAME",
    "INSPECTION_LOCATION_NAME",
    "PATHWAY",
    "INSPECTION_NUMBER",
    "action",
    "RISK_UNIT",
    "TOTAL_SAMPLING_UNITS_FOR_RISK_UNIT",
    "SAMPLING_UNITS_FOR_INSPECTION_UNIT",
    "REQUIRED_NUMBER_OF_BOXES",
]



#################################################
######## CONTAMINATION MODULE REFERENCES ########
#################################################


REQUIRED_FIELDS_CLARK_INPUT_GENERATION = [
        "INSPECTION_NUMBER",
        "RISK_UNIT",
        "action",
        "TOTAL_SAMPLING_UNITS_FOR_RISK_UNIT",
        "REQUIRED_NUMBER_OF_BOXES",
        "QUANTITY",
    ]


country_of_origin_names = {
    'Origin', 'origin', 'Origin Location Country Name', 'Origin Location Name',
    'Origin Name', 'Country Name', 'Country',
    'Country of Origin', 'Country of origin', 'Origin Country'
}
pm_type_names = {
    'Propagative Material Type', 'Propagative Material', 'PM Type',
    'PM', 'Material', 'Material Type'
}

producer_names = {
    'PRODUCER_NAME', 'Producer', 'Producer Name',
    'Prod', 'Producer Group', 'PRODUCER'
}

possible_pis_stations = {
    'Atlanta PIS',
    'Beltsville PIS',
    'Carolina PIS',
    'Guam PIS',
    'Honolulu PIS',
    'Houston PIS',
    'JFK PIS',
    'Linden PIS',
    'Los Angeles PIS',
    'Los Indios PIS',
    'Miami PIS',
    'Nogales PIS',
    'Orlando PIS',
    'San Diego PIS',
    'San Francisco PIS',
    'Seattle PIS'
}

engineered_features = {
    "producer_group": "Resolved Cleaned Producer Name",
    "median_qty_lt200": "Median Quantity of Inspection Units in the Risk Unit is Less Than 200 Units",
    "frac_small_gt07": "More than 7% of Inspection Units in the risk unit less than 200 units",
    "any_small": "Any single Inspection unit in the risk unit less than 200 units",
    "importer": "Cleaned Importer Name",
}

def get_domain_specific_aliases() -> Dict[str, Set[str]]:
    """Return hardcoded domain-specific aliases for RiskUnit attributes.

    These aliases capture common alternative names that may appear in
    compliance tables or PIS/RBS data and should map to canonical
    RiskUnit attributes (e.g., ``origin``, ``material_type``, ``port``,
    ``pathway``, and engineered features).

    Returns:
        Dictionary mapping canonical attribute names (e.g. ``"origin"``)
        to sets of alias strings.
    """
    return {
        'origin': {
            'country of origin',
            'country_of_origin',
            'origin country',
            'source country',
            'country',
            'COUNTRY_OF_ORIGIN_NAME',
            'coo',
        },
        'material_type': {
            'propagative material type',
            'PROPAGATIVE_MATERIAL_TYPE',
            'pm type',
            'material',
            'type',
            'commodity',
            'commodity type',
        },
        'port': {
            'inspection location',
            'INSPECTION_LOCATION_NAME',
            'pis station',
            'station',
            'location',
            'inspection station',
            'entry port',
        },
        'pathway': {
            'PATHWAY',
            'entry pathway',
            'import pathway',
        },
        'producer_group': {
            'producer',
            'grower',
            'producer group',
            'prod_group_name',
            'PRODUCER_GROUP_TOP',
        },
        'median_qty_lt200': {
            'median qty lt200',
            'MEDIAN_QTY_LT200',
            'small quantity',
            'qty lt 200',
        },
        'frac_small': {
            'fraction small',
            'FRAC_SMALL',
            'small fraction',
        },
        'frac_small_gt07': {
            'fraction small gt 07',
            'FRAC_SMALL_GT07',
            'frac small gt 0.7',
        },
        'any_small': {
            'ANY_SMALL',
            'has small',
            'contains small',
        },
        'importer': {
            'IMPORTER_NAME',
            'IMPORTER_NAME_TOP',
        },
    }



COLUMN_NAME_ALIASES = {
    'comm_ID': [
        'comm_id', 'commid', 'comm id',
        'COMM_ID', 'COMMID', 'COMM ID',
        'Comm_Id', 'CommId', 'Comm Id'
    ],
    'INSPECTION_ID': [
        'inspection_id', 'inspectionid', 'inspection id',
        'Inspection_Id', 'InspectionId', 'Inspection Id'
    ],
    'REF_COMMODITY_ID': [
        'ref_commodity_id', 'refcommodityid', 'ref commodity id',
        'Ref_Commodity_Id', 'RefCommodityId', 'Ref Commodity Id'
    ],
    'CERTIFIED_FACILITY_NAME': [
        'certified_facility_name', 'certifiedfacilityname', 'certified facility name',
        'Certified_Facility_Name', 'CertifiedFacilityName', 'Certified Facility Name'
    ],
    'CERTIFIED_FACILITY_NUMBER': [
        'certified_facility_number', 'certifiedfacilitynumber', 'certified facility number',
        'Certified_Facility_Number', 'CertifiedFacilityNumber', 'Certified Facility Number'
    ],
    'COMMODITY_CLASSIFICATION': [
        'commodity_classification', 'commodityclassification', 'commodity classification',
        'Commodity_Classification', 'CommodityClassification', 'Commodity Classification'
    ],
    'COMMODITY_COMMON_NAME': [
        'commodity_common_name', 'commoditycommonname', 'commodity common name',
        'Commodity_Common_Name', 'CommodityCommonName', 'Commodity Common Name'
    ],
    'COMMODITY_DISPLAY_NAME': [
        'commodity_display_name', 'commoditydisplayname', 'commodity display name',
        'Commodity_Display_Name', 'CommodityDisplayName', 'Commodity Display Name'
    ],
    'COMMODITY_TAXONOMIC_DISPLAY_NAME': [
        'commodity_taxonomic_display_name', 'commoditytaxonomicdisplayname',
        'commodity taxonomic display name',
        'Commodity_Taxonomic_Display_Name', 'CommodityTaxonomicDisplayName',
        'Commodity Taxonomic Display Name'
    ],
    'COMMODITY_HOST_TYPE': [
        'commodity_host_type', 'commodityhosttype', 'commodity host type',
        'Commodity_Host_Type', 'CommodityHostType', 'Commodity Host Type'
    ],
    'COMMODITY_TYPE': [
        'commodity_type', 'commoditytype', 'commodity type',
        'Commodity_Type', 'CommodityType', 'Commodity Type'
    ],
    'COUNTRY_OF_ORIGIN_NAME': [
        'country_of_origin_name', 'countryoforiginname', 'country of origin name',
        'Country_Of_Origin_Name', 'CountryOfOriginName', 'Country Of Origin Name',
        'origin', 'origin name', 'Origin Name', 'Origin', 'Origin_Name',
        'OriginName', 'originname', 'origin_name', 'ORIGIN', 'ORIGIN_NAME',
        'ORIGINNAME'
    ],
    'CONSIGNEE_NAME': [
        'consignee_name', 'consigneename', 'consignee name',
        'Consignee_Name', 'ConsigneeName', 'Consignee Name'
    ],
    'DESTINATION_STATE_NAME': [
        'destination_state_name', 'destinationstatename', 'destination state name',
        'Destination_State_Name', 'DestinationStateName', 'Destination State Name'
    ],
    'DISPOSITION_CODE': [
        'disposition_code', 'dispositioncode', 'disposition code',
        'Disposition_Code', 'DispositionCode', 'Disposition Code'
    ],
    'GENUS_NAME': [
        'genus_name', 'genusname', 'genus name',
        'Genus_Name', 'GenusName', 'Genus Name'
    ],
    'ENTRY_NUMBER': [
        'entry_number', 'entrynumber', 'entry number',
        'Entry_Number', 'EntryNumber', 'Entry Number'
    ],
    'ENTRY_LINE_NUMBER': [
        'entry_line_number', 'entrylinenumber', 'entry line number',
        'Entry_Line_Number', 'EntryLineNumber', 'Entry Line Number'
    ],
    'PGA_LINE_NUMBER': [
        'pga_line_number', 'pgalinenumber', 'pga line number',
        'Pga_Line_Number', 'PgaLineNumber', 'Pga Line Number'
    ],
    'PRODUCER_ID': [
        'producer_id', 'producerid', 'producer id',
        'Producer_Id', 'ProducerId', 'Producer Id'
    ],
    'PRODUCER_NAME': [
        'producer_name', 'producername', 'producer name',
        'Producer_Name', 'ProducerName', 'Producer Name'
    ],
    'PROPAGATIVE_MATERIAL_TYPE': [
        'propagative_material_type', 'propagativematerialtype', 'propagative material type',
        'Propagative_Material_Type', 'PropagativeMaterialType', 'Propagative Material Type',
        'PM Type', 'pm type', 'PM_Type', 'pm_type'
    ],
    'QUANTITY': [
        'quantity', 'Quantity', 'QUANTITY'
    ],
    'QUANTITY_UNITS_NAME': [
        'quantity_units_name', 'quantityunitsname', 'quantity units name',
        'Quantity_Units_Name', 'QuantityUnitsName', 'Quantity Units Name'
    ],
    'WADS_CODE': [
        'wads_code', 'wadscode', 'wads code',
        'Wads_Code', 'WadsCode', 'Wads Code'
    ],
    'SAMPLING_UNITS': [
        'sampling_units', 'samplingunits', 'sampling units',
        'Sampling_Units', 'SamplingUnits', 'Sampling Units'
    ],
    'IS_RBS': [
        'is_rbs', 'isrbs', 'is rbs',
        'Is_Rbs', 'IsRbs', 'Is Rbs'
    ],
    'RBS_STATUS': [
        'rbs_status', 'rbsstatus', 'rbs status',
        'Rbs_Status', 'RbsStatus', 'Rbs Status'
    ],
    'GROWING_MEDIA_PRESENCE': [
        'growing_media_presence', 'growingmediapresence', 'growing media presence',
        'Growing_Media_Presence', 'GrowingMediaPresence', 'Growing Media Presence'
    ],
    'CREATED_DATETIME': [
        'created_datetime', 'createddatetime', 'created datetime',
        'Created_Datetime', 'CreatedDatetime', 'Created Datetime'
    ],
    'INSPECTION_DATETIME': [
        'inspection_datetime', 'inspectiondatetime', 'inspection datetime',
        'Inspection_Datetime', 'InspectionDatetime', 'Inspection Datetime'
    ],
    'BROKER_NAME': [
        'broker_name', 'brokername', 'broker name',
        'Broker_Name', 'BrokerName', 'Broker Name'
    ],
    'CATEGORY': [
        'category', 'Category', 'CATEGORY'
    ],
    'SUBCATEGORY': [
        'subcategory', 'Subcategory', 'SUBCATEGORY'
    ],
    'IMPORTER_NAME': [
        'importer_name', 'importername', 'importer name',
        'Importer_Name', 'ImporterName', 'Importer Name'
    ],
    'INSPECTION_LOCATION_NAME': [
        'inspection_location_name', 'inspectionlocationname', 'inspection location name',
        'Inspection_Location_Name', 'InspectionLocationName', 'Inspection Location Name'
    ],
    'INSPECTION_LOCATION_ID': [
        'inspection_location_id', 'inspectionlocationid', 'inspection location id',
        'Inspection_Location_Id', 'InspectionLocationId', 'Inspection Location Id'
    ],
    'INSPECTION_NUMBER': [
        'inspection_number', 'inspectionnumber', 'inspection number',
        'Inspection_Number', 'InspectionNumber', 'Inspection Number'
    ],
    'PATHWAY_ID': [
        'pathway_id', 'pathwayid', 'pathway id',
        'Pathway_Id', 'PathwayId', 'Pathway Id'
    ],
    'PATHWAY': [
        'pathway', 'Pathway', 'PATHWAY'
    ],
    'SHIPPER_NAME': [
        'shipper_name', 'shippername', 'shipper name',
        'Shipper_Name', 'ShipperName', 'Shipper Name'
    ],
    'INSPECTION_LOCATION_STATE_CODE': [
        'inspection_location_state_code', 'inspectionlocationstatecode',
        'inspection location state code',
        'Inspection_Location_State_Code', 'InspectionLocationStateCode',
        'Inspection Location State Code'
    ],
    'RISK_UNIT': [
        'risk_unit', 'riskunit', 'risk unit',
        'Risk_Unit', 'RiskUnit', 'Risk Unit'
    ],
    'Row_ID': [
        'row_id', 'rowid', 'row id',
        'Row_Id', 'RowId', 'Row Id'
    ],
    'producer_group': [
        'producergroup', 'producer group', 'producer',
        'Producer_Group', 'ProducerGroup', 'Producer Group',
        'PRODUCER_GROUP', 'PRODUCERGROUP', 'PRODUCER GROUP'
    ],
}



def find_column_name(var: str = None,
                     available_columns: List = None,
                     alias_dict: dict = None,
                     cutoff: float = 0.6):
    """Find the best-matching column name given an input variable string.

    The search attempts:

    1. Case-insensitive exact matches in ``available_columns``.
    2. Direct matches against aliases in ``alias_dict``.
    3. Fuzzy matches against available column names.
    4. Fuzzy matches against all aliases of columns present in
       ``available_columns``.

    Args:
        var: Input variable name to resolve.
        available_columns: List of actual column names in the DataFrame.
        alias_dict: Mapping from canonical column names to a list of alias
            strings. If None, defaults to :data:`COLUMN_NAME_ALIASES`.
        cutoff: Similarity threshold (0.0–1.0) used by
            :func:`difflib.get_close_matches`.

    Returns:
        The chosen column name as a string, or None if no suitable match
        is found.
    """
    # Use the module-level constant if none provided
    if alias_dict is None:
        alias_dict = COLUMN_NAME_ALIASES

    # Normalize input
    var_normalized = var.lower().strip().replace(' ', '_')

    # Exact match in available columns (case-insensitive)
    for col in available_columns:
        if col.lower() == var_normalized:
            print(col)
            return col

    # Check against alias dictionary
    for canonical_name, aliases in alias_dict.items():
        if canonical_name in available_columns:
            if var_normalized in aliases:
                return canonical_name

    # Fuzzy match against available columns
    match = get_close_matches(var_normalized,
                              [c.lower() for c in available_columns],
                              n=1,
                              cutoff=cutoff)
    if match:
        # Find the original column name (with correct case)
        for col in available_columns:
            if col.lower() == match[0]:
                return col

    # Fuzzy match against all possible aliases
    all_aliases = []
    alias_to_canonical = {}

    for canonical_name, aliases in alias_dict.items():
        if canonical_name in available_columns:
            for alias in aliases:
                all_aliases.append(alias)
                alias_to_canonical[alias] = canonical_name

    match = get_close_matches(var_normalized, all_aliases, n=1, cutoff=cutoff)
    if match:
        return alias_to_canonical[match[0]]

    return None
