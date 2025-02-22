# 专门负责多进程任务调度和管理，将耗时任务放到独立的进程中执行，避免阻塞主进程
from multiprocessing import Process
from .config_manager import ConfigManager

class SyncExecutor:
    """多进程任务执行器（命令模式）"""
    
    def __init__(self):
        self.config = ConfigManager()
    
    def execute_strategy(self, strategy):
        """启动子进程执行策略"""
        def worker():
            strategy.execute()
        worker()    
        # p = Process(target=worker)
        # p.start()
        # 先不实现多进程，保持简单