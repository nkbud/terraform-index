"""Filesystem collector for terraform state files."""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, Dict, Any, Set

from .base import BaseCollector
from ..logging import LoggingMixin


class FileSystemCollector(BaseCollector, LoggingMixin):
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
        self.logger.info(f"📁 Starting filesystem collector (watching: {self.watch_directory})")
        self._running = True
        
        # Ensure watch directory exists
        self.watch_directory.mkdir(parents=True, exist_ok=True)
        self.logger.debug(f"Watch directory ensured: {self.watch_directory}")

    async def stop(self) -> None:
        """Clean up the collector."""
        self.logger.info("🛑 Stopping filesystem collector")
        self._running = False

    async def collect(self) -> AsyncIterator[Dict[str, Any]]:
        """
        Collect terraform state files from filesystem.
        
        Yields:
            Dict with 'content' (parsed tfstate JSON) and 'metadata'
        """
        self.logger.debug(f"Starting filesystem collection loop (poll interval: {self.poll_interval}s)")
        
        while self._running:
            try:
                # Scan for files
                files_found = 0
                async for item in self._scan_existing_files():
                    files_found += 1
                    self.logger.debug(f"Found new/updated file: {item['metadata']['source']}")
                    yield item
                
                if files_found > 0:
                    self.logger.info(f"📁 Processed {files_found} filesystem items")
                
                # Wait before next scan
                await asyncio.sleep(self.poll_interval)
                
            except Exception as e:
                self.logger.error(f"❌ Error in filesystem collector: {e}")
                self.logger.exception("Full error details:")
                await asyncio.sleep(1)

    async def _scan_existing_files(self) -> AsyncIterator[Dict[str, Any]]:
        """Scan directory for existing .tfstate files."""
        try:
            pattern = "**/*.tfstate" if self.recursive else "*.tfstate"
            self.logger.debug(f"Scanning {self.watch_directory} with pattern {pattern}")
            
            files_scanned = 0
            for file_path in self.watch_directory.glob(pattern):
                if file_path.is_file():
                    files_scanned += 1
                    async for item in self._process_file(str(file_path)):
                        yield item
            
            if files_scanned > 0:
                self.logger.debug(f"Scanned {files_scanned} .tfstate files")
                
        except Exception as e:
            self.logger.error(f"❌ Error scanning directory {self.watch_directory}: {e}")

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
            
            self.logger.debug(f"Processing new/updated file: {file_path}")
            
            # Read and parse file
            content = file_path_obj.read_text(encoding='utf-8')
            tfstate_data = json.loads(content)
            
            self.seen_files.add(file_id)
            
            file_size_kb = len(content) / 1024
            self.logger.debug(f"Loaded {file_size_kb:.1f}KB from {file_path}")
            
            yield {
                "content": tfstate_data,
                "metadata": {
                    "source": file_path,
                    "type": "filesystem",
                    "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "size_bytes": stat.st_size,
                    "collected_at": datetime.now().isoformat(),
                }
            }
            
        except json.JSONDecodeError as e:
            self.logger.error(f"❌ Invalid JSON in {file_path}: {e}")
        except Exception as e:
            self.logger.error(f"❌ Error processing file {file_path}: {e}")