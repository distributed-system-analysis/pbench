from pathlib import Path
import re
from typing import Any, Union

# A set of types defined to conform to the semantic definition of a JSON
# structure with Python syntax.
JSONSTRING = str
JSONNUMBER = Union[int, float]
JSONVALUE = Union["JSONOBJECT", "JSONARRAY", JSONSTRING, JSONNUMBER, bool, None]
JSONARRAY = list[JSONVALUE]
JSONOBJECT = dict[JSONSTRING, JSONVALUE]
JSON = JSONVALUE


class JSONMap:
    """This constructs an object with attributes from a JSON object to make
    access a bit more convenient. E.g., in Javascript we can access
    object.attribute as well as object["attribute"] ... this mapper provides
    the same convenience for Python.

    Note that we don't try to set any attributes if the JSON dict contains any
    key which isn't a Python symbol.
    """

    SYMBOL = re.compile(r"^[\w_]+$")

    def __init__(self, json: JSONOBJECT):
        """Save the JSON payload; if all JSON keys are legal Python symbols,
        also enable direct access to them as attributes.

        Args:
            json:   JSON dictionary
        """
        self.json = json
        if all(self.SYMBOL.match(k) for k in json.keys()):
            for k, v in json.items():
                setattr(self, k, JSONMap(v) if isinstance(v, dict) else v)

    def __getitem__(self, key: str) -> Any:
        """Regardless of possible attribute mapping, allow access to any JSON
        key by index.

        Args:
            key:    JSON key

        Returns:
            The value of the JSON key in the dictionary
        """
        return self.json[key]


class Dataset(JSONMap):
    @staticmethod
    def stem(tarball: Union[str, Path]) -> str:
        return Path(tarball).name[:-7]

    @staticmethod
    def md5(tarball: Path) -> str:
        """Read the tarball MD5 from the tarball's companion file

        Args:
            tarball: Path to a tarball file with a {name}.md5 companion

        Returns:
            The tarball's MD5 value
        """
        md5_file = Path(f"{str(tarball)}.md5")
        return md5_file.read_text().split()[0]
