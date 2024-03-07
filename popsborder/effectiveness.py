import random

import numpy as np


def validate_effectiveness(config, verbose=False):
    """Set the effectiveness of the inspector.

    If effective is not set or even out of range, return None. Otherwise, return the
    effectiveness set by user.

    :param config: Configuration file
    """
    try:
        if isinstance(config, dict):
            effectiveness = None
            if "effectiveness" in config["inspection"]:
                if 0 <= config["inspection"]["effectiveness"] <= 1:
                    effectiveness = config["inspection"]["effectiveness"]
                else:
                    if verbose:
                        print(
                            "Effectiveness out of range: it should be between "
                            "0 and 1."
                        )
            else:
                if verbose:
                    print("Effectiveness not set in the configuration file.")
    finally:
        return effectiveness


class Inspector:
    def __init__(self, effectiveness):
        self.effectiveness = effectiveness

    def generate_false_negative_item(self, size=10000):
        """Generate a list of items with a given percentage of true positives and
        randomly and then select one item from the list.

        :param size: Size of the list
        :return: A randomly selected item from the list 0 or 1
        """
        fn = 1 - self.effectiveness
        random_lst = np.random.choice([0, 1], size=size, p=[fn, self.effectiveness])
        zero_or_one = random.choice(random_lst)
        return zero_or_one

    def possibly_good_work(self):
        """Check if the inspector's work is good.

        Inspector inspects the contaminated item. Here, the inspector misses the
        contaminated item sometimes. Before calling this method, make sure the item is
        contaminated.

        :return: True the case of the inspector detected contaminated item or
        effectiveness is set to None, False otherwise.
        """
        if self.effectiveness is not None:
            zero_or_one = self.generate_false_negative_item()
            # num == 0 means the inspector missed contaminated item.
            if zero_or_one != 1:
                return False
        return True
