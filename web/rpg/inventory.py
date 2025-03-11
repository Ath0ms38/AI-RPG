class Item:
    """
    Represents an RPG item with a name, description, amount, and rarity.
    """

    def __init__(self, name: str, description: str, weight: float, amount: int = 1, rarity: str = "Common"):
        self.name = name
        self.description = description
        self.weight = weight
        self.amount = amount
        self.rarity = rarity

    def __str__(self):
        return (
            f"{self.name} (x{self.amount}) totaling {self.weight*self.amount}kg - {self.rarity}\n"
            f"  {self.description}"
        )


class Inventory:
    """
    A more advanced inventory system that stores items by a case-insensitive key (name).
    """

    def __init__(self):
        self.items = {}
        self.max_weight=30

    def add_item(self, name: str, description: str, weight: float, amount: int = 1, rarity: str = "Common") -> str:
        """
        Adds an item to the player's inventory.

        If the item already exists, increases its amount instead.

        Args:
            name (str): The name of the item to add.
            description (str): A brief description of the item.
            weight (int): The weight of the item in kg. (not the total only the weight of one item)
            amount (int, optional): The number of items to add. Defaults to 1.
            rarity (str, optional): The rarity of the item (e.g., "Common", "Rare"). Defaults to "Common".

        Returns:
            str: A message confirming the item was added or updated.
        """
        key = name.lower()
        if key in self.items:
            self.items[key].amount += amount
            return f"Added {amount} more {name}(s). You now have {self.items[key].amount} in your inventory. Total weight: {self.items[key].weight*self.items[key].amount}kg"
        else:
            self.items[key] = Item(name, description, weight, amount, rarity)
            return (
                f"Added {name} to your inventory.\n"
                f"  - Description: {description}\n"
                f"  - Rarity: {rarity}\n"
                f"  - Amount: {amount}"
                f"  - Weight of 1 item: {weight}kg"
                f"  - Total weight: {weight*amount}kg"
            )

    def remove_item(self, name: str, amount: int = 1) -> str:
        """
        Removes an item (or a specified quantity) from the player's inventory.

        If the requested amount exceeds the current inventory, the item is fully removed.

        Args:
            name (str): The name of the item to remove.
            amount (int, optional): The number of items to remove. Defaults to 1.

        Returns:
            str: A message confirming the removal or indicating that the item was not found.
        """
        key = name.lower()
        if key not in self.items:
            return f"'{name}' is not in your inventory."

        item_obj = self.items[key]
        if amount >= item_obj.amount:
            del self.items[key]
            return f"Removed all {item_obj.name}(s). None left in your inventory."
        else:
            item_obj.amount -= amount
            return f"Removed {amount} {item_obj.name}(s). You have {item_obj.amount} left now. Total weight: {item_obj.weight*item_obj.amount}kg"

    def see_inventory(self) -> str:
        """
        Displays the current inventory of the player.

        Lists all items, their quantities, descriptions, and rarities.

        Returns:
            str: A formatted string representing the current inventory contents.
        """
        if not self.items:
            return "Your inventory is empty."

        lines = ["=== Your Inventory ==="]
        lines.append(f"Total weight: {sum(itm.weight*itm.amount for itm in self.items.values())}kg of {self.max_weight}kg max")
        for itm in self.items.values():
            lines.append(str(itm))
        return "\n".join(lines)
