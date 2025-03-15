from flask import Blueprint, jsonify, session, redirect, request, render_template
from utils.auth import load_credentials, require_auth
from utils.models import UserPreferences

preferences_bp = Blueprint('preferences', __name__)

AVAILABLE_CATEGORIES = [
    "Internship", 
    "Hackathon", 
    "Cultural Events", 
    "Sports Events",
    "Academics",
    "Professional Development",
    "Research Opportunities",
    "Meetings",
    "Workshops",
    "Conferences",
    "Charity Events",
    "Volunteer Opportunities",
    "Clubs & Organizations",
    "Social Events"
]

@preferences_bp.route('/preferences')
@require_auth
def preferences_page():
    """Render the preferences page."""
    user_id = session.get('user_id')
    user_preferences = UserPreferences.load_preferences(user_id)
    
    return render_template('preferences.html', 
                          categories=AVAILABLE_CATEGORIES,
                          user_preferences=user_preferences)

@preferences_bp.route('/api/preferences', methods=['GET'])
@require_auth
def get_preferences():
    """Get user preferences."""
    user_id = session.get('user_id')
    try:
        preferences = UserPreferences.load_preferences(user_id)
        return jsonify(preferences)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@preferences_bp.route('/api/preferences', methods=['POST'])
@require_auth
def update_preferences():
    """Update user preferences."""
    user_id = session.get('user_id')
    try:
        data = request.json
        interests = data.get('interests', [])
        custom_interests = data.get('custom_interests', [])
        
        # Validate that all standard interests are in the available categories
        for interest in interests:
            if interest not in AVAILABLE_CATEGORIES and interest not in custom_interests:
                return jsonify({"error": f"Invalid interest: {interest}"}), 400
                
        # Combine standard and custom interests
        all_interests = interests + custom_interests
        
        preferences = {
            "interests": all_interests,
            "custom_interests": custom_interests,
            "enabled": data.get('enabled', True)
        }
        
        UserPreferences.update_preferences(user_id, preferences)
        return jsonify({"success": True, "preferences": preferences})
    except Exception as e:
        return jsonify({"error": str(e)}), 500 