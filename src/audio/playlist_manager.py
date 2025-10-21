import os
import json
import logging
from typing import Dict, List, Optional

class PlaylistManager:
    """
    Manages playlists with JSON persistence.
    """
    
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.playlists = {}  # name -> list of file paths
        self.current_playlist = None
        
        # Set up playlist storage path
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.playlist_path = os.path.join(script_dir, '../../data/playlists.json')
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.playlist_path), exist_ok=True)
        
        # Load existing playlists
        self._load_playlists()
    
    def create_playlist(self, name: str, file_paths: List[str] = None) -> bool:
        """
        Create a new playlist.
        
        Args:
            name (str): Playlist name
            file_paths (List[str], optional): Initial file paths
            
        Returns:
            bool: True if created successfully, False if name already exists
        """
        if name in self.playlists:
            self.logger.warning(f"Playlist '{name}' already exists")
            return False
        
        self.playlists[name] = file_paths or []
        self._save_playlists()
        self.logger.info(f"Created playlist '{name}' with {len(self.playlists[name])} files")
        return True
    
    def save_playlist(self, name: str, file_paths: List[str]) -> bool:
        """
        Save/update a playlist.
        
        Args:
            name (str): Playlist name
            file_paths (List[str]): File paths to save
            
        Returns:
            bool: True if saved successfully
        """
        self.playlists[name] = file_paths.copy()
        self._save_playlists()
        self.logger.info(f"Saved playlist '{name}' with {len(file_paths)} files")
        return True
    
    def load_playlists(self) -> Dict[str, List[str]]:
        """
        Load all playlists.
        
        Returns:
            Dict[str, List[str]]: Dictionary of playlist names to file paths
        """
        self._load_playlists()
        return self.playlists.copy()
    
    def delete_playlist(self, name: str) -> bool:
        """
        Delete a playlist.
        
        Args:
            name (str): Playlist name to delete
            
        Returns:
            bool: True if deleted successfully, False if not found
        """
        if name not in self.playlists:
            self.logger.warning(f"Playlist '{name}' not found")
            return False
        
        del self.playlists[name]
        
        # If this was the current playlist, clear it
        if self.current_playlist == name:
            self.current_playlist = None
        
        self._save_playlists()
        self.logger.info(f"Deleted playlist '{name}'")
        return True
    
    def add_to_playlist(self, playlist_name: str, file_path: str) -> bool:
        """
        Add a file to a playlist.
        
        Args:
            playlist_name (str): Playlist name
            file_path (str): File path to add
            
        Returns:
            bool: True if added successfully
        """
        if playlist_name not in self.playlists:
            self.logger.warning(f"Playlist '{playlist_name}' not found")
            return False
        
        if file_path not in self.playlists[playlist_name]:
            self.playlists[playlist_name].append(file_path)
            self._save_playlists()
            self.logger.info(f"Added file to playlist '{playlist_name}': {os.path.basename(file_path)}")
            return True
        
        return False  # File already in playlist
    
    def remove_from_playlist(self, playlist_name: str, file_path: str) -> bool:
        """
        Remove a file from a playlist.
        
        Args:
            playlist_name (str): Playlist name
            file_path (str): File path to remove
            
        Returns:
            bool: True if removed successfully
        """
        if playlist_name not in self.playlists:
            self.logger.warning(f"Playlist '{playlist_name}' not found")
            return False
        
        if file_path in self.playlists[playlist_name]:
            self.playlists[playlist_name].remove(file_path)
            self._save_playlists()
            self.logger.info(f"Removed file from playlist '{playlist_name}': {os.path.basename(file_path)}")
            return True
        
        return False  # File not in playlist
    
    def get_playlist_files(self, playlist_name: str) -> List[str]:
        """
        Get files in a playlist.
        
        Args:
            playlist_name (str): Playlist name
            
        Returns:
            List[str]: List of file paths, empty if playlist not found
        """
        return self.playlists.get(playlist_name, []).copy()
    
    def get_playlist_names(self) -> List[str]:
        """
        Get all playlist names.
        
        Returns:
            List[str]: Sorted list of playlist names
        """
        return sorted(self.playlists.keys())
    
    def set_current_playlist(self, playlist_name: Optional[str]) -> bool:
        """
        Set the current active playlist.
        
        Args:
            playlist_name (str, optional): Playlist name, None to clear
            
        Returns:
            bool: True if set successfully
        """
        if playlist_name is None:
            self.current_playlist = None
            return True
        
        if playlist_name in self.playlists:
            self.current_playlist = playlist_name
            self.logger.info(f"Set current playlist to '{playlist_name}'")
            return True
        
        self.logger.warning(f"Playlist '{playlist_name}' not found")
        return False
    
    def get_current_playlist(self) -> Optional[str]:
        """
        Get the current active playlist name.
        
        Returns:
            Optional[str]: Current playlist name or None
        """
        return self.current_playlist
    
    def get_current_playlist_files(self) -> List[str]:
        """
        Get files in the current playlist.
        
        Returns:
            List[str]: List of file paths in current playlist, empty if none
        """
        if self.current_playlist:
            return self.get_playlist_files(self.current_playlist)
        return []
    
    def is_file_in_playlist(self, playlist_name: str, file_path: str) -> bool:
        """
        Check if a file is in a playlist.
        
        Args:
            playlist_name (str): Playlist name
            file_path (str): File path to check
            
        Returns:
            bool: True if file is in playlist
        """
        return file_path in self.playlists.get(playlist_name, [])
    
    def _load_playlists(self):
        """Load playlists from JSON file."""
        try:
            if os.path.exists(self.playlist_path):
                with open(self.playlist_path, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.playlists = data
                    else:
                        self.playlists = {}
                self.logger.info(f"Loaded {len(self.playlists)} playlists")
            else:
                self.playlists = {}
                self.logger.info("No existing playlists found, starting fresh")
        except Exception as e:
            self.logger.error(f"Error loading playlists: {e}")
            self.playlists = {}
    
    def _save_playlists(self):
        """Save playlists to JSON file."""
        try:
            with open(self.playlist_path, 'w') as f:
                json.dump(self.playlists, f, indent=2)
            self.logger.debug(f"Saved {len(self.playlists)} playlists")
        except Exception as e:
            self.logger.error(f"Error saving playlists: {e}")
