from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
import os
import json
from web.config import templates
from web.user_management import (
    get_user_stories, create_story, update_story
)
from web.routes.auth import get_username_from_session
from web.game.session import GameSession
from web.game.helpers import process_character_creation, process_ai_response

router = APIRouter()

game_sessions = {}

@router.get("/stories", response_class=HTMLResponse)
async def stories_page(request: Request):
    username = get_username_from_session(request)
    if not username:
        return RedirectResponse("/login")
    return templates.TemplateResponse("stories.html", {"request": request, "username": username})

@router.get("/api/stories")
async def api_get_stories(request: Request):
    username = get_username_from_session(request)
    if not username:
        return {"success": False, "message": "Not authenticated"}
    stories = get_user_stories(username)
    return {"success": True, "stories": stories}

@router.post("/api/stories")
async def api_create_story(request: Request, data: dict):
    username = get_username_from_session(request)
    if not username:
        return {"success": False, "message": "Not authenticated"}
    world_description = data.get("world_description", "")
    character_description = data.get("character_description", "")
    # 1. Create story file and get story_id
    result = create_story(username, world_description, character_description)
    if not result.get("success"):
        return result
    story_id = result["story_data"]["id"]

    # 2. Create a game session for this story
    session = GameSession(story_id)
    game_sessions[story_id] = session

    # 3. Run character creation with both world and character description
    creation_input = f"World Description:\n{world_description}\n\nCharacter Description:\n{character_description}"
    await process_character_creation(None, session, creation_input)

    # 4. Generate the first AI message (intro to the world)
    from langchain.schema import HumanMessage, AIMessage, SystemMessage, BaseMessage

    # Compose a full summary for the first user message
    character_data = session.get_character_data()
    summary = (
        f"World Description:\n{world_description}\n\n"
        f"Character Description:\n{character_description}\n\n"
        f"Lore:\n{character_data['lore']}\n" if character_data and character_data.get("lore") else ""
    )
    session.chat_history.append(HumanMessage(content=summary + "Begin the adventure."))
    await process_ai_response(None, session, save_story_callback=None)

    # Serialize chat_history for saving
    def serialize_message(msg):
        if hasattr(msg, "type"):
            role = msg.type
        elif hasattr(msg, "__class__"):
            role = msg.__class__.__name__
        else:
            role = "unknown"
        content = getattr(msg, "content", None)
        if content is None and isinstance(msg, dict):
            content = msg.get("content")
        return {"role": role, "content": content}

    serializable_history = [serialize_message(m) for m in session.chat_history]
    character_data = session.get_character_data()

    # Save both character data and chat history to the story file
    story_update = {
        "character": character_data,
        "chat_history": serializable_history
    }
    # Use a new update_story_with_character function for this structure
    from web.user_management import update_story as legacy_update_story
    def update_story_with_character(username, story_id, story_update):
        import os
        import json
        from web.user_management import USERS_DIR
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

    update_story_with_character(username, story_id, story_update)

    return {"success": True, "story_id": story_id}

@router.delete("/api/stories/{story_id}")
async def api_delete_story(request: Request, story_id: str):
    print(f"DELETE /api/stories/{story_id} called")
    username = get_username_from_session(request)
    if not username:
        print("Not authenticated")
        return {"success": False, "message": "Not authenticated"}
    # Remove story file and update user JSON
    from web.user_management import USERS_DIR
    user_dir = os.path.join(USERS_DIR, username.lower())
    story_file = os.path.join(user_dir, f"{story_id}.json")
    user_file = os.path.join(USERS_DIR, f"{username.lower()}.json")
    print(f"user_dir: {user_dir}")
    print(f"story_file: {story_file}")
    print(f"user_file: {user_file}")
    try:
        if os.path.exists(story_file):
            os.remove(story_file)
            print("Story file removed")
        else:
            print("Story file does not exist")
        # Remove from user JSON
        if os.path.exists(user_file):
            with open(user_file, "r") as f:
                user_data = json.load(f)
            user_data["stories"] = [s for s in user_data.get("stories", []) if s["id"] != story_id]
            with open(user_file, "w") as f:
                json.dump(user_data, f, indent=2)
            print("Story removed from user JSON")
        else:
            print("User file does not exist")
        print("Story deleted successfully")
        return {"success": True}
    except Exception as e:
        print(f"Error deleting story: {e}")
        return {"success": False, "message": str(e)}
