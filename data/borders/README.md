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

