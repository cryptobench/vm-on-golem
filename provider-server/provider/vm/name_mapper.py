import asyncio
from typing import Optional, Dict
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class VMNameMapper:
    """Maps between requestor VM names and multipass VM names."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize name mapper.
        
        Args:
            db_path: Optional path to persist mappings
        """
        self._name_map: Dict[str, str] = {}  # requestor_name -> multipass_name
        self._reverse_map: Dict[str, str] = {}  # multipass_name -> requestor_name
        self._lock = asyncio.Lock()
        self._storage_path = db_path
        
        # Load existing mappings if storage path provided
        if db_path and db_path.exists():
            try:
                with open(db_path) as f:
                    data = json.load(f)
                    self._name_map = data.get('name_map', {})
                    self._reverse_map = data.get('reverse_map', {})
                logger.info(f"Loaded {len(self._name_map)} VM name mappings")
            except Exception as e:
                logger.error(f"Failed to load VM name mappings: {e}")

    async def add_mapping(self, requestor_name: str, multipass_name: str) -> None:
        """Add a new name mapping.
        
        Args:
            requestor_name: Name used by requestor
            multipass_name: Full multipass VM name
        """
        async with self._lock:
            self._name_map[requestor_name] = multipass_name
            self._reverse_map[multipass_name] = requestor_name
            await self._save_mappings()
            logger.info(f"Added mapping: {requestor_name} -> {multipass_name}")

    async def get_multipass_name(self, requestor_name: str) -> Optional[str]:
        """Get multipass name for a requestor name.
        
        Args:
            requestor_name: Name used by requestor
            
        Returns:
            Multipass VM name if found, None otherwise
        """
        return self._name_map.get(requestor_name)

    async def get_requestor_name(self, multipass_name: str) -> Optional[str]:
        """Get requestor name for a multipass name.
        
        Args:
            multipass_name: Full multipass VM name
            
        Returns:
            Requestor name if found, None otherwise
        """
        return self._reverse_map.get(multipass_name)

    async def remove_mapping(self, requestor_name: str) -> None:
        """Remove a name mapping.
        
        Args:
            requestor_name: Name used by requestor
        """
        async with self._lock:
            if requestor_name in self._name_map:
                multipass_name = self._name_map[requestor_name]
                del self._name_map[requestor_name]
                del self._reverse_map[multipass_name]
                await self._save_mappings()
                logger.info(f"Removed mapping: {requestor_name} -> {multipass_name}")

    async def _save_mappings(self) -> None:
        """Save mappings to storage if path provided."""
        if self._storage_path:
            try:
                data = {
                    'name_map': self._name_map,
                    'reverse_map': self._reverse_map
                }
                # Create parent directories if they don't exist
                self._storage_path.parent.mkdir(parents=True, exist_ok=True)
                # Write to temporary file first
                temp_path = self._storage_path.with_suffix('.tmp')
                with open(temp_path, 'w') as f:
                    json.dump(data, f, indent=2)
                # Rename temporary file to actual file (atomic operation)
                temp_path.rename(self._storage_path)
            except Exception as e:
                logger.error(f"Failed to save VM name mappings: {e}")

    def list_mappings(self) -> Dict[str, str]:
        """Get all current name mappings.
        
        Returns:
            Dictionary of requestor_name -> multipass_name mappings
        """
        return dict(self._name_map)
