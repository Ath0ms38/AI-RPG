import json
import uuid
from langchain.schema import HumanMessage, AIMessage, SystemMessage
from langchain_core.messages.tool import ToolMessage

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
                    # Save tool call in descriptive format for frontend compatibility
                    tool_history_message = (
                        f"Tool AI called Tool {tool_call['name']} with arguments: {tool_call['args']} and got response:\n {tool_output}"
                    )
                    # Append required ToolMessage for OpenAI compatibility
                    session.chat_history.append(ToolMessage(
                        content=tool_output,
                        tool_call_id=tool_call.get('id', str(uuid.uuid4()))
                    ))
                    # Also append descriptive message for frontend
                    session.chat_history.append(AIMessage(content=tool_history_message))
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
