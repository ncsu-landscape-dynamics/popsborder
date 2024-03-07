# DEVELOPER.md

This document is intended to help developers understand how code is developed or to
provide ideas for developing code.

## Effectiveness

Here, the effectiveness is only for identifying contaminated items, not for identifying uncontaminated items as uncontaminated. 

* **effectiveness.py** - The file contains methods to check whether the effectiveness key is present in the config file and the effectiveness number is between 0 and 1. The Inspector class contains a method for generating a list of items with a given effectiveness percentage (1s). The "possibly_good_work" method uses this method to programmatically create false negatives to prevent contamination detection (human errors).

* **test_effectiveness.py** - This file contains the test cases for the effectiveness.py.

* **simulation.py** - A few new variables have been added to the simulation result. It is necessary to evaluate these variables since they are experimental. Find TODOs for evaluation and deletion.

  * *total_contaminated_items_missed*: The total number of contaminated items that were missed by the inspector.

  * *avg_items_missed_bf_detection*: This is for "items with no cluster strategy". The average number of contamination items missed before the first contamination item was detected.

  * *inspection_effectiveness*: Calculated by 

    total_contaminated_items_detected / (total_contaminated_items_detected + total_contaminated_items_missed)

    It should be close enough to the effectiveness value in the config file.

