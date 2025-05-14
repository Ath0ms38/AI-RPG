from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from web.config import templates
from web.routes.auth import get_username_from_session
from web.game.session import GameSession, CharacterUpdate

router = APIRouter()

game_sessions = {}

@router.get("/", response_class=HTMLResponse)
async def get_root(request: Request):
    username = get_username_from_session(request)
    if username:
        return RedirectResponse("/stories")
    return RedirectResponse("/login")

@router.get("/game/{story_id}", response_class=HTMLResponse)
async def game_page(request: Request, story_id: str):
    return templates.TemplateResponse("index.html", {"request": request, "story_id": story_id})

@router.get("/api/game-ready/{story_id}")
async def api_game_ready(story_id: str):
    return {"ready": True}

@router.post("/session")
async def create_session():
    import uuid
    session_id = str(uuid.uuid4())
    game_sessions[session_id] = GameSession(session_id)
    return {"session_id": session_id}

@router.get("/character/{session_id}")
async def get_character(session_id: str):
    if session_id in game_sessions:
        return game_sessions[session_id].get_character_data()
    # Try to load from story file
    import os
    import json
    from web.user_management import USERS_DIR
    for user_file in os.listdir(USERS_DIR):
        if user_file.endswith(".json"):
            username = user_file[:-5]
            user_dir = os.path.join(USERS_DIR, username)
            story_file = os.path.join(user_dir, f"{session_id}.json")
            if os.path.exists(story_file):
                with open(story_file, "r") as f:
                    story_data = json.load(f)
                if "character" in story_data:
                    return story_data["character"]
                else:
                    return {"error": "Character data not found in story file"}
    return {"error": "Session not found"}

@router.get("/story/{session_id}")
async def get_story_full(session_id: str):
    # Returns both character and chat_history for the session/story
    import os
    import json
    from web.user_management import USERS_DIR
    for user_file in os.listdir(USERS_DIR):
        if user_file.endswith(".json"):
            username = user_file[:-5]
            user_dir = os.path.join(USERS_DIR, username)
            story_file = os.path.join(user_dir, f"{session_id}.json")
            if os.path.exists(story_file):
                with open(story_file, "r") as f:
                    story_data = json.load(f)
                return {
                    "character": story_data.get("character"),
                    "chat_history": story_data.get("chat_history", [])
                }
    return {"error": "Session not found"}

@router.put("/character/{session_id}")
async def update_character(session_id: str, update: CharacterUpdate):
    if session_id not in game_sessions:
        return {"error": "Session not found"}
    return game_sessions[session_id].update_character(update)
