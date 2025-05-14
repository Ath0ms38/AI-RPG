import uuid
import json
import os
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Form, Depends, Response, status, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, Any, Union
import asyncio

# Import from the RPG module
from rpg.Character import Character
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain_core.messages.tool import ToolMessage

# User management
from user_management import (
    register_user, authenticate_user, get_user_stories, create_story,
    get_story, update_story
)
import shutil

from dotenv import load_dotenv
load_dotenv()


app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="supersecretkey")

# CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Store active game sessions
game_sessions = {}

# --- Session helpers ---

def get_username_from_session(request: Request) -> Optional[str]:
    return request.session.get("username")

def require_auth(request: Request):
    username = get_username_from_session(request)
    if not username:
        raise Exception("Not authenticated")
    return username

# --- API ROUTES ---

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/stories", response_class=HTMLResponse)
async def stories_page(request: Request):
    username = get_username_from_session(request)
    if not username:
        return RedirectResponse("/login")
    return templates.TemplateResponse("stories.html", {"request": request, "username": username})

@app.post("/api/register")
async def api_register(data: dict):
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return {"success": False, "message": "Username and password required"}
    result = register_user(username, password)
    return result

@app.post("/api/login")
async def api_login(request: Request, data: dict):
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return {"success": False, "message": "Username and password required"}
    result = authenticate_user(username, password)
    if result.get("success"):
        request.session["username"] = username
    return result

@app.post("/api/logout")
async def api_logout(request: Request):
    request.session.clear()
    return {"success": True}

@app.get("/api/check-auth")
async def api_check_auth(request: Request):
    username = get_username_from_session(request)
    return {"authenticated": bool(username), "username": username}

@app.get("/api/stories")
async def api_get_stories(request: Request):
    username = get_username_from_session(request)
    if not username:
        return {"success": False, "message": "Not authenticated"}
    stories = get_user_stories(username)
    return {"success": True, "stories": stories}

@app.post("/api/stories")
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
    #    (simulate what the frontend would send as first message)
    creation_input = f"World Description:\n{world_description}\n\nCharacter Description:\n{character_description}"
    await process_character_creation(None, session, creation_input)

    # 4. Generate the first AI message (intro to the world)
    #    (simulate a "start" message from the user)
    session.chat_history.append(HumanMessage(content="Begin the adventure."))
    await process_ai_response(None, session, save_story_callback=lambda: update_story(username, story_id, session.chat_history))

    # 5. Save the session/chat history to the story file
    update_story(username, story_id, session.chat_history)

    return {"success": True, "story_id": story_id}

@app.delete("/api/stories/{story_id}")
async def api_delete_story(request: Request, story_id: str):
    username = get_username_from_session(request)
    if not username:
        return {"success": False, "message": "Not authenticated"}
    # Remove story file and update user JSON
    user_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "users", username.lower())
    story_file = os.path.join(user_dir, f"{story_id}.json")
    user_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "users", f"{username.lower()}.json")
    try:
        if os.path.exists(story_file):
            os.remove(story_file)
        # Remove from user JSON
        if os.path.exists(user_file):
            with open(user_file, "r") as f:
                user_data = json.load(f)
            user_data["stories"] = [s for s in user_data.get("stories", []) if s["id"] != story_id]
            with open(user_file, "w") as f:
                json.dump(user_data, f, indent=2)
        return {"success": True}
    except Exception as e:
        return {"success": False, "message": str(e)}

# --- GAME PAGE ROUTE AND GAME-READY ENDPOINT ---

@app.get("/game/{story_id}", response_class=HTMLResponse)
async def game_page(request: Request, story_id: str):
    # Serve the main game UI, passing story_id for frontend use
    return templates.TemplateResponse("index.html", {"request": request, "story_id": story_id})

@app.get("/api/game-ready/{story_id}")
async def api_game_ready(story_id: str):
    # Placeholder: always ready, can add logic to check session/story state
    return {"ready": True}

# --- RPG GAME LOGIC (existing) ---

class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    lore: Optional[str] = None

class GameSession:
    def __init__(self, session_id):
        self.session_id = session_id
        self.player_character = Character()
        self.chat_history = []

        # Set up tools and LLMs
        self.action_tools = self.setup_action_tools()
        self.creation_tools = self.setup_creation_tools()
        self.observation_tools = self.setup_observation_tools()

        self.llm_main = ChatOpenAI(model_name="gpt-4o-mini", streaming=True).bind_tools(
            list(self.action_tools.values()))
        self.llm_creation = ChatOpenAI(model_name="gpt-4o", streaming=True).bind_tools(
            list(self.creation_tools.values()))
        self.llm_observation = ChatOpenAI(model_name="gpt-4o-mini", streaming=True).bind_tools(
            list(self.observation_tools.values()))

        # Set up system messages
        self.game_system = SystemMessage(content="""RPG Game Master Guidelines

    Tool Usage for Inventory & Character Management
        Storage Types: All items must reside in either the character’s equipment or inventory.
        Add/Remove Items:
            Use add_item to place a new item into the inventory.
            Use remove_item to remove an item from the inventory. (This includes when a user uses or discards an item.)
        Equip/Unequip Items:
            Use equip_item to move an item from the inventory to the equipment slot.
            Use unequip_item to move an item from the equipment slot back into the inventory. (No need to recreate the item—unequipping automatically returns it to the inventory.)
        Equipment Restrictions: Only clothing, armor, tools, and weapons should be equipped. Other items remain in the inventory.

    Describe Consequences of Tool Actions
        Whenever you use a tool, narrate how that action impacts the character or the world (e.g., changes to stats, storyline progression).

    Maintain a Consistent Fantasy Setting
        Keep descriptions and events aligned with a cohesive fantasy world. Avoid modern or anachronistic references.

    Track Character Status Through Tools
        Ensure all tool actions accurately reflect character health, experience, abilities, and other relevant stats.

    Challenge the Player with Appropriate Encounters
        Provide enemies, puzzles, or scenarios suitable for the player’s level and progress.

    Reward Creativity with Items/Experience
        Recognize inventive actions by granting unique items, additional experience, or special narrative outcomes.

    Do Not Duplicate Tool Calls
        If the Observation AI has already invoked a particular tool for an event, do not call that same tool again.

    Speaking Style (Second-Person Observational)
        When narrating the world or describing in-game events, use second-person phrasing (e.g., “You step into the clearing and sense a shift in the air…”). This creates an immersive experience where the player feels actively involved.

    No Full Inventory Explanations
        The user can view their own inventory at any time, so do not provide a fully formatted inventory list in your narrative. If an item from the inventory is relevant to the current situation, mention only that specific item rather than reciting the entire inventory.
        
    Important: These rules are critical for a smooth, immersive RPG experience. Do not break them under any circumstances.""")

        self.creation_system = SystemMessage(content="""RPG Character Creation Guidelines

    Single Tool Call Requirement
        Always use exactly one create_character call to supply all required parameters. Splitting parameters across multiple calls is not allowed.

    Mandatory Fields
        name (string, 2-5 words)
        lore (string: a descriptive backstory for the character)
        level_and_experience (dict: must include level, experience, experience_to_next_level)
        health_and_mana (dict: must include current_health, max_health, current_mana, max_mana)
        equipment (dict): must include the following slots:
            head, chest, legs, feet, hands, main_hand, off_hand
            Each slot is either None or a dict representing an item with:

            {
              "name": str,
              "description": str,
              "weight": float,
              "amount": int,
              "rarity": str
            }

        Omitting any of these fields will cause an error, so be certain to include them all.

    Handling Missing Information
        If the user does not provide a specific field (e.g., lore, level), you must generate a value for it yourself.
        If no description is provided, you can create a random or placeholder description.
        If the user omits level, experience, or any equipment details, default to beginner-level attributes (low values and minimal gear).

    Obligation to Create a Character
        Even if the user input is incomplete, unclear, or nonsensical, you must still fulfill the request by providing a valid character with all required fields. There are no exceptions.

Important: All these rules must be followed exactly. Missing any required field, using multiple tool calls, or otherwise deviating from these guidelines will lead to errors.
""")

        self.observation_system = SystemMessage(content="""Observation AI:
1. Monitor inventory/equipment changes
2. Track health changes
3. Verify tool actions
4. Only use see_inventory/etc. when needed
5. Get information about player character, for exemple see_name or see_lore
6. Never communicate directly with the player
""")

        # Initialize chat history with the system message
        self.chat_history = [self.game_system]
        self.character_created = False

    def setup_action_tools(self):
        @tool
        def add_item(name: str, description: str, weight: float,
                     amount: int = 1, rarity: str = "Common") -> str:
            """Adds an item to the player's inventory."""
            return self.player_character.add_item(name, description, weight, amount, rarity)

        @tool
        def remove_item(name: str, amount: int = 1) -> str:
            """Removes an item from the player's inventory."""
            return self.player_character.remove_item(name, amount)

        @tool
        def equip_item(item_name: str, slot: str) -> str:
            """Equips an item from inventory to a specific slot."""
            return self.player_character.equip(slot, item_name)

        @tool
        def unequip_item(slot: str) -> str:
            """Removes an item from an equipment slot."""
            return self.player_character.unequip(slot)

        @tool
        def see_inventory_and_equipements() -> str:
            """Returns detailed list of all inventory items and equipment."""
            inventory = self.player_character.see_inventory()
            equipped = self.player_character.see_equipment()
            return f"Inventory:\n{inventory}\nEquipment:\n{equipped}"

        @tool
        def see_equipment() -> str:
            """Returns currently equipped items in all slots"""
            return str(self.player_character.see_equipment())

        @tool
        def see_health() -> str:
            """Returns current health and mana status"""
            return str(self.player_character.see_health_and_mana())

        @tool
        def see_level() -> str:
            """Returns current level and experience progress"""
            return str(self.player_character.see_level_and_experience())

        @tool
        def see_inventory() -> str:
            """Returns detailed inventory contents"""
            return self.player_character.see_inventory()

        @tool
        def adjust_health(amount: int) -> str:
            """Modifies character's current health."""
            self.player_character.health_and_mana['current_health'] += amount
            self.player_character.health_and_mana['current_health'] = max(
                0,
                min(self.player_character.health_and_mana['current_health'],
                    self.player_character.health_and_mana['max_health'])
            )
            return f"Health: {self.player_character.health_and_mana['current_health']}/{self.player_character.health_and_mana['max_health']}"

        @tool
        def level_up() -> str:
            """Advances character to next level with benefits."""
            pc = self.player_character
            pc.level_and_experience['level'] += 1
            pc.health_and_mana['max_health'] = int(pc.health_and_mana['max_health'] * 1.1)
            pc.health_and_mana['current_health'] = pc.health_and_mana['max_health']
            pc.health_and_mana['max_mana'] = int(pc.health_and_mana['max_mana'] * 1.1)
            pc.health_and_mana['current_mana'] = pc.health_and_mana['max_mana']
            pc.level_and_experience['experience'] = 0
            pc.level_and_experience['experience_to_next_level'] *= 2

            return f"""LEVEL UP! Now level {pc.level_and_experience['level']}.
Max Health: {pc.health_and_mana['max_health']}
Max Mana: {pc.health_and_mana['max_mana']}
Next Level Requires: {pc.level_and_experience['experience_to_next_level']} XP"""

        @tool
        def see_name() -> str:
            """Returns the character's name"""
            return self.player_character.name

        @tool
        def see_lore() -> str:
            """Returns the character's lore"""
            return self.player_character.lore

        return {
            "add_item": add_item,
            "remove_item": remove_item,
            "equip_item": equip_item,
            "unequip_item": unequip_item,
            "see_inventory": see_inventory,
            "adjust_health": adjust_health,
            "level_up": level_up,
            "see_inventory_and_equipements": see_inventory_and_equipements,
            "see_equipment": see_equipment,
            "see_health": see_health,
            "see_level": see_level,
            "see_name": see_name,
            "see_lore": see_lore
        }

    def setup_creation_tools(self):
        @tool
        def create_character(name: str, lore: str, level_and_experience: dict, health_and_mana: dict,
                             equipment: dict) -> str:
            """Creates the player character with comprehensive attributes."""
            self.player_character.create_character(
                name=name,
                lore=lore,
                level_and_experience=level_and_experience,
                health_and_mana=health_and_mana,
                equipment=equipment
            )
            self.character_created = True
            return f"""Character '{name}' created!
Lore: {lore}
Equipment Slots: {self.player_character.see_equipment()}
Starting Inventory: {self.player_character.see_inventory()}"""

        return {"create_character": create_character}

    def setup_observation_tools(self):
        # These tools are the same as some action tools but separated for observation use
        return {key: self.action_tools[key] for key in [
            "see_inventory",
            "see_equipment",
            "see_health",
            "see_level",
            "see_inventory_and_equipements",
            "see_name",
            "see_lore"
        ]}

    def call_tool(self, tool_name, tool_args):
        """Executes the specified tool with given arguments."""
        if tool_name in self.action_tools:
            try:
                return self.action_tools[tool_name].invoke(tool_args)
            except Exception as e:
                return f"Error executing {tool_name}: {e}"
        elif tool_name in self.creation_tools:
            try:
                return self.creation_tools[tool_name].invoke(tool_args)
            except Exception as e:
                return f"Error executing {tool_name}: {e}"
        return f"Unknown tool '{tool_name}'"

    def get_character_data(self):
        """Returns character data for the UI"""
        return {
            "name": self.player_character.name,
            "lore": self.player_character.lore,
            "health": self.player_character.see_health_and_mana(),
            "level": self.player_character.see_level_and_experience(),
            "equipment": self.player_character.see_equipment(),
            "inventory": self.player_character.see_inventory()
        }

    def update_character(self, update_data: CharacterUpdate):
        """Update character attributes"""
        if update_data.name:
            self.player_character.name = update_data.name
        if update_data.lore:
            self.player_character.lore = update_data.lore
        return self.get_character_data()

# --- Existing game endpoints (index, session, character, websocket) ---

@app.get("/", response_class=HTMLResponse)
async def get_root(request: Request):
    username = get_username_from_session(request)
    if username:
        return RedirectResponse("/stories")
    return RedirectResponse("/login")

@app.post("/session")
async def create_session():
    session_id = str(uuid.uuid4())
    game_sessions[session_id] = GameSession(session_id)
    return {"session_id": session_id}

@app.get("/character/{session_id}")
async def get_character(session_id: str):
    if session_id not in game_sessions:
        return {"error": "Session not found"}
    return game_sessions[session_id].get_character_data()

@app.put("/character/{session_id}")
async def update_character(session_id: str, update: CharacterUpdate):
    if session_id not in game_sessions:
        return {"error": "Session not found"}
    return game_sessions[session_id].update_character(update)

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()

    if session_id not in game_sessions:
        await websocket.send_text(json.dumps({"error": "Session not found"}))
        await websocket.close()
        return

    session = game_sessions[session_id]

    try:
        if not session.character_created:
            user_input = await websocket.receive_text()
            await process_character_creation(websocket, session, user_input)
            await websocket.send_text(json.dumps({
                "type": "system",
                "content": "GAME STARTED!"
            }))
            await websocket.send_text(json.dumps({
                "type": "character_update",
                "data": session.get_character_data()
            }))

        while True:
            user_input = await websocket.receive_text()
            await websocket.send_text(json.dumps({
                "type": "user",
                "content": user_input
            }))

            session.chat_history.append(HumanMessage(content=user_input))

            observation_results = await process_observation(session)
            await websocket.send_text(json.dumps({
                "type": "observation",
                "content": observation_results
            }))

            await process_ai_response(websocket, session)
            await websocket.send_text(json.dumps({
                "type": "character_update",
                "data": session.get_character_data()
            }))

    except WebSocketDisconnect:
        print(f"Client disconnected: {session_id}")
    except Exception as e:
        print(f"Error: {e}")
        await websocket.close()

async def process_character_creation(websocket, session, user_input):
    creation_history = [session.creation_system, HumanMessage(content=user_input)]
    response = await session.llm_creation.ainvoke(creation_history)
    if response.tool_calls:
        for tool_call in response.tool_calls:
            if websocket:
                await websocket.send_text(json.dumps({
                    "type": "tool_call",
                    "name": tool_call['name'],
                    "args": tool_call['args']
                }))
            tool_output = session.call_tool(tool_call['name'], tool_call['args'])
            if websocket:
                await websocket.send_text(json.dumps({
                    "type": "tool_output",
                    "content": tool_output
                }))
    session.chat_history = [session.game_system]

async def process_observation(session):
    observation_history = [session.observation_system] + session.chat_history[-2:]
    gathered_msg = None
    try:
        async for chunk in session.llm_observation.astream(observation_history):
            if chunk.tool_calls:
                gathered_msg = chunk if not gathered_msg else gathered_msg + chunk
        if not gathered_msg or not gathered_msg.tool_calls:
            return None
        observation_results = []
        for tool_call in gathered_msg.tool_calls:
            tool_output = session.call_tool(tool_call['name'], tool_call['args'])
            observation_results.append({
                "tool": tool_call['name'],
                "output": tool_output
            })
            history_message = f"Observation AI called Tool {tool_call['name']} and got response:\n {tool_output}"
            session.chat_history.append(AIMessage(content=history_message))
        return observation_results or []
    except Exception as e:
        print(f"Error in observation processing: {e}")
        return []

async def process_ai_response(websocket, session, save_story_callback=None):
    gathered_msg = None
    response_content = ""
    try:
        async for chunk in session.llm_main.astream(session.chat_history):
            if chunk.content:
                response_content += chunk.content
                if websocket:
                    await websocket.send_text(json.dumps({
                        "type": "ai_chunk",
                        "content": chunk.content
                    }))
            gathered_msg = chunk if not gathered_msg else gathered_msg + chunk
        if gathered_msg:
            session.chat_history.append(gathered_msg)
            if websocket:
                await websocket.send_text(json.dumps({
                    "type": "ai_complete",
                    "content": response_content
                }))
            if gathered_msg.tool_calls:
                for tool_call in gathered_msg.tool_calls:
                    if websocket:
                        await websocket.send_text(json.dumps({
                            "type": "tool_call",
                            "name": tool_call['name'],
                            "args": tool_call['args']
                        }))
                    tool_output = session.call_tool(tool_call['name'], tool_call['args'])
                    if websocket:
                        await websocket.send_text(json.dumps({
                            "type": "tool_output",
                            "content": tool_output
                        }))
                    session.chat_history.append(ToolMessage(
                        content=tool_output,
                        tool_call_id=tool_call.get('id', str(uuid.uuid4()))
                    ))
                await process_ai_response(websocket, session, save_story_callback=save_story_callback)
            # Save story after AI message if callback provided
            if save_story_callback:
                save_story_callback()
    except Exception as e:
        print(f"Error in AI response processing: {e}")
        if websocket:
            await websocket.send_text(json.dumps({
                "type": "error",
                "content": f"Error processing response: {str(e)}"
            }))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
