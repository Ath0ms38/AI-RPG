from rpg.inventory import Inventory

class Character():
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

        self.stats = {
            "strengh": 10,
            "dexterity": 10,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 10,
            "charisma": 10,
        }

        self.inventory = Inventory()

        self.equipped = {
            "head": None,
            "chest": None,
            "legs": None,
            "feet": None,
            "hands": None,
            "main_hand": None,
            "off_hand": None,
        }

    def create_character(self,
                         name: str,
                         level_and_experience: dict,
                         health_and_mana: dict,
                         stats: dict,
                         equipped: dict):
        self.name = name
        self.level_and_experience = level_and_experience
        self.health_and_mana = health_and_mana
        self.stats = stats
        self.equipped = equipped




    def equip(self, slot: str, item: str):
        if slot in self.equipped:
            self.equipped[slot] = item
            return f"Equipped {item} in {slot} slot."
        else:
            return f"Invalid slot: {slot}, list of valid slots: {self.equipped.keys()}"

    def unequip(self, slot: str):
        if slot in self.equipped:
            self.equipped[slot] = None
            return f"Unequipped item from {slot} slot."
        else:
            return f"Invalid slot: {slot}, list of valid slots: {self.equipped.keys()}"

    def get_name(self):
        return self.name

    def get_lore(self):
        return self.lore


    def see_equipment(self):
        return self.equipped

    def see_stats(self):
        return self.stats

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

