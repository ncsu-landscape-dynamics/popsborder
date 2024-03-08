def validate_effectiveness(config, verbose=False):
    """Set the effectiveness of the inspector.

    If effective is not set or even out of range, return 1. Otherwise, return the
    effectiveness set by user.

    :param config: Configuration file
    :param verbose: Print the message if True
    """
    try:
        if isinstance(config, dict):
            effectiveness = 1
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
