class Cache:
    def __init__(self):
        self.cache = {}
        
    def get(self, key):
        return self.cache.get(key, None)
        
    def set(self, key, value):
        self.cache[key] = value
        
    def clear(self):
        self.cache.clear()