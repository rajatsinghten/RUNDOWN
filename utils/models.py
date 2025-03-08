from flask import session
import os
import json
from config import TOKENS_DIR

class UserPreferences:
    """Manages user preferences for email filtering and task suggestions."""
    
    @staticmethod
    def get_preferences_path(user_id):
        """Get the path to the user's preferences file."""
        return os.path.join(TOKENS_DIR, f"{user_id}_preferences.json")
    
    @staticmethod
    def save_preferences(user_id, preferences):
        """Save user preferences to a file."""
        preferences_path = UserPreferences.get_preferences_path(user_id)
        with open(preferences_path, 'w') as f:
            json.dump(preferences, f)
    
    @staticmethod
    def load_preferences(user_id):
        """Load user preferences from a file."""
        preferences_path = UserPreferences.get_preferences_path(user_id)
        if not os.path.exists(preferences_path):
            # Default preferences
            return {
                "interests": [],
                "enabled": True
            }
        with open(preferences_path, 'r') as f:
            return json.load(f)
    
    @staticmethod
    def update_preferences(user_id, new_preferences):
        """Update existing user preferences."""
        current_preferences = UserPreferences.load_preferences(user_id)
        current_preferences.update(new_preferences)
        UserPreferences.save_preferences(user_id, current_preferences)
        return current_preferences 