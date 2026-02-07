---
name: essay-to-map
description: Generate a history_cartopy YAML manifest from a historical text essay or description. Use when the user provides historical text and wants to create a map from it.
argument-hint: "[text-file-path]"
allowed-tools: Read, Glob, Grep
---

# Essay-to-Map: Generate a Map Manifest from Historical Text

You are creating a YAML manifest for the `history_cartopy` map renderer. Your job is to read a historical essay or description and produce a well-crafted, cartographically sound manifest that tells the story visually.

## Step 1: Read the Input

Read the essay file provided as `$ARGUMENTS`. If no file path is given, ask the user for one.

Also read these project files for reference:
- `data/city-locations.yaml` — the gazetteer (only cities listed here can be used by name)
- `examples/__reference__/manifest.yaml` — full YAML schema reference

## Step 2: Analyze the Essay

Extract from the text:
- **Time period** — year(s), specific dates of movements
- **Key places** — capitals, cities, towns, battlefields, river crossings
- **Movements** — who marched where, in what order, with what outcome
- **Battles/events** — specific incidents at specific places
- **Territories/kingdoms** — political entities relevant to the story
- **Rivers and geography** — rivers mentioned as obstacles, boundaries, or routes

## Step 3: Make Cartographic Decisions

Follow these editorial guidelines carefully. The goal is a map that a reader can glance at and understand the narrative — not a database dump of every place mentioned.

### Choosing the Extent
- **Tight but contextual.** The extent should comfortably contain all the action with ~10-15% padding on each side. Don't show the whole subcontinent for a campaign that spans 200km.
- **Landscape orientation** — the renderer requires 3:2 aspect ratio.
- Extent format: `[west_lon, east_lon, south_lat, north_lat]`.

### Choosing Cities (and Levels)
- **Include only cities that matter to the narrative.** A city is worth including if:
  - It is a starting point, destination, or waypoint of a campaign
  - A significant event happened there (battle, siege, treaty)
  - It is a capital or seat of power relevant to the story
  - It provides geographic context (a well-known reference point)
- **Exclude** cities that are merely mentioned in passing or are far from the action.
  - Sometimes the narrative mentions places which are extremely close to each other, so on the map choose the more important city.
- **Levels:**
  - Level 1: Capitals, seats of power, the most important places in the story
  - Level 2: Significant cities — campaign waypoints, major battles
  - Level 3: Minor towns, small waypoints, secondary locations
  - Level 4: Modern reference cities (e.g., showing "Kolkata" for orientation) — use sparingly
- **Rule of thumb:** A map with 5-12 cities is usually right. More than 15 is almost certainly cluttered.
- **Check the gazetteer** (`data/city-locations.yaml`) — if a city isn't listed, you'll need to tell the user so they can add it or provide raw coordinates.

### Choosing Rivers
- Include rivers that are **mentioned in the text** as obstacles, routes, or landmarks.
- Include rivers that are **geographically prominent** within the extent (e.g., a major river crossing the map even if not mentioned).
- Use auto-placement (just `- name: "RiverName"`) unless you have reason to place manually.
- Typically 2-5 rivers is appropriate.

### Choosing Regions
- Use region labels for **large political/geographic areas** that orient the reader (e.g., "DECCAN", "BENGAL", "PERSIA").
- Only include if the map extent is large enough that regional context helps.
- Place them in visually empty areas of the map.

### Designing Campaigns (Arrows)
This is the heart of most military history maps. Get this right.

- **Segment long marches** into phases rather than one long arrow. Each segment can carry its own date label. This is clearer and prevents arrow overlap.
- **Use distinct styles** for different factions/commanders:
  - `invasion` (red) — primary attacking force
  - `invasion-orange` — secondary/allied force
  - `invasion-black` — imperial/defending force
  - `boring` (dashed) — raiders, secondary movements, supply routes
  - `retreat` (grey dash-dot) — retreating forces
- **Label the first segment** of each commander's march with `label_above: "Commander Name"`. Add dates as `label_below` is available and relevant.
- **Don't over-label** — not every segment needs both labels. The first and last segment of a campaign line are usually enough.
- **Curvature (`rad`):** Default 0.3 is usually fine. Use negative values to curve the other way when two arrows would otherwise overlap. Use 0.0 for very short segments.
- **Path options:** Prefer named cities from the gazetteer. Use raw `[lon, lat]` coordinates only for intermediate waypoints not worth labeling as cities.

### Choosing Events
- Mark **specific incidents** — battles, river crossings, sieges, treaties — that happened at a definite place and time.
- Format: `"Event Name (Date)"` e.g., `"Dharmat (Apr 15)"`
- Use `icon: "battle"` for military engagements.
- Use `location:` if the place is in the gazetteer; use `coords:` for unnamed locations.
- Don't duplicate information — if a city label already conveys the importance of a place, you don't always need an event marker too.

### Territories
- Only include if GeoJSON polygon files exist or if you flag to the user that they need to be created.
- Useful for showing the political landscape — empires, kingdoms, disputed zones.
- `edge-tint` is subtle and works well for most maps. `fuzzy-fill` for empires.

### General Principles
- **Less is more.** A clean map with 8 cities and 4 arrows tells a better story than a cluttered one with 20 cities and 12 arrows.
- **Visual hierarchy matters.** The main campaign should use `invasion` style. Secondary movements should be visually subordinate (`boring`, `retreat`).
- **Dates anchor the narrative.** Include dates on campaign segments so the reader can follow the chronology.

## Step 4: Generate the YAML

Produce a complete, valid manifest. Use this structure:

```yaml
# Brief description of what this map shows
metadata:
  title: "Evocative Title"
  year: YYYY
  extent: [west, east, south, north]
  resolution: "high-yellow"
  output: "descriptive-filename.png"
  dimensions: [3600, 2400]
  graticule: true
  scale_bar: true

labels:
  cities:
    - name: "City"
      level: N
    # ...

  rivers:
    - name: "River"
    # ...

  # regions: (if needed)

campaigns:
  - name: "Description"
    path: ["From", "To"]
    style: "invasion"
    label_above: "Commander"
    label_below: "Date"
  # ...

events:
  - text: "Event (Date)"
    location: "Place"
    icon: "battle"
  # ...

# territories: (if GeoJSON files are available)
```

## Step 5: Explain Your Decisions

After the YAML, briefly explain:
1. **What you included and why** — the narrative arc of the map
2. **What you deliberately excluded** — places/events from the text that didn't make the cut, and why
3. **Cities not in the gazetteer** — any places that need to be added to `data/city-locations.yaml` before the map will render. Provide coordinates if you can determine them.
4. **Missing assets** — any GeoJSON territory files that would need to be created
5. **Suggested refinements** — things the user might want to tweak after seeing the first render (e.g., manual offsets for crowded areas, additional campaign segments)
