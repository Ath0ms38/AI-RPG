import uuid
import json
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Dict, List, Optional, Any, Union
import asyncio

# Import from the RPG module
from rpg.Character import Character
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain_core.messages.tool import ToolMessage

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Store active game sessions
game_sessions = {}


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
        self.game_system = SystemMessage(content="""RPG Game Master Guidelines:
1. Use tools for inventory/character changes. When a character unequip an item, it is added to the inventory automatically you don't need to recreate it.
2. Describe consequences of tool actions
3. Maintain consistent fantasy setting
4. Track character status through tools
5. Challenge player with appropriate encounters
6. Reward creativity with items/experience
7. DO NOT CALL A TOOL IF THE OBSERVATION AI CALLED IT BEFORE.

All the rules are importants, don't break them !!!
""")

        self.creation_system = SystemMessage(content="""Always call create_character with ALL required parameters in ONE tool call.
Ensure the following fields are present:
- name (string, 2-5 words)
- lore (string describing the character)
- level_and_experience (dict: level, experience, experience_to_next_level)
- health_and_mana (dict: current_health, max_health, current_mana, max_mana)
- equipment (dict: head, chest, legs, feet, hands, main_hand, off_hand) 
  with each slot either None or an item dict: 
    { 
      "name": str, 
      "description": str, 
      "weight": float, 
      "amount": int, 
      "rarity": str
    }
MISSING ANY FIELD WILL CAUSE AN ERROR. Ensure all fields are included!
If a user doesn't provide a field, you can generate it yourself.
If a user doesn't give a description, you can generate it yourself randomly !!.
Unless the user provides a level, experience, or equipment make it beginner level.
YOU ARE OBLIGATED TO CREATE A CHARACTER, even if the user input doesn't make any sense.
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


@app.get("/", response_class=HTMLResponse)
async def get_root(request: Request):
    """Serve the main game page"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/session")
async def create_session():
    """Create a new game session"""
    session_id = str(uuid.uuid4())
    game_sessions[session_id] = GameSession(session_id)
    return {"session_id": session_id}


@app.get("/character/{session_id}")
async def get_character(session_id: str):
    """Get character data for a session"""
    if session_id not in game_sessions:
        return {"error": "Session not found"}

    return game_sessions[session_id].get_character_data()


@app.put("/character/{session_id}")
async def update_character(session_id: str, update: CharacterUpdate):
    """Update character attributes"""
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
        # For the web app, we'll wait for the user to send the character description first,
        # rather than prompting them directly (the UI will show a modal)
        if not session.character_created:
            # Wait for character description
            user_input = await websocket.receive_text()

            # Process creation phase
            await process_character_creation(websocket, session, user_input)

            # Send game started message
            await websocket.send_text(json.dumps({
                "type": "system",
                "content": "GAME STARTED!"
            }))

            # Send updated character data after creation
            await websocket.send_text(json.dumps({
                "type": "character_update",
                "data": session.get_character_data()
            }))

        # Main game loop
        while True:
            user_input = await websocket.receive_text()
            await websocket.send_text(json.dumps({
                "type": "user",
                "content": user_input
            }))

            session.chat_history.append(HumanMessage(content=user_input))

            # Process observation
            observation_results = await process_observation(session)
            # Always send observation data to keep UI consistent
            await websocket.send_text(json.dumps({
                "type": "observation",
                "content": observation_results
            }))

            # Process AI response
            await process_ai_response(websocket, session)

            # Send updated character data
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
    """Process character creation phase"""
    # Create a clean history just for character creation to avoid issues with tool messages
    creation_history = [session.creation_system, HumanMessage(content=user_input)]

    response = await session.llm_creation.ainvoke(creation_history)

    if response.tool_calls:
        for tool_call in response.tool_calls:
            await websocket.send_text(json.dumps({
                "type": "tool_call",
                "name": tool_call['name'],
                "args": tool_call['args']
            }))

            tool_output = session.call_tool(tool_call['name'], tool_call['args'])

            await websocket.send_text(json.dumps({
                "type": "tool_output",
                "content": tool_output
            }))

    # Now initialize the real chat history with just the system message
    # This avoids issues with tool messages without preceding tool calls
    session.chat_history = [session.game_system]


async def process_observation(session):
    """Process observation phase and return results"""
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

        # Always return at least an empty array so the frontend knows
        # an observation was processed, even if no tools were called
        return observation_results or []
    except Exception as e:
        print(f"Error in observation processing: {e}")
        # Return an empty array to avoid breaking the frontend
        return []


async def process_ai_response(websocket, session):
    """Process AI response and handle tool calls"""
    gathered_msg = None
    response_content = ""

    try:
        async for chunk in session.llm_main.astream(session.chat_history):
            if chunk.content:
                response_content += chunk.content
                await websocket.send_text(json.dumps({
                    "type": "ai_chunk",
                    "content": chunk.content
                }))

            gathered_msg = chunk if not gathered_msg else gathered_msg + chunk

        if gathered_msg:
            session.chat_history.append(gathered_msg)

            # Send complete AI message
            await websocket.send_text(json.dumps({
                "type": "ai_complete",
                "content": response_content
            }))

            # Process any tool calls
            if gathered_msg.tool_calls:
                for tool_call in gathered_msg.tool_calls:
                    await websocket.send_text(json.dumps({
                        "type": "tool_call",
                        "name": tool_call['name'],
                        "args": tool_call['args']
                    }))

                    tool_output = session.call_tool(tool_call['name'], tool_call['args'])

                    await websocket.send_text(json.dumps({
                        "type": "tool_output",
                        "content": tool_output
                    }))

                    # Add to chat history - make sure we have the proper structure
                    session.chat_history.append(ToolMessage(
                        content=tool_output,
                        tool_call_id=tool_call.get('id', str(uuid.uuid4()))
                    ))

                # Process any followup after tool usage
                await process_ai_response(websocket, session)
    except Exception as e:
        print(f"Error in AI response processing: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "content": f"Error processing response: {str(e)}"
        }))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)