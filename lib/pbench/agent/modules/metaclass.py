from pathlib import Path
import json
import os


class BadConstruction(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)


class ToolMetadata:
    def __init__(self, mode, context, logger):
        self.logger = logger
        assert mode in (
            "redis",
            "json",
        ), f"Logic bomb! Unexpected mode, {mode}, encountered constructing tool meta data"
        if not context:
            raise (BadConstruction("No proper context given"))
        self.mode = mode
        if mode == "redis":
            self.redis_server = context
            self.json_file = None
        else:
            self.redis_server = None
            json_path = Path(context, "tool-scripts", "meta.json")
            try:
                self.json = json_path.resolve(strict=True)
            except FileNotFoundError:
                raise Exception(f"missing {json_path}")
            except Exception:
                raise
        self.data = self.__getInitialData()

    def __getInitialData(self):
        if self.mode == "json":
            if not os.path.isfile(self.json):
                self.logger.error(
                    "There is no tool-scripts/meta.json in given install dir"
                )
                return None
            with self.json.open("r") as json_file:
                metadata = json.load(json_file)
        elif self.mode == "redis":
            try:
                meta_raw = self.redis_server.get("tool-metadata")
                if meta_raw is None:
                    self.logger.error("Metadata has not been loaded into redis yet")
                    return None
                meta_str = meta_raw.decode("utf-8")
                metadata = json.loads(meta_str)
            except Exception:
                self.logger.error("Failure to reach redis server")
        return metadata

    def __dataCheck(self):
        if not self.data:
            self.data == self.__getInitialData()
            if not self.data:
                self.logger.error(f"Unable to access data through {self.mode}")
                return 0
        return 1

    def getFullData(self):
        if self.__dataCheck():
            return self.data
        return None

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

    def loadIntoRedis(self, info):
        if self.mode == "redis":
            try:
                self.json = Path(info).resolve(strict=True)
            except FileNotFoundError:
                raise Exception(f"missing {info}")
            except Exception:
                raise
        elif self.mode == "json":
            self.redis_server = info

        try:
            with self.json.open("r") as json_file:
                metadata = json.load(json_file)
                self.redis_server.set("tool-metadata", json.dumps(metadata))
        except Exception:
            self.logger.error("Failed to load the data into redis")
            raise
        return None
