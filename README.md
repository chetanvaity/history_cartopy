# History Cartopy

Create beautiful historical maps from declarative YAML manifests with decorative tiled borders.

## Example Maps

| Sack of Hyderabad (1655) | Advance from Deccan (1658) | Tactical Agra (1658) |
|:------------------------:|:--------------------------:|:--------------------:|
| ![Sack of Hyderabad](sack-of-hyderabad-16535.png) | ![Advance from Deccan](advance-from-deccan-1658.png) | ![Tactical Agra](tactical-agra-1658.png) |

## Features

- Declarative YAML-based map configuration
- Support for territories, cities, campaigns (troop movements), and labels
- Tiled PNG border system with customizable styles
- 3:2 landscape aspect ratio for beautiful narrative maps
- High-resolution output (300 DPI)

## Installation

### Prerequisites

- Python 3.9 or higher
- GEOS library (required by Cartopy)

On Ubuntu/Debian:
```bash
sudo apt install libgeos-dev
```

On macOS:
```bash
brew install geos
```

### Install from source

```bash
git clone https://github.com/chetanvaity/history-cartopy.git
cd history-cartopy
pip install -e .
```

### Set up backgrounds

Download or create background images and set the environment variable:
```bash
export CARTOPY_USER_BACKGROUNDS=/path/to/history-cartopy/data/backgrounds
```

Add this to your shell profile (`~/.bashrc` or `~/.zshrc`) to make it permanent.


## Map Configuration

### Manifest Structure

Maps are defined in YAML manifests:

```yaml
metadata:
  title: "Map Title"
  year: 1655
  extent: [70, 85, 13, 23]  # [MinLon, MaxLon, MinLat, MaxLat]
  resolution: "dev"  # dev, low, med, high
  output: "output.png"
  dimensions: [3600, 2400]  # pixels (width × height) - must be 3:2 ratio
  border_style: "mughal"  # optional - references data/borders/mughal/

labels:
  capitals:
    - name: Hyderabad
  cities:
    - name: Aurangabad
  rivers:
    - name: "Krishna"
      coords: [79.2, 16.6]
      rotation: 10

campaigns:
  - path: ["Aurangabad", "Hyderabad"]
    style: "invasion"
    label_above: "Aurangzeb"

territories:
  - name: "Kingdom"
    file: "kingdom.geojson"
    style: "kingdom1"
    type: "edge-tint"
```

### Dimension Requirements

**Aspect Ratio:**
- Maps must maintain **3:2 landscape** aspect ratio (width:height = 1.5)
- Examples: 3000×2000, 3600×2400, 4800×3200

**Recommended Dimensions:**
- Divisible by 300 (DPI) for clean inch conversion
- Divisible by 200 (tile size) for complete patterns with no cropping
- **Ideal:** 3600×2400 (perfectly divisible by both)

**Default:** 3600×2400 pixels (12×8 inches at 300 DPI)

## Usage

```bash
# Render a map
history-map examples/war-of-succession.yaml

# Specify output filename
history-map examples/war-of-succession.yaml --output my-map.png

# Save without displaying (for SSH sessions or scripts)
history-map examples/war-of-succession.yaml --no-show

# Override resolution (dev, low, med, high)
history-map examples/war-of-succession.yaml --res high
```

## Directory Structure

```
history_cartopy/
├── src/history_cartopy/
│   ├── render_map.py       # Main entry point
│   ├── border_styles.py    # Border rendering
│   ├── core.py             # Core rendering functions
│   ├── styles.py           # Text and label styles
│   ├── campaign_styles.py  # Campaign arrow styles
│   ├── territory_styles.py # Territory rendering styles
│   └── stylemaps.py        # Style definitions
├── data/
│   ├── borders/            # Border tile styles
│   ├── backgrounds/        # Background images
│   ├── polygons/           # GeoJSON territory files
│   └── city-locations.yaml # Gazetteer
├── examples/               # Example manifests
└── tests/                  # Test utilities and manifests
```

## Creating Historical Maps

1. Define your map in a YAML manifest (see `examples/reference-manifest.yaml`)
2. Create or reuse GeoJSON files for territories
3. Design border tiles for historical period (optional)
4. Render the map: `history-map your-manifest.yaml`
5. Output: High-resolution PNG with exact dimensions

## License

MIT License - see [LICENSE](LICENSE) for details.
