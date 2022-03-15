class InventoryManager:
    def __init__(self, loader, sources):
        self.loader = loader
        self.sources = sources

    def get_groups_dict(self):
        masters = ["masterA.example.com"]
        nodes = ["pprofA.example.com"]
        return {"masters": masters, "pprof": nodes}
