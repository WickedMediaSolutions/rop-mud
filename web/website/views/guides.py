"""
Custom views for Rites of Passage - Home, Guides, Armory, Races & Classes, Map.
"""

from django.shortcuts import render
from django.db.models import Q
from evennia.objects.models import ObjectDB
from world.rules import RACES, CLASSES
from world.armor_sets import ArmorSetChecker


def home_view(request):
    """Landing page for Rites of Passage."""
    context = {"page_title": "Rites of Passage"}
    return render(request, "website/home.html", context)


def how_to_play_view(request):
    """How to Play guide page."""
    context = {"page_title": "How to Play"}
    return render(request, "website/how_to_play.html", context)


def new_players_view(request):
    """New Players guide page."""
    context = {"page_title": "New Players Guide"}
    return render(request, "website/new_players.html", context)


def races_view(request):
    """Races & Classes reference page."""
    context = {
        "page_title": "Races & Classes",
        "races": RACES,
        "classes": CLASSES,
        "good_races": [(k, v) for k, v in RACES.items() if v["alignment"] == "Good"],
        "evil_races": [(k, v) for k, v in RACES.items() if v["alignment"] == "Evil"],
    }
    return render(request, "website/races.html", context)


def armory_view(request):
    """
    Armory — searchable/sortable character roster.
    Queries Evennia's ObjectDB for characters with chargen_completed.
    """
    search_query = request.GET.get("q", "").strip()
    sort_by = request.GET.get("sort", "name")
    faction_filter = request.GET.get("faction", "")
    class_filter = request.GET.get("class", "")

    # Base: all characters that have a race attribute (finished chargen)
    chars = ObjectDB.objects.filter(
        db_typeclass_path__contains="characters.Character"
    )

    # We need to filter to only those with chargen completed.
    # Since we can't filter on attributes directly in SQL, we do it in Python
    # but limit by the character typeclass first.
    character_list = []
    for obj in chars:
        try:
            if not obj.attributes.has("race"):
                continue
            race = obj.attributes.get("race")
            if not race:
                continue
            cls = obj.attributes.get("character_class") or "Unknown"
            alignment = obj.attributes.get("alignment") or "Neutral"
            level = obj.attributes.get("level") or 1
            stats = obj.attributes.get("stats") or {}
            hp = obj.attributes.get("hp") or obj.attributes.get("max_hp") or 100
            max_hp = obj.attributes.get("max_hp") or 100
            mana = obj.attributes.get("mana") or obj.attributes.get("max_mana") or 50
            max_mana = obj.attributes.get("max_mana") or 50
            kills = obj.attributes.get("kills") or 0
            warpoints = obj.attributes.get("warpoints") or 0

            character_list.append({
                "id": obj.id,
                "name": obj.key,
                "race": race,
                "cls": cls,
                "alignment": alignment,
                "level": level,
                "hp": hp,
                "max_hp": max_hp,
                "mana": mana,
                "max_mana": max_mana,
                "kills": kills,
                "warpoints": warpoints,
                "stats": stats,
                "date_created": obj.db_date_created,
            })
        except Exception:
            continue

    # Apply filters
    if search_query:
        q = search_query.lower()
        character_list = [
            c for c in character_list
            if q in c["name"].lower() or q in c["race"].lower() or q in c["cls"].lower()
        ]
    if faction_filter:
        character_list = [c for c in character_list if c["alignment"].lower() == faction_filter.lower()]
    if class_filter:
        character_list = [c for c in character_list if c["cls"].lower() == class_filter.lower()]

    # Sort
    sort_map = {
        "name": lambda c: c["name"].lower(),
        "level": lambda c: -c["level"],
        "race": lambda c: c["race"].lower(),
        "class": lambda c: c["cls"].lower(),
        "kills": lambda c: -c["kills"],
        "warpoints": lambda c: -c["warpoints"],
        "hp": lambda c: -c["max_hp"],
    }
    key_fn = sort_map.get(sort_by, lambda c: c["name"].lower())
    character_list.sort(key=key_fn)

    total_chars = len(character_list)

    context = {
        "page_title": "Armory",
        "characters": character_list,
        "total_chars": total_chars,
        "search_query": search_query,
        "sort_by": sort_by,
        "faction_filter": faction_filter,
        "class_filter": class_filter,
        "all_classes": list(CLASSES.keys()),
    }
    return render(request, "website/armory.html", context)


def map_view(request):
    """World Map page."""
    context = {"page_title": "World Map"}
    return render(request, "website/map.html", context)
