import time
from collections import defaultdict
from config import RATE_LIMIT_WINDOW, MAX_REQUESTS

class RateLimiter:
    def __init__(self):
        self._requests = defaultdict(list)

    def can_proceed(self, user_id: int) -> bool:
        """Check if user can make a new request"""
        current_time = time.time()
        user_requests = self._requests[user_id]

        # Remove expired timestamps
        while user_requests and current_time - user_requests[0] > RATE_LIMIT_WINDOW:
            user_requests.pop(0)

        # Check if user has exceeded rate limit
        if len(user_requests) >= MAX_REQUESTS:
            return False

        # Add new request timestamp
        user_requests.append(current_time)
        return True
