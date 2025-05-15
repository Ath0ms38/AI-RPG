from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
from web.game.session import GameSession
from web.game.helpers import process_character_creation, process_observation, process_ai_response

router = APIRouter()

game_sessions = {}

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()

    if session_id not in game_sessions:
        # Try to load session from story file
        import os
        import json
        from web.user_management import USERS_DIR
        from web.game.session import GameSession
        for user_file in os.listdir(USERS_DIR):
            if user_file.endswith(".json"):
                username = user_file[:-5]
                user_dir = os.path.join(USERS_DIR, username)
                story_file = os.path.join(user_dir, f"{session_id}.json")
                if os.path.exists(story_file):
                    with open(story_file, "r") as f:
                        story_data = json.load(f)
                    # Reconstruct GameSession with character data if available
                    session = GameSession(session_id, username)
                    if "character" in story_data:
                        char = story_data["character"]
                        from web.rpg.Character import Character
                        if not isinstance(session.player_character, Character):
                            print("player_character is not a Character instance, resetting.")
                            session.player_character = Character()
                        session.player_character.name = char.get("name", "")
                        session.player_character.lore = char.get("lore", "")
                        session.player_character.health_and_mana = char.get("health", {})
                        session.player_character.level_and_experience = char.get("level", {})
                        session.player_character.equipment = char.get("equipment", {})
                        # Do NOT restore inventory directly; let Character class manage it
                        # session.player_character.inventory = char.get("inventory", "")
                        print("player_character type after restore:", type(session.player_character))
                    # Restore chat history if available
                    chat_history = story_data.get("chat_history", [])
                    from langchain.schema import HumanMessage, AIMessage, SystemMessage
                    restored_history = []
                    for msg in chat_history:
                        if isinstance(msg, dict):
                            role = msg.get("role", "").lower()
                            content = msg.get("content", "")
                            if role == "human":
                                restored_history.append(HumanMessage(content=content))
                            elif role == "system":
                                restored_history.append(SystemMessage(content=content))
                            elif "ai" in role:
                                restored_history.append(AIMessage(content=content))
                            elif role == "tool":
                                print(f"Tool message detected: {msg}")
                            else:
                                print(f"Skipping unknown message type: {msg}")
                        else:
                            print(f"Unexpected message format: {msg}")
                    if restored_history:
                        session.chat_history = restored_history
                    session.character_created = True
                    game_sessions[session_id] = session
                    break
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
            from langchain.schema import HumanMessage
            await websocket.send_text(json.dumps({
                "type": "user",
                "content": user_input
            }))

            session.chat_history.append(HumanMessage(content=user_input))
            session.save_session()

            observation_results = await process_observation(session)
            await websocket.send_text(json.dumps({
                "type": "observation",
                "content": observation_results
            }))

            await process_ai_response(websocket, session)
            session.save_session()
            await websocket.send_text(json.dumps({
                "type": "character_update",
                "data": session.get_character_data()
            }))

    except WebSocketDisconnect:
        print(f"Client disconnected: {session_id}")
    except Exception as e:
        print(f"Error: {e}")
        await websocket.close()
