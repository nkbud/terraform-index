"""Filesystem collector for terraform state files."""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, Dict, Any, Set

from .base import BaseCollector


class FileSystemCollector(BaseCollector):
    """Collects terraform state files from local filesystem."""

    def __init__(
        self,
        watch_directory: str,
        poll_interval: int = 5,
        recursive: bool = True,
    ):
        """
        Initialize filesystem collector.
        
        Args:
            watch_directory: Directory to watch for .tfstate files
            poll_interval: Interval in seconds for polling existing files
            recursive: Whether to watch subdirectories recursively
        """
        self.watch_directory = Path(watch_directory)
        self.poll_interval = poll_interval
        self.recursive = recursive
        self.seen_files: Set[str] = set()
        self._running = False

    async def start(self) -> None:
        """Initialize the collector."""
        self._running = True
        
        # Ensure watch directory exists
        self.watch_directory.mkdir(parents=True, exist_ok=True)

    async def stop(self) -> None:
        """Clean up the collector."""
        self._running = False

    async def collect(self) -> AsyncIterator[Dict[str, Any]]:
        """
        Collect terraform state files from filesystem.
        
        Yields:
            Dict with 'content' (parsed tfstate JSON) and 'metadata'
        """
        while self._running:
            try:
                # Scan for files
                async for item in self._scan_existing_files():
                    yield item
                
                # Wait before next scan
                await asyncio.sleep(self.poll_interval)
                
            except Exception as e:
                print(f"Error in filesystem collector: {e}")
                await asyncio.sleep(1)

    async def _scan_existing_files(self) -> AsyncIterator[Dict[str, Any]]:
        """Scan directory for existing .tfstate files."""
        try:
            pattern = "**/*.tfstate" if self.recursive else "*.tfstate"
            for file_path in self.watch_directory.glob(pattern):
                if file_path.is_file():
                    async for item in self._process_file(str(file_path)):
                        yield item
        except Exception as e:
            print(f"Error scanning directory {self.watch_directory}: {e}")

    async def _process_file(self, file_path: str) -> AsyncIterator[Dict[str, Any]]:
        """Process a single .tfstate file."""
        file_path_obj = Path(file_path)
        
        try:
            # Get file stats
            stat = file_path_obj.stat()
            file_id = f"{file_path}:{stat.st_mtime}"
            
            # Skip if already processed
            if file_id in self.seen_files:
                return
            
            # Read and parse file
            content = file_path_obj.read_text(encoding='utf-8')
            tfstate_data = json.loads(content)
            
            self.seen_files.add(file_id)
            
            yield {
                'content': tfstate_data,
                'metadata': {
                    'source': 'filesystem',
                    'path': str(file_path),
                    'size': stat.st_size,
                    'last_modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'collected_at': datetime.utcnow().isoformat(),
                }
            }
            
        except (json.JSONDecodeError, OSError, IOError) as e:
            print(f"Error processing file {file_path}: {e}")
        except Exception as e:
            print(f"Unexpected error processing file {file_path}: {e}")