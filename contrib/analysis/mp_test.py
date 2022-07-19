import pathos

class custom:
    def __init__(self):
        self.val = 0

    def worker(self, val):
        print(locals())
        return val + 1

    def execute(self):
        pool = pathos.pools.ProcessPool(4)
        val_list = [1,2,3,4]
        res = pool.map(self.worker, val_list)
        pool.close()
        pool.join()
        print(res)

if __name__ == "__main__":
    obj = custom()
    obj.execute()
