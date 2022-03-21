import configparser


class MetadataLog(configparser.ConfigParser):
    """MetadataLog - a sub-class of ConfigParser that always has interpolation
    turned off with no other behavioral changes.
    """

    def __init__(self, *args, **kwargs):
        """Constructor - overrides `interpolation` to always be None."""
        kwargs["interpolation"] = None
        super().__init__(*args, **kwargs)
