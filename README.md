# History Cartopy

Create beautiful historical maps from declarative YAML manifests with decorative tiled borders.

## Example Maps

| Sack of Hyderabad (1655) | Advance from Deccan (1658) | Tactical Agra (1658) |
|:------------------------:|:--------------------------:|:--------------------:|
| ![Sack of Hyderabad](sack-of-hyderabad-1655.png) | ![Advance from Deccan](advance-from-deccan-1658.png) | ![Tactical Agra](tactical-agra-1658.png) |

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

## Border Tile Requirements

Maps can be decorated with tiled PNG borders. Border styles are created by placing 8 PNG files in a directory under `data/borders/<style-name>/`.

### Required Files

Each border style directory must contain these 8 PNG files:

1. **Edge Tiles** (repeat along edges):
   - `top-horizontal-tile.png` - 200×100 pixels (width × height)
   - `bottom-horizontal-tile.png` - 200×100 pixels
   - `left-vertical-tile.png` - 100×200 pixels
   - `right-vertical-tile.png` - 100×200 pixels

2. **Corner Tiles** (placed at corners, can "jut in" to map):
   - `left-top-corner-tile.png` - 300×300 pixels
   - `right-top-corner-tile.png` - 300×300 pixels
   - `left-bottom-corner-tile.png` - 300×300 pixels
   - `right-bottom-corner-tile.png` - 300×300 pixels

### Tile Specifications

**Edge Tiles:**
- Horizontal tiles (top/bottom): **200×100 pixels**
  - 200px width allows for elaborate repeating patterns (knots, arabesques, etc.)
  - 100px height defines the border width
  - Tiles repeat horizontally with no cropping (for 3000px map: 15 tiles; for 3600px: 18 tiles)

- Vertical tiles (left/right): **100×200 pixels**
  - 100px width defines the border width
  - 200px height allows for elaborate repeating patterns
  - Tiles repeat vertically with no cropping (for 2000px map: 10 tiles; for 2400px: 12 tiles)

**Corner Tiles:**
- **300×300 pixels** (3× the border width)
- Larger size allows for elaborate corner decorations
- Corners overlay the edges and can "jut into" the map area
- Should visually connect with the edge patterns

**File Format:**
- PNG format with RGBA support (transparency recommended)
- Alpha channel allows map to show through decorative elements
- Use colors and patterns appropriate to historical period

### Creating Border Styles

1. Create a directory: `data/borders/your-style-name/`
2. Add all 8 required PNG files with exact filenames and dimensions
3. Reference in manifest: `border_style: "your-style-name"`

Example directory structure:
```
data/borders/
├── mughal/
│   ├── left-vertical-tile.png
│   ├── right-vertical-tile.png
│   ├── top-horizontal-tile.png
│   ├── bottom-horizontal-tile.png
│   ├── left-top-corner-tile.png
│   ├── right-top-corner-tile.png
│   ├── left-bottom-corner-tile.png
│   └── right-bottom-corner-tile.png
└── maratha/
    └── [same 8 files]
```

### Design Considerations

**Pattern Repetition:**
- Horizontal patterns repeat 15 times on a 3000px wide map
- Vertical patterns repeat 10 times on a 2000px tall map
- Design patterns that look good when repeated (seamless edges)

**Border Width:**
- Standard border width is 100 pixels
- This is 1/30th of a 3000px map width
- Corners at 300px extend into the map for emphasis

**Historical Accuracy:**
- Mughal style: Islamic geometric patterns, arabesques, floral motifs
- Maratha style: Hindu geometric patterns, chevrons, temple-inspired designs
- Medieval Islamic: Interlaced patterns, calligraphy borders, star polygons

### Generating Test Tiles

A test tile generator is provided:

```bash
python3 tests/generate_test_borders.py
```

This creates simple colored test tiles in `data/borders/test/` for verifying the border system works correctly.

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
