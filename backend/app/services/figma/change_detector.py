"""Change detection service for Figma files using polling."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.models.figma_models import FileChangeEvent, WatchedFile
from app.services.figma.figma_service import FigmaService

logger = logging.getLogger(__name__)


class FigmaChangeDetector:
    """Service for detecting changes in Figma files through polling."""
    
    def __init__(
        self,
        figma_service: Optional[FigmaService] = None,
        polling_interval_minutes: Optional[int] = None,
    ):
        """Initialize the change detector.
        
        Args:
            figma_service: FigmaService instance to use.
            polling_interval_minutes: Override polling interval from config.
        """
        self.figma_service = figma_service or FigmaService()
        self.polling_interval = polling_interval_minutes or settings.figma.polling_interval_minutes
        
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._watched_files: dict[str, WatchedFile] = {}
        self._change_callbacks: list[Callable[[FileChangeEvent], Any]] = []
        self._is_running = False
    
    def add_watched_file(self, file_key: str, name: str) -> WatchedFile:
        """Add a file to watch for changes.
        
        Args:
            file_key: Figma file key.
            name: Human-readable name for the file.
            
        Returns:
            WatchedFile configuration object.
        """
        watched = WatchedFile(file_key=file_key, name=name)
        self._watched_files[file_key] = watched
        logger.info(f"Added file to watch: {name} ({file_key})")
        return watched
    
    def remove_watched_file(self, file_key: str) -> bool:
        """Remove a file from watching.
        
        Args:
            file_key: Figma file key to stop watching.
            
        Returns:
            True if file was being watched, False otherwise.
        """
        if file_key in self._watched_files:
            del self._watched_files[file_key]
            logger.info(f"Removed file from watch: {file_key}")
            return True
        return False
    
    def get_watched_files(self) -> list[WatchedFile]:
        """Get list of all watched files.
        
        Returns:
            List of WatchedFile objects.
        """
        return list(self._watched_files.values())
    
    def on_change(self, callback: Callable[[FileChangeEvent], Any]) -> None:
        """Register a callback for file change events.
        
        Args:
            callback: Function to call when a file changes.
        """
        self._change_callbacks.append(callback)
    
    async def _notify_change(self, event: FileChangeEvent) -> None:
        """Notify all registered callbacks of a change.
        
        Args:
            event: The change event to notify about.
        """
        for callback in self._change_callbacks:
            try:
                result = callback(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Error in change callback: {e}")
    
    async def check_file(self, file_key: str) -> Optional[FileChangeEvent]:
        """Check a single file for changes.
        
        Args:
            file_key: The Figma file key to check.
            
        Returns:
            FileChangeEvent if file changed, None otherwise.
        """
        if file_key not in self._watched_files:
            logger.warning(f"File {file_key} is not being watched")
            return None
        
        watched = self._watched_files[file_key]
        
        try:
            has_changed, new_version, new_modified = await self.figma_service.check_file_changed(
                file_key,
                watched.last_version,
                watched.last_modified,
            )
            
            watched.last_checked = datetime.now()
            
            if has_changed and new_version:
                logger.info(f"Change detected in {watched.name} ({file_key})")
                
                event = FileChangeEvent(
                    file_key=file_key,
                    file_name=watched.name,
                    old_version=watched.last_version,
                    new_version=new_version,
                    changed_at=new_modified or datetime.now(),
                )
                
                # Update watched file state
                watched.last_version = new_version
                watched.last_modified = new_modified
                
                # Notify callbacks
                await self._notify_change(event)
                
                return event
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking file {file_key}: {e}")
            return None
    
    async def check_all_files(self) -> list[FileChangeEvent]:
        """Check all watched files for changes.
        
        Returns:
            List of FileChangeEvent for files that changed.
        """
        events = []
        
        for file_key in self._watched_files:
            event = await self.check_file(file_key)
            if event:
                events.append(event)
        
        return events
    
    async def _polling_job(self) -> None:
        """Job executed by the scheduler to check for changes."""
        logger.debug("Running scheduled change detection...")
        await self.check_all_files()
    
    def start(self) -> None:
        """Start the polling scheduler."""
        if self._is_running:
            logger.warning("Change detector is already running")
            return
        
        self._scheduler = AsyncIOScheduler()
        self._scheduler.add_job(
            self._polling_job,
            IntervalTrigger(minutes=self.polling_interval),
            id="figma_change_detection",
            name="Figma Change Detection",
            replace_existing=True,
        )
        self._scheduler.start()
        self._is_running = True
        
        logger.info(f"Started change detection (polling every {self.polling_interval} minutes)")
    
    def stop(self) -> None:
        """Stop the polling scheduler."""
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
        self._is_running = False
        logger.info("Stopped change detection")
    
    @property
    def is_running(self) -> bool:
        """Check if the detector is running."""
        return self._is_running
    
    def load_watched_files_from_config(self) -> None:
        """Load watched files from configuration."""
        for file_config in settings.figma.watched_files:
            self.add_watched_file(file_config.file_key, file_config.name)
    
    async def initialize(self) -> None:
        """Initialize the change detector with config and perform initial check."""
        self.load_watched_files_from_config()
        
        # Perform initial check to get current versions
        for file_key, watched in self._watched_files.items():
            try:
                _, version, modified = await self.figma_service.check_file_changed(file_key)
                if version:
                    watched.last_version = version
                    watched.last_modified = modified
                    watched.last_checked = datetime.now()
                    logger.info(f"Initialized {watched.name}: version {version}")
            except Exception as e:
                logger.error(f"Error initializing file {file_key}: {e}")


# Global change detector instance
change_detector: Optional[FigmaChangeDetector] = None


def get_change_detector() -> FigmaChangeDetector:
    """Get or create the global change detector instance."""
    global change_detector
    if change_detector is None:
        change_detector = FigmaChangeDetector()
    return change_detector

