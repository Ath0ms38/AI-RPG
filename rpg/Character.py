from rpg.inventory import Inventory, Item

class Character:
    def __init__(self):
        self.name = "Unnamed"
        self.lore = "No lore available."
        self.level_and_experience = {
            "level": 1,
            "experience": 0,
            "experience_to_next_level": 10,
        }
        self.health_and_mana = {
            "current_health": 10,
            "max_health": 10,
            "current_mana": 10,
            "max_mana": 10,
        }
        # We use the Item-based approach for equipment
        self.equipped = {
            "head": None,
            "chest": None,
            "legs": None,
            "feet": None,
            "hands": None,
            "main_hand": None,
            "off_hand": None,
        }
        self.inventory = Inventory()

    def create_character(self,
                         name: str,
                         lore: str,
                         level_and_experience: dict,
                         health_and_mana: dict,
                         equipment: dict):
        self.name = name
        self.lore = lore
        self.level_and_experience = level_and_experience
        self.health_and_mana = health_and_mana

        # Set up equipment using Items
        for slot in self.equipped:
            slot_data = equipment.get(slot)
            if slot_data is not None:
                # slot_data must be a dict describing the item
                self.equipped[slot] = Item(
                    name=slot_data["name"],
                    description=slot_data["description"],
                    weight=slot_data["weight"],
                    amount=slot_data.get("amount", 1),
                    rarity=slot_data.get("rarity", "Common")
                )
            else:
                self.equipped[slot] = None

    def equip(self, slot: str, item_name: str):
        """Move an item from inventory to a specific slot."""
        if slot not in self.equipped:
            return f"Invalid slot: {slot}, list of valid slots: {list(self.equipped.keys())}"

        # Check if item exists in inventory
        key = item_name.lower()
        if key not in self.inventory.items:
            return f"You don't have '{item_name}' in your inventory."

        # We'll remove one from inventory if available
        item_in_inv = self.inventory.items[key]
        if item_in_inv.amount < 1:
            return f"No more of '{item_name}' left in inventory."

        # Actually equip it
        self.equipped[slot] = Item(
            name=item_in_inv.name,
            description=item_in_inv.description,
            weight=item_in_inv.weight,
            amount=1,  # We only equip one
            rarity=item_in_inv.rarity
        )
        item_in_inv.amount -= 1

        # If the inventory item is depleted, remove it entirely
        if item_in_inv.amount <= 0:
            del self.inventory.items[key]

        return f"Equipped {item_name} in {slot} slot."

    def unequip(self, slot: str):
        """Unequip the item in a given slot, returning it to inventory."""
        if slot not in self.equipped:
            return f"Invalid slot: {slot}, list of valid slots: {list(self.equipped.keys())}"

        equipped_item = self.equipped[slot]
        if equipped_item is None:
            return f"There's no item equipped in {slot} slot."

        # Add back to inventory
        self.inventory.add_item(
            name=equipped_item.name,
            description=equipped_item.description,
            weight=equipped_item.weight,
            amount=equipped_item.amount,
            rarity=equipped_item.rarity
        )

        self.equipped[slot] = None
        return f"Unequipped {equipped_item.name} from {slot} slot."

    def see_equipment(self):
        """Returns a dictionary of slot -> item or None (display only)."""
        result = {}
        for slot, item_obj in self.equipped.items():
            if item_obj is None:
                result[slot] = None
            else:
                result[slot] = f"{item_obj.name} (x{item_obj.amount}, {item_obj.rarity})"
        return result

    def serialize_equipment(self):
        """Returns a dictionary of slot -> item dict or None (for saving)."""
        result = {}
        for slot, item_obj in self.equipped.items():
            if item_obj is None:
                result[slot] = None
            else:
                result[slot] = {
                    "name": item_obj.name,
                    "description": item_obj.description,
                    "weight": item_obj.weight,
                    "amount": item_obj.amount,
                    "rarity": item_obj.rarity
                }
        return result

    def see_health_and_mana(self):
        return self.health_and_mana

    def see_level_and_experience(self):
        return self.level_and_experience

    def see_inventory(self):
        return self.inventory.see_inventory()

    def add_item(self, name: str, description: str, weight: float, amount: int = 1, rarity: str = "Common"):
        return self.inventory.add_item(name, description, weight, amount, rarity)

    def remove_item(self, name: str, amount: int = 1):
        return self.inventory.remove_item(name, amount)
