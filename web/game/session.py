from pydantic import BaseModel
from typing import Optional

from web.rpg.Character import Character
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain_core.messages.tool import ToolMessage

class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    lore: Optional[str] = None

from web.utils.story_utils import update_story_with_character

class GameSession:
    def __init__(self, session_id, username):
        self.session_id = session_id
        self.username = username
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
        def see_mana() -> str:
            """Returns current mana status"""
            return str(self.player_character.see_mana())

        @tool
        def see_level() -> str:
            """Returns current level and experience progress"""
            return str(self.player_character.see_level_and_experience())

        @tool
        def see_experience() -> str:
            """Returns current experience and XP to next level"""
            return str(self.player_character.see_experience())

        @tool
        def adjust_mana(amount: int) -> str:
            """Modifies character's current mana."""
            return self.player_character.adjust_mana(amount)

        @tool
        def adjust_experience(amount: int) -> str:
            """Modifies character's experience points and handles level up if needed."""
            return self.player_character.adjust_experience(amount)

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
            "adjust_mana": adjust_mana,
            "adjust_experience": adjust_experience,
            "level_up": level_up,
            "see_inventory_and_equipements": see_inventory_and_equipements,
            "see_equipment": see_equipment,
            "see_health": see_health,
            "see_mana": see_mana,
            "see_level": see_level,
            "see_experience": see_experience,
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
            "see_mana",
            "see_level",
            "see_experience",
            "see_inventory_and_equipements",
            "see_name",
            "see_lore"
        ]}

    def call_tool(self, tool_name, tool_args):
        """Executes the specified tool with given arguments."""
        print(f"call_tool: {tool_name}, player_character type: {type(self.player_character)}")
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
        """Returns character data for the UI and saving (equipment as dict)."""
        return {
            "name": self.player_character.name,
            "lore": self.player_character.lore,
            "health": self.player_character.see_health_and_mana(),
            "level": self.player_character.see_level_and_experience(),
            "equipment": self.player_character.serialize_equipment(),
            "inventory": self.player_character.see_inventory()
        }

    def save_session(self):
        """Saves the current session data to the story file."""
        story_update = {
            "character": self.get_character_data(),
            "chat_history": [
                {"role": msg.type, "content": msg.content} for msg in self.chat_history
            ]
        }
        update_story_with_character(self.username, self.session_id, story_update)

    def update_character(self, update_data: CharacterUpdate):
        """Update character attributes and save session."""
        if update_data.name:
            self.player_character.name = update_data.name
        if update_data.lore:
            self.player_character.lore = update_data.lore
        self.save_session()
        return self.get_character_data()
