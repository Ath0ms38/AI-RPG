import asyncio
import uuid
import pytest

from web.game.helpers import process_ai_response
from langchain_core.messages.tool import ToolMessage
from langchain.schema import AIMessage

class DummyWebSocket:
    def __init__(self):
        self.sent = []
    async def send_text(self, text):
        self.sent.append(text)

class DummySession:
    def __init__(self, tool_calls=None):
        self.chat_history = []
        self.llm_main = self
        self.tool_calls = tool_calls or []
        self.tool_outputs = {}
        self.calls = []
    async def astream(self, chat_history):
        # Simulate a single chunk with tool_calls
        class Chunk:
            def __init__(self, tool_calls):
                self.content = None
                self.tool_calls = tool_calls
        yield Chunk(self.tool_calls)
    def call_tool(self, name, args):
        self.calls.append((name, args))
        return self.tool_outputs.get(name, "output")

@pytest.mark.asyncio
async def test_process_ai_response_multiple_tool_calls():
    tool_calls = [
        {"name": "tool1", "args": {"x": 1}, "id": "id1"},
        {"name": "tool2", "args": {"y": 2}, "id": "id2"}
    ]
    session = DummySession(tool_calls=tool_calls)
    session.tool_outputs = {"tool1": "result1", "tool2": "result2"}
    websocket = DummyWebSocket()
    await process_ai_response(websocket, session)
    # Check that ToolMessages with correct ids are in chat_history
    tool_message_ids = [
        m.tool_call_id for m in session.chat_history if isinstance(m, ToolMessage)
    ]
    assert set(tool_message_ids) == {"id1", "id2"}
    # Check that tool outputs are correct
    tool_message_contents = [
        m.content for m in session.chat_history if isinstance(m, ToolMessage)
    ]
    assert "result1" in tool_message_contents
    assert "result2" in tool_message_contents
