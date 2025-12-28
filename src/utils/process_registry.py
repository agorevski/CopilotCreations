"""
Process registry for tracking and cleaning up subprocesses.

Provides a centralized way to track spawned subprocesses so they can be
terminated when the main process is killed or cancelled.
"""

import asyncio
import os
import signal
from typing import Set, Optional
from .logging import logger


class ProcessRegistry:
    """Registry for tracking active subprocesses."""
    
    def __init__(self) -> None:
        self._processes: Set[asyncio.subprocess.Process] = set()
        self._lock = asyncio.Lock()
    
    async def register(self, process: asyncio.subprocess.Process) -> None:
        """Register a subprocess for tracking."""
        async with self._lock:
            self._processes.add(process)
            logger.debug(f"Registered process PID {process.pid}")
    
    async def unregister(self, process: asyncio.subprocess.Process) -> None:
        """Unregister a subprocess from tracking."""
        async with self._lock:
            self._processes.discard(process)
            logger.debug(f"Unregistered process PID {process.pid}")
    
    async def kill_all(self) -> None:
        """Kill all tracked subprocesses."""
        async with self._lock:
            if not self._processes:
                return
            
            logger.info(f"Killing {len(self._processes)} tracked subprocess(es)...")
            
            for process in list(self._processes):
                try:
                    if process.returncode is None:  # Still running
                        logger.info(f"Killing subprocess PID {process.pid}")
                        process.kill()
                        try:
                            await asyncio.wait_for(process.wait(), timeout=5.0)
                        except asyncio.TimeoutError:
                            logger.warning(f"Subprocess PID {process.pid} did not terminate in time")
                except Exception as e:
                    logger.error(f"Error killing process PID {process.pid}: {e}")
            
            self._processes.clear()
    
    def kill_all_sync(self) -> None:
        """Synchronously kill all tracked subprocesses (for signal handlers)."""
        if not self._processes:
            return
        
        logger.info(f"Killing {len(self._processes)} tracked subprocess(es) (sync)...")
        
        for process in list(self._processes):
            try:
                if process.returncode is None:  # Still running
                    logger.info(f"Killing subprocess PID {process.pid}")
                    # On Windows, process.kill() sends SIGTERM-like signal
                    process.kill()
            except Exception as e:
                logger.error(f"Error killing process PID {process.pid}: {e}")
        
        self._processes.clear()
    
    @property
    def active_count(self) -> int:
        """Return the number of active tracked processes."""
        return len(self._processes)


# Global singleton instance
_process_registry: Optional[ProcessRegistry] = None


def get_process_registry() -> ProcessRegistry:
    """Get or create the global process registry."""
    global _process_registry
    if _process_registry is None:
        _process_registry = ProcessRegistry()
    return _process_registry
