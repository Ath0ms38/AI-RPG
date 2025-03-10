import asyncio
import uuid
from termcolor import colored
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain_core.messages.tool import ToolMessage
from rpg.Character import Character

##########################
# Initialize Player
##########################
player_character = Character()


##########################
# Define Tools (with detailed docstrings)
##########################
@tool
def create_character(name: str, lore: str, level_and_experience: dict, health_and_mana: dict, equipment: dict) -> str:
    """Creates the player character with comprehensive attributes.

    Args:
        name: Full name of the character (2-5 words).
        lore: Brief backstory or description of the character.
        level_and_experience: Dictionary containing level and experience details.
            Required keys: level, experience, experience_to_next_level (values as integers).
        health_and_mana: Dictionary with current and maximum health/mana values.
            Required keys: current_health, max_health, current_mana, max_mana (values as integers).
        equipment: Dictionary specifying all equipped items in corresponding slots (head, chest, legs, feet, hands, main_hand, off_hand).
            Each slot should either be None or a dict with item fields:
            {
              "name": str,
              "description": str,
              "weight": float,
              "amount": int,
              "rarity": str
            }

    Returns:
        Confirmation message with created character details.
    """

    global player_character
    player_character.create_character(
        name=name,
        lore=lore,
        level_and_experience=level_and_experience,
        health_and_mana=health_and_mana,
        equipment=equipment
    )

    return f"""Character '{name}' created!
Lore: {lore}
Equipment Slots: {player_character.see_equipment()}
Starting Inventory: {player_character.see_inventory()}"""


@tool
def add_item(name: str, description: str, weight: float,
             amount: int = 1, rarity: str = "Common") -> str:
    """Adds an item to the player's inventory.

    Args:
        name: Item name (e.g., 'Health Potion')
        description: Physical description (1-2 sentences)
        weight: Weight in kilograms (0.1-50.0)
        amount: Quantity to add (1-10)
        rarity: Rarity level (Common, Uncommon, Rare, Epic, Legendary)

    Returns:
        Confirmation message with added item details
    """
    return player_character.add_item(name, description, weight, amount, rarity)


@tool
def equip_item(item_name: str, slot: str) -> str:
    """Equips an item from inventory to a specific slot.
    Call see_inventory to see available items. And use unequip_item to remove an item from a slot.

    Args:
        item_name: Exact name of item to equip
        slot: Body slot (head, chest, legs, feet, hands, main_hand, off_hand)

    Returns:
        Confirmation message or error if slot/item invalid
    """
    return player_character.equip(slot, item_name)


@tool
def unequip_item(slot: str) -> str:
    """Removes an item from an equipment slot.

    Args:
        slot: Body slot (head, chest, legs, feet, hands, main_hand, off_hand)

    Returns:
        Confirmation message or error if slot invalid
    """
    return player_character.unequip(slot)


@tool
def see_inventory_and_equipements() -> str:
    """Returns detailed list of all inventory items and equipment.

    Returns:
        Formatted string showing:
        - Carried items (name, quantity, weight)
        - Equipped items (slot: item name)
        - Total carried weight
    """
    inventory = player_character.see_inventory()
    equipped = player_character.see_equipment()
    return f"Inventory:\n{inventory}\nEquipment:\n{equipped}"


@tool
def see_equipment() -> str:
    """Returns currently equipped items in all slots"""
    return str(player_character.see_equipment())


@tool
def see_health() -> str:
    """Returns current health and mana status"""
    return str(player_character.see_health_and_mana())


@tool
def see_level() -> str:
    """Returns current level and experience progress"""
    return str(player_character.see_level_and_experience())


@tool
def see_inventory() -> str:
    """Returns detailed inventory contents"""
    return player_character.see_inventory()


@tool
def adjust_health(amount: int) -> str:
    """Modifies character's current health.

    Args:
        amount: Positive to heal, negative to damage
                Range: -50 to +50

    Returns:
        New health value and status warning if critical
    """
    player_character.health_and_mana['current_health'] += amount
    player_character.health_and_mana['current_health'] = max(
        0,
        min(player_character.health_and_mana['current_health'],
            player_character.health_and_mana['max_health'])
    )
    return f"Health: {player_character.health_and_mana['current_health']}/{player_character.health_and_mana['max_health']}"


@tool
def level_up() -> str:
    """Advances character to next level with benefits.

    Increases:
    - Level by 1
    - Max health by 10%
    - Max mana by 10%
    - Resets experience to 0
    - Doubles experience needed for next level

    Returns:
        Detailed level up report
    """
    pc = player_character
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
    return player_character.name

@tool
def see_lore() -> str:
    """Returns the character's lore"""
    return player_character.lore


# Tool groups
creation_tools = {"create_character": create_character}
action_tools = {
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
observation_tools = {
    "see_inventory": see_inventory,
    "see_equipment": see_equipment,
    "see_health": see_health,
    "see_level": see_level,
    "see_inventory_and_equipements": see_inventory_and_equipements,
    "see_name": see_name,
    "see_lore": see_lore
}

llm_main = ChatOpenAI(model_name="gpt-4o-mini", streaming=True).bind_tools(list(action_tools.values()))
llm_creation = ChatOpenAI(model_name="gpt-4o-mini", streaming=True).bind_tools(list(creation_tools.values()))
llm_observation = ChatOpenAI(model_name="gpt-4o-mini", streaming=True).bind_tools(list(observation_tools.values()))

##########################
# System Messages
##########################
creation_system = SystemMessage(content="""Always call create_character with ALL required parameters in ONE tool call.
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
YOU ARE OBLIGATED TO CREATE A CHARACTER, even if the user input doesn't make any sense.
""")

game_system = SystemMessage(content="""RPG Game Master Guidelines:
1. Use tools for inventory/character changes. When a character unequip an item, it is added to the inventory automatically
2. Describe consequences of tool actions
3. Maintain consistent fantasy setting
4. Track character status through tools
5. Challenge player with appropriate encounters
6. Reward creativity with items/experience
7. DO NOT CALL A TOOL IF THE OBSERVATION AI CALLED IT BEFORE.

All the rules are importants, don't break them !!!
""")

observation_system = SystemMessage(content="""Observation AI:
1. Monitor inventory/equipment changes
2. Track health changes
3. Verify tool actions
4. Only use see_inventory/etc. when needed
5. Get information about player character, for exemple see_name or see_lore
6. Never communicate directly with the player
""")

##########################
# Creation Phase
##########################
async def create_character_phase():
    global player_character
    print(colored("\nCHARACTER CREATION\n", "blue", attrs=["bold"]))
    print(colored("Describe your character (e.g., 'A grizzled dwarf warrior", "cyan"))
    print(colored("with a mysterious past and skill with axes'):\n", "cyan"))

    desc = input(colored("Your description: ", "yellow"))
    if desc.lower() in ["exit", "quit"]:
        raise SystemExit

    # Use non-streaming for more reliable completion
    response = await llm_creation.ainvoke([creation_system, HumanMessage(content=desc)])

    if response.tool_calls:
        for tool_call in response.tool_calls:
            print(colored(f"\nCharacter Creation: {tool_call['name']} {tool_call['args']}", "yellow"))
            tool_output = call_tool(tool_call['name'], tool_call['args'])
            print(colored(f"\nCharacter Creation: {tool_output}", "yellow"))
    return True


##########################
# Helper Functions
##########################
def call_tool(tool_name, tool_args):
    """Executes the specified tool with given arguments."""
    if tool_name in action_tools:
        try:
            return action_tools[tool_name].invoke(tool_args)
        except Exception as e:
            return f"Error executing {tool_name}: {e}"
    elif tool_name in creation_tools:
        try:
            return creation_tools[tool_name].invoke(tool_args)
        except Exception as e:
            return f"Error executing {tool_name}: {e}"
    return f"Unknown tool '{tool_name}'"


async def process_observation(chat_history):
    """Handles observation phase"""
    observation_history = [observation_system] + chat_history[-2:]
    gathered_msg = None
    async for chunk in llm_observation.astream(observation_history):
        if chunk.tool_calls:
            gathered_msg = chunk if not gathered_msg else gathered_msg + chunk

    if gathered_msg and gathered_msg.tool_calls:
        for tool_call in gathered_msg.tool_calls:
            tool_output = call_tool(tool_call['name'], tool_call['args'])
            history_message = f"Observation AI called to Tool {tool_call['name']} and got response:\n {tool_output}"
            print(colored(f"\nObservation: {tool_output}", "yellow"))
            chat_history.append(AIMessage(content=history_message))


async def process_response(chat_history):
    """Handles AI response and tool execution"""
    gathered_msg = None
    print(colored("\nAI: ", "green"), end="", flush=True)
    async for chunk in llm_main.astream(chat_history):
        if chunk.content:
            print(colored(chunk.content, "green"), end="", flush=True)
        gathered_msg = chunk if not gathered_msg else gathered_msg + chunk

    if gathered_msg:
        chat_history.append(gathered_msg)
        if gathered_msg.tool_calls:
            for tool_call in gathered_msg.tool_calls:
                tool_output = call_tool(tool_call['name'], tool_call['args'])
                print(colored(f"\nTool Result: {tool_output}", "magenta"))
                chat_history.append(
                    ToolMessage(
                        content=tool_output,
                        tool_call_id=tool_call.get('id', str(uuid.uuid4()))
                    )
                )
            # Recursively process any follow-up after tool usage
            await process_response(chat_history)


async def async_chat():
    response = await create_character_phase()
    chat_history = [game_system]
    print(colored("\nGAME STARTED!\n", "green", attrs=["bold"]))

    while True:
        user_input = input(colored("\nYour action: ", "cyan"))
        if user_input.lower() in ["exit", "quit"]:
            break

        chat_history.append(HumanMessage(content=user_input))
        await process_observation(chat_history)
        await process_response(chat_history)


##########################
# Main Game Execution
##########################
if __name__ == "__main__":
    asyncio.run(async_chat())
