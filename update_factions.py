import re

# Update Phase 1 Faction Titles
with open("world/builder_phase1.py", "r") as f:
    content = f.read()

content = content.replace("EVIL_TOWNS = [", "# --- THE GORGOROTH HORDE (EVIL) ---\nEVIL_TOWNS = [")
content = content.replace("GOOD_TOWNS = [", "# --- THE AETHELGARD ALLIANCE (GOOD) ---\nGOOD_TOWNS = [")

with open("world/builder_phase1.py", "w") as f:
    f.write(content)

# Update Phase 3 Mob & Faction Tags
with open("world/builder_phase3.py", "r") as f:
    p3_content = f.read()

p3_content = p3_content.replace('"evil"', '"Gorgoroth Horde"')
p3_content = p3_content.replace('"good"', '"Aethelgard Alliance"')

with open("world/builder_phase3.py", "w") as f:
    f.write(p3_content)

print("SUCCESS: Builder scripts updated with Gorgoroth Horde & Aethelgard Alliance!")
