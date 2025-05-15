import os
import json
import hashlib
from typing import Dict, List, Optional, Any, Union
import uuid
from datetime import datetime

# Path to the users directory
USERS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "users")

def ensure_user_directories():
    """Ensure the users directory exists"""
    if not os.path.exists(USERS_DIR):
        os.makedirs(USERS_DIR)


def hash_password(password: str) -> str:
    """Hash a password for storing"""
    return hashlib.sha256(password.encode()).hexdigest()


def register_user(username: str, password: str) -> Dict[str, Any]:
    """
    Register a new user
    
    Args:
        username: The username
        password: The password
        
    Returns:
        Dict with status and message
    """
    ensure_user_directories()
    
    # Check if username already exists
    user_file = os.path.join(USERS_DIR, f"{username.lower()}.json")
    if os.path.exists(user_file):
        return {"success": False, "message": "Username already exists"}
    
    # Create user data
    user_data = {
        "username": username,
        "password_hash": hash_password(password),
        "created_at": datetime.now().isoformat(),
        "stories": []
    }
    
    # Create user directory
    user_dir = os.path.join(USERS_DIR, username.lower())
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)
    
    # Save user data
    with open(user_file, "w") as f:
        json.dump(user_data, f, indent=2)
    
    return {"success": True, "message": "User registered successfully"}


def authenticate_user(username: str, password: str) -> Dict[str, Any]:
    """
    Authenticate a user
    
    Args:
        username: The username
        password: The password
        
    Returns:
        Dict with status and message
    """
    user_file = os.path.join(USERS_DIR, f"{username.lower()}.json")
    
    if not os.path.exists(user_file):
        return {"success": False, "message": "Invalid username or password"}
    
    try:
        with open(user_file, "r") as f:
            user_data = json.load(f)
        
        if user_data["password_hash"] == hash_password(password):
            return {"success": True, "message": "Login successful", "user_data": user_data}
        else:
            return {"success": False, "message": "Invalid username or password"}
    except Exception as e:
        return {"success": False, "message": f"Error during authentication: {str(e)}"}


def get_user_stories(username: str) -> List[Dict[str, Any]]:
    """
    Get all stories for a user, only returning those with an existing story file.
    """
    user_file = os.path.join(USERS_DIR, f"{username.lower()}.json")
    user_dir = os.path.join(USERS_DIR, username.lower())

    if not os.path.exists(user_file):
        return []

    try:
        with open(user_file, "r") as f:
            user_data = json.load(f)
        stories = user_data.get("stories", [])
        filtered_stories = []
        for story in stories:
            story_file = os.path.join(user_dir, f"{story['id']}.json")
            if os.path.exists(story_file):
                filtered_stories.append(story)
        return filtered_stories
    except Exception:
        return []


def create_story(username: str, world_description: str, character_description: str) -> Dict[str, Any]:
    """
    Create a new story for a user
    
    Args:
        username: The username
        world_description: Description of the game world
        character_description: Description of the player character
        
    Returns:
        Dict with status and story data
    """
    user_file = os.path.join(USERS_DIR, f"{username.lower()}.json")
    
    if not os.path.exists(user_file):
        return {"success": False, "message": "User not found"}
    
    try:
        # Generate a unique ID for the story
        story_id = str(uuid.uuid4())
        
        # Create story data
        story_data = {
            "id": story_id,
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "world_description": world_description,
            "character_description": character_description,
            "chat_history": []
        }
        
        # Create story directory if it doesn't exist
        user_dir = os.path.join(USERS_DIR, username.lower())
        if not os.path.exists(user_dir):
            os.makedirs(user_dir)
        
        # Save story data
        story_file = os.path.join(user_dir, f"{story_id}.json")
        with open(story_file, "w") as f:
            json.dump(story_data, f, indent=2)
        
        # Update user data with new story
        with open(user_file, "r") as f:
            user_data = json.load(f)
        
        user_data["stories"].append({
            "id": story_id,
            "created_at": story_data["created_at"],
            "last_updated": story_data["last_updated"],
            "world_description": world_description[:50] + "..." if len(world_description) > 50 else world_description
        })
        
        with open(user_file, "w") as f:
            json.dump(user_data, f, indent=2)
        
        return {"success": True, "message": "Story created successfully", "story_data": story_data}
    except Exception as e:
        return {"success": False, "message": f"Error creating story: {str(e)}"}


def get_story(username: str, story_id: str) -> Dict[str, Any]:
    """
    Get a specific story for a user
    
    Args:
        username: The username
        story_id: The story ID
        
    Returns:
        Dict with story data or error message
    """
    story_file = os.path.join(USERS_DIR, username.lower(), f"{story_id}.json")
    
    if not os.path.exists(story_file):
        return {"success": False, "message": "Story not found"}
    
    try:
        with open(story_file, "r") as f:
            story_data = json.load(f)
        
        return {"success": True, "story_data": story_data}
    except Exception as e:
        return {"success": False, "message": f"Error retrieving story: {str(e)}"}


def update_story(username: str, story_id: str, chat_history: List) -> Dict[str, Any]:
    """
    Update a story with new chat history
    
    Args:
        username: The username
        story_id: The story ID
        chat_history: The updated chat history
        
    Returns:
        Dict with status and message
    """
    story_file = os.path.join(USERS_DIR, username.lower(), f"{story_id}.json")
    
    if not os.path.exists(story_file):
        return {"success": False, "message": "Story not found"}
    
    try:
        with open(story_file, "r") as f:
            story_data = json.load(f)
        
        # Update chat history and last_updated
        story_data["chat_history"] = chat_history
        story_data["last_updated"] = datetime.now().isoformat()
        
        with open(story_file, "w") as f:
            json.dump(story_data, f, indent=2)
        
        # Also update the last_updated in the user's stories list
        user_file = os.path.join(USERS_DIR, f"{username.lower()}.json")
        with open(user_file, "r") as f:
            user_data = json.load(f)
        
        for story in user_data["stories"]:
            if story["id"] == story_id:
                story["last_updated"] = story_data["last_updated"]
                break
        
        with open(user_file, "w") as f:
            json.dump(user_data, f, indent=2)
        
        return {"success": True, "message": "Story updated successfully"}
    except Exception as e:
        return {"success": False, "message": f"Error updating story: {str(e)}"}
