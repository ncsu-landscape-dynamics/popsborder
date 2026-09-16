# © 2026 The Johns Hopkins University Applied Physics Laboratory LLC

import streamlit as st

from gui.models import init_state
from gui.navigation import render_sidebar_navigation
from gui.page_styles import apply_shared_page_styles, render_page_intro, apply_glossary_page_styles


GLOSSARY_TERMS = [
    {
        "group": "Consignments",
        "term": "Consignment",
        "definition": "A named bundle of inspection units; also called a shipment.",
    },
    {
        "group": "Consignments",
        "term": "Inspection unit",
        "definition": "The single lowest, readily-distinguishable taxon, cultivar, "
                      "or variety that is clearly defined as being from one source and "
                      "in similar condition on the invoice, packing list, or phytosanitary certificate. "
                      "In PIS inspection data, also known as a commodity line.",
    },
    {
        "group": "Consignments",
        "term": "Consignment name/ID",
        "definition": "The unique label for a consignment.",
    },
    {
        "group": "Consignments",
        "term": "Synthetic consignments",
        "definition": "Fake consignments generated to mimic realistic consignments.",
    },
    {
        "group": "Consignments",
        "term": "Historical consignments",
        "definition": "Actual consignments from past inspections at plant inspection stations.",
    },
    {
        "group": "Consignments",
        "term": "Sampling method",
        "definition": "The algorithm used to generate synthetic consignments from source data.",
    },
    {
        "group": "Consignments",
        "term": "Producer grouping file",
        "definition": "An optional CSV file that groups producers (required if producers are used as feature in model); "
                      "used for entity resolution (maps raw names to groups that represent resolved entity names). "
                      "Note: These 'groups' are not used during data-driven consignment generation processes. "
                      "Raw producers generated, then this mapping is used to resolve them.",
    },
    {
        "group": "Consignments",
        "term": "Port of entry",
        "definition": "An official location where goods can legally enter the country.",
    },
    {
        "group": "Consignments",
        "term": "Country of origin",
        "definition": "The source country of an inspection unit.",
    },
    {
        "group": "Consignments",
        "term": "Propagative material type",
        "definition": "A class of propogative materials (e.g., unrooted cutting, tissue culture) as defined by PPQ.",
    },
    {
        "group": "Consignments",
        "term": "Pathway",
        "definition": "The transport route used for a consignment (e.g., Airport - Aircraft - Cargo - PIS)",
    },
    {
        "group": "Consignments",
        "term": "Sample units",
        "definition": "A sample unit is an individual member (e.g., box), selected from a population (e.g., boxes on a consignment), that is inspected.",
    },
    {
        "group": "Consignments",
        "term": "Sample units per inspection unit",
        "definition": "The number of sample units associated with a single inspection unit.",
    },
    {
        "group": "Consignments",
        "term": "Plants per sample unit",
        "definition": "How many plants are within each sample unit.",
    },
    {
        "group": "Consignments",
        "term": "RBS dataset",
        "definition": "The saved CSV output used by downstream pages for consignment, policy, and scenario workflows.", # Joe - I'll need your help on better describing what this actually is
    },
    {
        "group": "Consignments",
        "term": "Multinomial Sequential",
        "definition": "An approach to generate synthetic consignments that samples from multinomial distributions", # Joe - Please review
    },
    {
        "group": "Consignments",
        "term": "Gaussian Mixture",
        "definition": "An approach to generate synthetic consignments that samples from gaussian distributions", # Joe - Please review
    },
    {
        "group": "Contamination",
        "term": "Contaminated",
        "definition": "Whether an item (e.g., plant, sampling unit) had at least one pest, pathogen, or other contaminate.",
    },
    {
        "group": "Contamination",
        "term": "Contamination fit",
        "definition": "The workflow that estimates contamination parameters from selected consignment data.",
    },
    {
        "group": "Contamination",
        "term": "Consignment data source",
        "definition": "The file source used to fit contamination parameters on Page 2.",
    },
    {
        "group": "Contamination",
        "term": "Contamination parameter set name",
        "definition": "The name assigned to a saved contamination parameter set.",
    },
    {
        "group": "Contamination",
        "term": "Average contamination rate",
        "definition": "Given an uncertain contamination rate, the mean of the distribution describing the contamination rate.",
    },
    {
        "group": "Contamination",
        "term": "Alpha",
        "definition": "A beta-binomial shape parameter that helps control contamination rate.",
    },
    {
        "group": "Contamination",
        "term": "Beta",
        "definition": "The beta-binomial shape parameter paired with alpha, representing the uncertainty about the contamination rate.",
    },
    {
        "group": "Contamination",
        "term": "Beta-binomial",
        "definition": "The probability distribution used in the app to model uncertain contamination rates.",
    },
    {
        "group": "Contamination",
        "term": "Beta-binomial Probability Density Function (PDF)",
        "definition": "The chart that visualizes the fitted or saved beta-binomial contamination distribution.",
    },
    {
        "group": "Compliance",
        "term": "RBS compliance policy",
        "definition": "A policy that maps feature combinations of risk units to compliance levels.",
    },
    {
        "group": "Compliance",
        "term": "Compliance level upload",
        "definition": "A CSV that defines an RBS compliance policy.",
    },
    {
        "group": "Compliance",
        "term": "Detection/confidence mapping",
        "definition": "The CSV that maps compliance levels to detection and confidence values used in hypergeometric sampling.",
    },
    {
        "group": "Compliance",
        "term": "Feature columns",
        "definition": "Attributes of risk units used to determine their compliance level.",
    },
    {
        "group": "Compliance",
        "term": "Compliance level",
        "definition": "The policy category assigned to risk units, typically Poor, Low, Medium, or High.",
    },
    {
        "group": "Compliance",
        "term": "Detection level",
        "definition": "The smallest proportion of contaminated items in a finite lot that would be expected to be detected by the sampling plan.",
    },
    {
        "group": "Compliance",
        "term": "Confidence level",
        "definition": "The probability that the sampling plan will detect contamination when contamination is present at the detection level.",
    },
    {
        "group": "Compliance",
        "term": "Values for <feature>",
        "definition": "The allowed values selected for a chosen feature when manually building a policy.",
    },
    {
        "group": "Scenarios And Experiments",
        "term": "Experiment package",
        "definition": "A bundle of scenarios where a scenario represents a collection"
                      " of consignments generated (Page 1), "
                      "contamination parameter sets (Page 2),"
                      " RBS Compliancy policy (Page 3).",
    },
    {
        "group": "Scenarios And Experiments",
        "term": "Scenario table",
        "definition": "A table describing the scenarios of an experiment package.",
    },
    {
        "group": "Scenarios And Experiments",
        "term": "Scenario row",
        "definition": "One runnable configuration for a simulation.",
    },
    {
        "group": "Scenarios And Experiments",
        "term": "Scenario label",
        "definition": "The unique name used to identify a scenario row and its results.",
    },
    {
        "group": "Scenarios And Experiments",
        "term": "Files available",
        "definition": "The inventory of selectable datasets/parameter sets currently available for building scenarios.",
    },
    {
        "group": "Simulation",
        "term": "Action",
        "definition": "Action is taken when an actionable contaminate and/or pest was identified within the sampling units.",
    },{
        "group": "Simulation",
        "term": "Execution options",
        "definition": "The sidebar section where you choose replications and the experiment package to run.",
    },
    {
        "group": "Simulation",
        "term": "Simulation replications",
        "definition": "the number of times the same scenario is run to produce stable, reliable results despite randomness.",
    },
    {
        "group": "Simulation",
        "term": "Run experiment",
        "definition": "The action that starts the simulation pipeline for the selected experiment package.",
    },
    {
        "group": "Simulation",
        "term": "Run details",
        "definition": "The collapsed table showing the scenario setup that was executed.",
    },
    {
        "group": "Simulation",
        "term": "Run summary",
        "definition": "The section summarizing performance across scenarios, replications, shipments, inspections, and totals.",
    },
    {
        "group": "Simulation",
        "term": "Consignments per replication",
        "definition": "The number of consignments processed in each replication.",
    },
    {
        "group": "Simulation Results",
        "term": "Simulation summary view",
        "definition": "The control that switches the results to display either mean across replications, median across replications, or a single selected replication.",
    },
    {
        "group": "Simulation Results",
        "term": "Slippage",
        "definition": "Contaminated units (e.g., plants, sampling units) that evade detection.",
    },
    {
        "group": "Simulation Results",
        "term": "Slippage Level Results",
        "definition": "Results showing missed contaminated units at the consignment, inspection, sample, and plant levels.", # Joe - I am going to need some help here. It is not clear to me what I am looking at. Doesn't seem to match description.
    },
    {
        "group": "Simulation Results",
        "term": "Interceptions",
        "definition": "Results showing intercepted versus slipped outcomes by level.", 
    },
    {
        "group": "Simulation Results",
        "term": "Contamination Level Results - Contamination totals by level",
        "definition": "Results showing number of contaminated units across all consignments averaged across all replications."
                      " Calculated by summing all of the contaminated units (e.g., plants)"
                      " within each replication and then dividing by the total number of replications."
                      " Not contaminated represents the total number of units across all consignments"
                      " not contaminated averaged across replications (calculated by subtracting the total contaminated from the"
                      " total number of plants across all consignments for each replication and then divided by the"
                      " number of replications). 95% intervals represent the 95% confidence intervals using a normal distribution"
                      " of error.",
    },
    {
        "group": "Simulation Results",
        "term": "Contamination Level Results - Contamination percentages by level",
        "definition": "Results showing contamination rate across all consignments averaged across all replications."
                      " Calculated by summing all of the contaminated units across all consignments within a replication (e.g., plants),"
                      " dividing by the total number of units across all consignments (e.g., total number of plants on all consignments)"
                      " within each replication to construct the contamination rate for that replication."
                      " Then those rates are averaged across all replications."
                      " 95% intervals represent the 95% confidence intervals across replications on this rate using a standard"
                      " normal distribution of error.",
    },
    {
        "group": "Simulation Results",
        "term": "Inspection Workload Level Results - Number of units inspected",
        "definition": "Results showing number of units inspected (e.g., plants) across all consignments averaged across all replications."
                      " Calculated by summing all of inspected units (e.g., plants)"
                      " within each replication and then dividing by the total number of replications."
                      " 95% intervals represent the 95% confidence intervals using a standard normal distribution"
                      " of error.",
    },
    {
        "group": "Simulation Results",
        "term": "Contamination Level Results - Percent of units inspected",
        "definition": "Results showing proportion of units inspected (e.g., plants) across all consignments averaged across all replications."
                      " Calculated by summing all of inspected units (e.g., plants) across all consignments,"
                      " dividing by the total number of that unit (e.g., total number of plants across all consignments)"
                      " within each replication representing the proportion inspected across all consignemtns within that replication."
                      " Then those proportions are averaged across the replications."
                      " 95% intervals represent the 95% confidence intervals across the replications using a standard normal distribution"
                      " of error.",
    },
    {
        "group": "Simulation Results",
        "term": "Intercepted",
        "definition": "Contaminated units detected by the inspection process at the reported level.",
    },
    {
        "group": "Simulation Results",
        "term": "Slipped",
        "definition": "Contaminated units not detected by the inspection process at the reported level, representing slippage.",
    },
    {
        "group": "Simulation Results",
        "term": "95% Interval",
        "definition": "A 95% confidence interval for the mean of the metric of interest; computed assuming a normal distribution.",
    },
    {
        "group": "Simulation Results",
        "term": "lower",
        "definition": "The 2.5th percentile of slipped units across all replications",
    },
    {
        "group": "Simulation Results",
        "term": "upper",
        "definition": "The 97.5th percentile of slipped units across all replications",
    },
    {
        "group": "Simulation Results",
        "term": "Workload",
        "definition": "The number of items inspected.", 
    },
    {
        "group": "App Notes",
        "term": "RBS",
        "definition": "Risk-based Sampling",
    },
    {
        "group": "App Notes",
        "term": "PIS",
        "definition": "Plant Inspection Station",
    },
]


def _render_summary(total_terms: int) -> None:
    st.markdown(
        f"""
        <div class="glossary-summary">
            <div class="glossary-summary-title">Glossary Overview</div>
            <div class="glossary-summary-text">
                {total_terms} terms shown. Entries are listed alphabetically and tagged with the app section where they are mainly used.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_glossary_card(item: dict) -> None:
    st.markdown(
        f"""
        <div class="glossary-card">
            <div class="glossary-badge">{item["group"]}</div>
            <p class="glossary-term">{item["term"]}</p>
            <p class="glossary-definition">{item["definition"]}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.set_page_config(
    page_title="Glossary",
    page_icon=":book:",
    layout="wide",
)

init_state()
render_sidebar_navigation()
apply_shared_page_styles()
apply_glossary_page_styles()

st.warning(
    "**Test Deployment Notice: This is a test deployment with limited functionality and is under active development. "
    "Features may be incomplete and subject to change. Results have not been validated.**"
)
st.title("Glossary")
render_page_intro(
    "Reference definitions for terminology used across the app. "
    "These entries were compiled from the current page labels, controls, and results sections."
)

filter_cols = st.columns([2, 1])
with filter_cols[0]:
    search_text = st.text_input("Search glossary", value="", help="Filter glossary terms by name or definition.")
with filter_cols[1]:
    section_options = ["All sections"] + sorted({item["group"] for item in GLOSSARY_TERMS})
    selected_section = st.selectbox("Section", section_options, index=0)

query = search_text.strip().lower()

filtered = [
    item
    for item in GLOSSARY_TERMS
    if (selected_section == "All sections" or item["group"] == selected_section)
    and (not query or query in item["term"].lower() or query in item["definition"].lower() or query in item["group"].lower())
]

_render_summary(len(filtered))

if not filtered:
    st.info("No glossary terms match the current search.")
else:
    sorted_terms = sorted(filtered, key=lambda entry: entry["term"].lower())
    left_col, right_col = st.columns(2, gap="large")
    for idx, item in enumerate(sorted_terms):
        with (left_col if idx % 2 == 0 else right_col):
            _render_glossary_card(item)

st.divider()
nav_cols = st.columns(3)
with nav_cols[0]:
    if st.button("Reset and Return Home", type="secondary", key="nav_reset_page6"):
        st.session_state.clear()
        st.switch_page("frontend.py")
with nav_cols[1]:
    if st.button("Previous Page", type="primary", key="nav_back_page6"):
        st.switch_page("pages/5_Run_Simulation.py")
with nav_cols[2]:
    if st.button("Finish and Return Home", type="primary", key="nav_finish_page6"):
        st.switch_page("frontend.py")
