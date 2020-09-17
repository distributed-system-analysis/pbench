from pathlib import Path
import json
import os


class ToolMetadata:
    def __init__(self, logger, redis_server=None, install_path=None):
        self.logger = logger
        if not redis_server and not install_path:
            self.logger.debug("Defaulting to /opt/pbench-agent")
            self.mode = "json"
            self.json = Path("/opt/pbench-agent", "tool-scripts", "meta.json")
        elif redis_server:
            self.mode = "redis"
            self.redis_server = redis_server
        else:
            self.mode = "json"
            self.json = Path(install_path, "tool-scripts", "meta.json")
        self.data = None

    def getFullData(self):
        if self.data:
            return self.data

        if self.mode == "json":
            if not os.path.isfile(self.json):
                self.logger.error('There is no tool-scripts/meta.json in given install dir')
                return None
            with self.json.open("r") as json_file:
                metadata = json.load(json_file)
                self.data = metadata
        elif self.mode == "redis":
            meta_raw = self.redis_server.get("tool-metadata")
            if meta_raw is None:
                self.logger.error('Metadata was never loaded into redis')
                return None
            meta_str = meta_raw.decode("utf-8")
            metadata = json.loads(meta_str)
            self.data = metadata
        return self.data

    def __dataCheck(self):
        if not self.data:
            if not self.getFullData():
                self.logger.error(f"Unable to access data through {self.mode}")
                return 0
        return 1

    def getPersistentTools(self):
        if self.__dataCheck():
            return list(self.data["persistent"].keys())
        return None

    def getTransientTools(self):
        if self.__dataCheck():
            return list(self.data["transient"].keys())
        return None

    def getProperties(self, tool):
        if tool in self.data["persistent"].keys():
            return self.data["persistent"][tool]
        elif tool in self.data["transient"].keys():
            return self.data["transient"][tool]
        return None
