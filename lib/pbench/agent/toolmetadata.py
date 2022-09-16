"""Tool Metadata module

Classes for working with and manipulating the tool-scripts/meta.json file.
"""
import json


class ToolMetadataError(Exception):
    """ToolMetadataError - simple exception class for all exceptions raised by the
    ToolMetadata class.
    """

    pass


class ToolMetadata:
    """ToolMetadata - an in-memory representation of the on-disk meta.json file
    for tool metadata.
    """

    def __init__(self, inst_dir=None):
        """Constructor for a ToolMetadata object.

        Accepts an optional installation directory.  If one is not provided,
        then the two attributes of _json_path and _data are set to None.  When
        an installation directory is provided, the constructor loads the JSON
        data from {inst_dir}/tool-scripts/meta.json and validates it before
        finishing the object construction.
        """
        if inst_dir is None:
            self._json_path = None
            self._data = None
            return

        json_path = inst_dir / "tool-scripts" / "meta.json"
        try:
            self._json_path = json_path.resolve(strict=True)
        except FileNotFoundError:
            raise ToolMetadataError(f"missing {json_path}")
        except Exception:
            raise
        try:
            with self._json_path.open("r") as json_file:
                metadata = json.load(json_file)
        except FileNotFoundError:
            self._data = None
        except Exception:
            raise
        else:
            ToolMetadata._validate_metadata(metadata)
            self._data = metadata

    @staticmethod
    def _validate_metadata(metadata):
        """_validate_metadata - state method for validating the metadata dictionary
        object has the appropriate structure.
        """
        if "persistent" not in metadata:
            raise ToolMetadataError("Missing persistent tools")
        if "transient" not in metadata:
            raise ToolMetadataError("Missing transient tools")
        for tool in metadata["persistent"].keys():
            if tool in metadata["transient"].keys():
                raise ToolMetadataError(
                    f"Tool {tool} found in both transient and persistent tool lists"
                )
        for tool in metadata["transient"].keys():
            if tool in metadata["persistent"].keys():
                raise ToolMetadataError(
                    f"Tool {tool} found in both persistent and transient tool lists"
                )

    @classmethod
    def tool_md_from_dict(cls, metadata):
        """tool_md_from_dict - returns a ToolMetadata object given a raw dictionary."""
        ToolMetadata._validate_metadata(metadata)
        tmd = cls()
        tmd._data = metadata
        return tmd

    def getFullData(self):
        """getFullData - return the entire dictionary of metadata for both persistent
        and transient tools.
        """
        return self._data

    def getPersistentTools(self):
        """getPersistentTools - return a list of all the persistent tools
        supported.
        """
        return list(self._data["persistent"].keys())

    def getTransientTools(self):
        """getTransientTools - return a list of all the transient tools
        supported.
        """
        return list(self._data["transient"].keys())

    def getProperties(self, tool):
        """getProperties - return the recorded properties for the given tool."""
        try:
            tool_prop = self._data["transient"][tool]
        except KeyError:
            try:
                tool_prop = self._data["persistent"][tool]
            except KeyError:
                tool_prop = None
        return tool_prop

    def __str__(self):
        return str(self.getFullData())
