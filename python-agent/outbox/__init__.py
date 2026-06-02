"""
Event outbox module for reliable event persistence and delivery.

This module provides persistent event storage using Redis to ensure
events are not lost during system failures or restarts.
"""

from .redis_outbox import RedisOutbox

__all__ = ["RedisOutbox"]