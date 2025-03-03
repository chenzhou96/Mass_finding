class ThreadPool:
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            # 需在此初始化线程池相关属性
        return cls._instance