from concurrent.futures import ThreadPoolExecutor

class ThreadPool:
    _instance = None
    _executor = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._executor = ThreadPoolExecutor(max_workers=5)
        return cls._instance

    def submit(self, fn, *args, **kwargs):
        return self._executor.submit(fn, *args, **kwargs)