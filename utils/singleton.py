import threading


class Singleton:
    _instances = {}
    _global_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls not in Singleton._instances:
            with Singleton._global_lock:
                if cls not in Singleton._instances:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    Singleton._instances[cls] = instance
        return Singleton._instances[cls]

    @classmethod
    def reset_instance(cls):
        with Singleton._global_lock:
            instance = Singleton._instances.pop(cls, None)
            if instance is not None:
                instance._initialized = False
