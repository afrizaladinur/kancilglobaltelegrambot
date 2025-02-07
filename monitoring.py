import logging
import time
import psutil
import os
from typing import Dict, Any
from datetime import datetime
from loguru import logger

class SystemMonitor:
    def __init__(self):
        self.start_time = time.time()
        self._setup_logging()

    def _setup_logging(self):
        """Configure advanced logging"""
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        log_level = logging.DEBUG
        log_file = 'bot.log'

        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)
        log_path = os.path.join('logs', log_file)

        # Configure root logger
        logging.basicConfig(
            format=log_format,
            level=log_level,
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(log_path, mode='a')
            ]
        )

        # Create a specific logger for the monitor
        self.logger = logging.getLogger('BotMonitor')
        self.logger.setLevel(log_level)

        # Log initial startup
        self.logger.info("System monitor initialized")

    def get_system_health(self) -> Dict[str, Any]:
        """Get system health metrics"""
        try:
            process = psutil.Process(os.getpid())
            metrics = {
                'uptime': time.time() - self.start_time,
                'memory_usage': process.memory_info().rss / 1024 / 1024,  # MB
                'cpu_percent': process.cpu_percent(),
                'thread_count': process.num_threads(),
                'open_files': len(process.open_files()),
                'connections': len(process.connections())
            }
            self.logger.debug(f"Health metrics collected: {metrics}")
            return metrics
        except Exception as e:
            self.logger.error(f"Error getting system health: {str(e)}")
            return {}

    async def check_database_health(self, data_store) -> Dict[str, Any]:
        """Check database connection and basic functionality"""
        try:
            async with data_store.pool.acquire() as conn:
                # Test basic connectivity
                await conn.execute("SELECT 1")

                # Get connection pool stats
                pool = data_store.pool
                pool_stats = {
                    'size': pool.get_size(),
                    'free_size': pool.get_free_size(),
                    'max_size': pool.get_max_size()
                }

                self.logger.info(f"Database health check passed. Pool stats: {pool_stats}")
                return {
                    'database_connected': True,
                    'pool_stats': pool_stats
                }
        except Exception as e:
            self.logger.error(f"Database health check failed: {str(e)}")
            return {'database_connected': False}

    def log_rate_limit_event(self, user_id: int, command: str):
        """Log rate limit events for monitoring"""
        self.logger.warning(f"Rate limit reached - User: {user_id}, Command: {command}")

    def log_error(self, error: Exception, context: Dict[str, Any] = None):
        """Enhanced error logging with context"""
        error_details = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'timestamp': datetime.now().isoformat(),
            'context': context or {}
        }
        self.logger.error(f"Error occurred: {error_details}", exc_info=True)

# Create singleton instance
monitor = SystemMonitor()