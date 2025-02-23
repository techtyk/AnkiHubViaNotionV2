from aqt.qt import QRunnable, QThreadPool  # 引入 Qt 中的 QRunnable 和 QThreadPool
from .config_manager import ConfigManager
from ...utils.logger import logger

class _SyncTask(QRunnable):
    """
    定义一个QRunnable任务类，用于在后台线程中执行同步策略。
    """
    def __init__(self, strategy):
        super().__init__()
        self.strategy = strategy

    def run(self):
        try:
            self.strategy.execute()
        except Exception as e:
            # 这里可以进一步替换为日志记录，也可通过信号机制反馈到 UI
            logger.error("执行同步策略时发生异常:", e)

class SyncExecutor:
    """多进程任务执行器（命令模式）"""
    
    def __init__(self):
        self.thread_pool = QThreadPool.globalInstance()
        self.config = ConfigManager()

    def execute_strategy(self, strategy):
        """启动多线程/异步执行"""
        task = _SyncTask(strategy)
        self.thread_pool.start(task)

    def execute_strategy_without_async_thread(self, strategy):
        """不借助多线程和协程，纯执行策略"""
        strategy.execute()
  
