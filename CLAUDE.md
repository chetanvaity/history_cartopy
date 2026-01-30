# Purpose

Create beautiful historical maps from declarative YAML manifests.
See [motivation](motivation.md).

# Philosophy

- The priority is on beautiful, printable maps - for history books.
- Keep the code modular and loosely coupled where possible.

# Structure

The input is a YAML file describing the desired map. It contains:
  - map extents, title, etc
  - cities to be labelled in the map
  - military movements - called campaigns
  - specific events

The backgrounds used are NaturalEarth provided images of the world.

## Anchor circle
- An imaginary circle around a city dot - where labels and campaign arrow endpoints are placed.

## Placement Manager
- Module to resolve candidate positions for labels, arrows, etc to get a visually pleasing decluttered map.

# Run

The python venv to use is ~/hcvenv/

```bash
source ~/hcvenv/bin/activate
history-map <manifest.yaml>          # Render a map
history-map --init                    # Download Natural Earth data
history-map <manifest.yaml> --res dev # Quick dev preview
```

# Key Modules

| Module | Purpose |
|--------|---------|
| `render_map.py` | Main entry point, 3-phase pipeline |
| `labels.py` | City/river/region label handling |
| `campaigns.py` | Military movement arrows |
| `placement.py` | Overlap resolution (greedy algorithm) |
| `anchor.py` | 8-position Imhof model around city dots |
| `events.py` | Battle/event markers |
| `territories.py` | GeoJSON polygon rendering |

# Pipeline

1. **Collect** - Generate multiple candidate positions for labels/arrows
2. **Resolve** - Greedy placement to avoid overlaps
3. **Render** - Draw everything at final positions

# Example Manifests

- `examples/__reference__/manifest.yaml` - Full feature reference
- `examples/sack-of-hyderabad-1655/` - Simple example
- `examples/war-of-succession-1/` - Complex multi-campaign

