import os
import json
from web.user_management import USERS_DIR

def update_story_with_character(username, story_id, story_update):
    """
    Updates the story file with character data and chat history.
    """
    story_file = os.path.join(USERS_DIR, username.lower(), f"{story_id}.json")
    print(f"Saving story to: {story_file}")
    print(f"Character data: {story_update.get('character')}")
    print(f"Chat history: {story_update.get('chat_history')}")
    if not os.path.exists(story_file):
        print("Story file does not exist at save time")
        return {"success": False, "message": "Story not found"}
    try:
        with open(story_file, "r") as f:
            story_data = json.load(f)
        # Update character and chat_history
        story_data["character"] = story_update.get("character")
        story_data["chat_history"] = story_update.get("chat_history")
        story_data["last_updated"] = story_data.get("last_updated")
        with open(story_file, "w") as f:
            json.dump(story_data, f, indent=2)
        print("Story file after save:", json.dumps(story_data, indent=2))
        return {"success": True, "message": "Story updated successfully"}
    except Exception as e:
        print(f"Error updating story: {e}")
        return {"success": False, "message": f"Error updating story: {str(e)}"}
