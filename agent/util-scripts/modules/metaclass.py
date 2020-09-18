from pathlib import Path
import json
import os


class ToolMetadata:
    def __init__(self, mode, context, logger):
        self.logger = logger
        if mode not in ("redis", "json"):
            raise Exception()
        if not context:
            raise Exception()
        self.mode = mode
        if mode == "redis":
            self.redis_server = context
            self.json_file = None
        else:
            if not self.mode == "json":
                self.mode = json
                self.logger.debug("Defaulting mode to json")
            self.redis_server = None
            json_path = Path(context, "tool-scripts", "meta.json")
            try:
                self.json = json_path.resolve(strict=True)
            except FileNotFoundError:
                raise Exception(f"missing {json_path}")
            except Exception:
                raise
        self.data = None

    def getFullData(self):
        if self.data:
            return self.data

        if self.mode == "json":
            if not os.path.isfile(self.json):
                self.logger.error(
                    "There is no tool-scripts/meta.json in given install dir"
                )
                return None
            with self.json.open("r") as json_file:
                metadata = json.load(json_file)
                self.data = metadata
        elif self.mode == "redis":
            try:
                meta_raw = self.redis_server.get("tool-metadata")
                if meta_raw is None:
                    self.logger.error("Metadata was never loaded into redis")
                    return None
                meta_str = meta_raw.decode("utf-8")
                metadata = json.loads(meta_str)
                self.data = metadata
            except Exception:
                self.logger.error("Failure to reach redis server")
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
