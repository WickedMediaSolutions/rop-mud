"""
Branching NPC Dialogue System for 'rop'

Provides:
  - DialogueNode: A single node in a dialogue tree (NPC text + player choices)
  - DialogueTree: A full branching conversation with conditions and effects
  - DialogueRegistry: Central registry of all dialogue trees
  - DialogueSession: Per-player active dialogue state

Usage:
  from world.quest_dialogue import DialogueNode, DialogueTree, dialogue_registry

  tree = DialogueTree(
      id="guard_intro",
      npc_key="Town Guard",
      start_node="greeting",
  )
  tree.add_node(DialogueNode(
      id="greeting",
      text="Hail, adventurer! What brings you here?",
      choices=[
          ("I seek quests.", "quests"),
          ("Tell me about this town.", "town_info"),
          ("Goodbye.", None),  # None = end conversation
      ],
  ))
  dialogue_registry.register(tree)
"""


class DialogueNode:
    """
    A single node in a dialogue tree.

    Attributes:
        id: Unique node identifier within the tree.
        text: The NPC's dialogue text for this node.
        choices: List of (choice_text, next_node_id) tuples.
                 next_node_id of None means end conversation.
        conditions: Optional dict of conditions to show this node.
                    e.g. {"quest_completed": "good_wolf_hunt", "min_level": 5}
        effects: Optional dict of effects when this node is reached.
                 e.g. {"give_quest": "good_wolf_hunt", "set_flag": "met_guard"}
        on_enter: Optional callable(node, session) called when node is entered.
    """

    def __init__(self, id, text, choices=None, conditions=None, effects=None,
                 on_enter=None):
        self.id = id
        self.text = text
        self.choices = choices or []
        self.conditions = conditions or {}
        self.effects = effects or {}
        self.on_enter = on_enter

    def evaluate_conditions(self, character):
        """
        Check if all conditions for this node are met for the given character.

        Supported conditions:
          - quest_completed: quest_id must be in completed quests
          - quest_active: quest_id must be active
          - quest_not_completed: quest_id must NOT be completed
          - min_level: character level >= value
          - max_level: character level <= value
          - has_item: item_key must be in character's inventory
          - faction: minimum faction_points required
          - flag: character must have the named dialogue flag set
          - not_flag: character must NOT have the named dialogue flag set
        """
        from world.quests import quest_registry

        for key, value in self.conditions.items():
            if key == "quest_completed":
                if not character.quests.has_completed(value):
                    return False
            elif key == "quest_active":
                if not character.quests.is_active(value):
                    return False
            elif key == "quest_not_completed":
                if character.quests.has_completed(value):
                    return False
            elif key == "min_level":
                level = character.attributes.get("level", default=1)
                if level < value:
                    return False
            elif key == "max_level":
                level = character.attributes.get("level", default=1)
                if level > value:
                    return False
            elif key == "has_item":
                found = False
                for obj in character.contents:
                    if obj.key.lower() == value.lower():
                        found = True
                        break
                if not found:
                    return False
            elif key == "faction":
                fp = character.attributes.get("faction_points", default=0)
                if fp < value:
                    return False
            elif key == "flag":
                flags = character.attributes.get("dialogue_flags", default=[])
                if not isinstance(flags, list):
                    flags = []
                if value not in flags:
                    return False
            elif key == "not_flag":
                flags = character.attributes.get("dialogue_flags", default=[])
                if not isinstance(flags, list):
                    flags = []
                if value in flags:
                    return False
        return True

    def apply_effects(self, character):
        """
        Apply all effects for this node to the given character.

        Supported effects:
          - give_quest: quest_id to offer/auto-accept
          - set_flag: dialogue flag name to set
          - clear_flag: dialogue flag name to clear
          - give_item: item_key to create and give
          - give_xp: XP amount to award
          - give_gold: gold amount to award
          - faction: faction points to add
        """
        from world.quests import quest_registry
        from evennia.objects.objects import DefaultObject

        for key, value in self.effects.items():
            if key == "give_quest":
                # Auto-accept the quest if not already active/completed
                qdef = quest_registry.get(value)
                if qdef and not character.quests.is_active(value):
                    if not character.quests.has_completed(value) or qdef.repeatable:
                        character.quests.accept(value)
            elif key == "set_flag":
                flags = character.attributes.get("dialogue_flags", default=[])
                if not isinstance(flags, list):
                    flags = []
                if value not in flags:
                    flags.append(value)
                character.attributes.add("dialogue_flags", flags)
            elif key == "clear_flag":
                flags = character.attributes.get("dialogue_flags", default=[])
                if not isinstance(flags, list):
                    flags = []
                if value in flags:
                    flags.remove(value)
                character.attributes.add("dialogue_flags", flags)
            elif key == "give_item":
                try:
                    new_item = DefaultObject.create(key=value)
                    new_item.location = character
                    character.msg(f"|gYou receive: {value}|n")
                except Exception:
                    pass
            elif key == "give_xp":
                character.award_xp(value)
                character.msg(f"|y+{value} XP|n")
            elif key == "give_gold":
                current = character.attributes.get("gold", default=0)
                character.attributes.add("gold", current + value)
                character.msg(f"|y+{value} Gold|n")
            elif key == "faction":
                fp = character.attributes.get("faction_points", default=0)
                character.attributes.add("faction_points", fp + value)


class DialogueTree:
    """
    A full branching dialogue tree for an NPC.

    Attributes:
        id: Unique tree identifier.
        npc_key: The NPC key this tree belongs to.
        start_node: The ID of the first node.
        nodes: Dict of node_id -> DialogueNode.
        repeatable: Whether the tree can be restarted after completion.
    """

    def __init__(self, id, npc_key, start_node="start", repeatable=True):
        self.id = id
        self.npc_key = npc_key
        self.start_node = start_node
        self.nodes = {}
        self.repeatable = repeatable

    def add_node(self, node):
        """Add a DialogueNode to this tree."""
        self.nodes[node.id] = node

    def get_node(self, node_id):
        """Get a node by ID, or None."""
        return self.nodes.get(node_id)

    def get_start_node(self, character):
        """
        Get the starting node for a character, evaluating conditions.
        Returns the first node whose conditions are met, or the default start_node.
        """
        # Try the default start node first
        start = self.nodes.get(self.start_node)
        if start and start.evaluate_conditions(character):
            return start

        # If start node conditions fail, try to find an alternate entry
        for node in self.nodes.values():
            if node.evaluate_conditions(character):
                return node

        return None

    def get_available_choices(self, node, character):
        """
        Return list of (choice_text, next_node) tuples that are valid
        for the character (next node conditions are met, or next_node is None).
        """
        available = []
        for choice_text, next_id in node.choices:
            if next_id is None:
                available.append((choice_text, None))
            else:
                next_node = self.nodes.get(next_id)
                if next_node and next_node.evaluate_conditions(character):
                    available.append((choice_text, next_node))
        return available


class DialogueRegistry:
    """Central registry of all dialogue trees."""

    def __init__(self):
        self._trees = {}  # id -> DialogueTree

    def register(self, tree):
        """Register a DialogueTree."""
        if not isinstance(tree, DialogueTree):
            raise TypeError("Must register a DialogueTree instance")
        self._trees[tree.id] = tree

    def get(self, tree_id):
        """Get a tree by ID."""
        return self._trees.get(tree_id)

    def get_by_npc(self, npc_key):
        """Get all dialogue trees for a given NPC key."""
        return [
            t for t in self._trees.values()
            if t.npc_key.lower() == npc_key.lower()
        ]

    def all(self):
        """Return all registered trees."""
        return list(self._trees.values())

    def clear(self):
        """Remove all trees."""
        self._trees.clear()


# Global registry instance
dialogue_registry = DialogueRegistry()


class DialogueSession:
    """
    Per-player active dialogue session.

    Tracks which tree and node the player is currently on,
    and handles choice selection.
    """

    def __init__(self, character, tree, current_node=None):
        self.character = character
        self.tree = tree
        self.current_node = current_node or tree.get_start_node(character)
        self._ended = False

    @property
    def is_active(self):
        return not self._ended and self.current_node is not None

    def display(self):
        """Display the current dialogue node to the character."""
        if not self.current_node:
            self._ended = True
            self.character.msg("|yThe conversation ends.|n")
            return

        # Apply on-enter effects
        self.current_node.apply_effects(self.character)
        if self.current_node.on_enter:
            try:
                self.current_node.on_enter(self.current_node, self)
            except Exception:
                pass

        # Show NPC text
        npc_name = self.tree.npc_key
        self.character.msg(f"|c{npc_name} says:|n \"{self.current_node.text}\"")
        self.character.msg("")

        # Show available choices
        available = self.tree.get_available_choices(self.current_node, self.character)
        if not available:
            self._ended = True
            self.character.msg("|y(End of conversation)|n")
            return

        for i, (choice_text, _) in enumerate(available, 1):
            self.character.msg(f"  |w[{i}]|n {choice_text}")

        self.character.msg("")
        self.character.msg("|yType |wtalk <number>|y to choose, or |wtalk end|y to leave.|n")

    def choose(self, choice_index):
        """
        Select a choice by its 1-based index.

        Returns (True, message) or (False, error_message).
        """
        if not self.is_active:
            return False, "No active conversation."

        available = self.tree.get_available_choices(self.current_node, self.character)
        if choice_index < 1 or choice_index > len(available):
            return False, f"Invalid choice. Choose 1-{len(available)}."

        _, next_node = available[choice_index - 1]

        if next_node is None:
            self._ended = True
            self.current_node = None
            self.character.msg("|yYou end the conversation.|n")
            return True, "Conversation ended."

        self.current_node = next_node
        self.display()
        return True, ""

    def end(self):
        """Force-end the dialogue session."""
        self._ended = True
        self.current_node = None


# ---------------------------------------------------------------------------
# DEFAULT DIALOGUE TREES
# ---------------------------------------------------------------------------

def register_default_dialogues():
    """Register default dialogue trees for key NPCs."""
    dialogue_registry.clear()

    # --- Good Quartermaster ---
    qm_tree = DialogueTree(
        id="good_quartermaster",
        npc_key="Good Quartermaster",
        start_node="greeting",
    )

    qm_tree.add_node(DialogueNode(
        id="greeting",
        text="Well met, traveler! I'm the Quartermaster of Aethelgard. "
             "How can I help you today?",
        choices=[
            ("I'm looking for work.", "offer_quests"),
            ("What's happening in the realm?", "realm_news"),
            ("I've completed a task for you.", "turn_in"),
            ("Just passing through. Farewell.", None),
        ],
    ))

    qm_tree.add_node(DialogueNode(
        id="offer_quests",
        text="We always have work for capable adventurers. "
             "Check your quest journal for available tasks. "
             "Use |wquest list|n to see what I'm offering.",
        choices=[
            ("I'll take a look. Thanks!", None),
            ("Tell me about the realm first.", "realm_news"),
        ],
        effects={"set_flag": "talked_to_quartermaster"},
    ))

    qm_tree.add_node(DialogueNode(
        id="realm_news",
        text="Dark times, friend. The wolves grow bolder each day, "
             "and strange creatures lurk in the shadows. "
             "We need every sword arm we can get.",
        choices=[
            ("I'll help however I can.", "offer_quests"),
            ("I must be going.", None),
        ],
    ))

    qm_tree.add_node(DialogueNode(
        id="turn_in",
        text="Ah, you've been busy! Use |wquest complete <id>|n "
             "to turn in your completed tasks and claim your reward.",
        choices=[
            ("Will do!", None),
            ("What else do you have for me?", "offer_quests"),
        ],
    ))

    dialogue_registry.register(qm_tree)

    # --- Evil Quartermaster ---
    eqm_tree = DialogueTree(
        id="evil_quartermaster",
        npc_key="Evil Quartermaster",
        start_node="greeting",
    )

    eqm_tree.add_node(DialogueNode(
        id="greeting",
        text="*grunts* Another whelp looking for coin? "
             "What do you want?",
        choices=[
            ("I need work. What have you got?", "offer_quests"),
            ("Nothing. Forget it.", None),
        ],
    ))

    eqm_tree.add_node(DialogueNode(
        id="offer_quests",
        text="The rats in the tunnels need culling, and I need skulls. "
             "Check your journal with |wquest list|n. "
             "Don't waste my time.",
        choices=[
            ("I'm on it.", None),
            ("Maybe later.", None),
        ],
        effects={"set_flag": "talked_to_evil_qm"},
    ))

    dialogue_registry.register(eqm_tree)

    # --- Town Guard (branching example with conditions) ---
    guard_tree = DialogueTree(
        id="town_guard",
        npc_key="Town Guard",
        start_node="greeting",
    )

    guard_tree.add_node(DialogueNode(
        id="greeting",
        text="Halt! State your business, stranger.",
        choices=[
            ("I'm an adventurer seeking work.", "adventurer"),
            ("Just passing through.", "passing"),
            ("I've already helped your quartermaster.", "friendly"),
        ],
    ))

    guard_tree.add_node(DialogueNode(
        id="adventurer",
        text="Another one, eh? The Quartermaster is always looking "
             "for help. Head to the town square.",
        choices=[
            ("Thanks for the tip.", None),
        ],
        effects={"set_flag": "met_town_guard"},
    ))

    guard_tree.add_node(DialogueNode(
        id="passing",
        text="Keep your nose clean and we won't have problems. Move along.",
        choices=[
            ("*nod and move on*", None),
        ],
    ))

    guard_tree.add_node(DialogueNode(
        id="friendly",
        text="Ah, you're the one who's been helping out. "
             "Good to have you around. Carry on!",
        choices=[
            ("Good to be here.", None),
        ],
        conditions={"flag": "talked_to_quartermaster"},
    ))

    dialogue_registry.register(guard_tree)