#!/usr/bin/env python3
"""
Generate test border tiles for the History Cartopy border system.

Creates 8 PNG tiles with simple patterns for testing:
- Horizontal tiles: 200×100 pixels (top/bottom edges)
- Vertical tiles: 100×200 pixels (left/right edges)
- Corner tiles: 100×100 pixels (corners)

Output: data/borders/test/
"""

import os
from PIL import Image, ImageDraw, ImageFont

# Tile dimensions
HORIZONTAL_TILE_SIZE = (200, 100)  # width × height
VERTICAL_TILE_SIZE = (100, 200)    # width × height
CORNER_TILE_SIZE = (100, 100)      # width × height

# Output directory
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '../data/borders/test')


def create_horizontal_tile(color, label, pattern='stripes'):
    """Create a horizontal tile (200×100) with pattern"""
    img = Image.new('RGBA', HORIZONTAL_TILE_SIZE, color)
    draw = ImageDraw.Draw(img)

    if pattern == 'stripes':
        # Draw horizontal stripes
        for i in range(0, 100, 20):
            draw.rectangle([0, i, 200, i+10], fill=(255, 255, 255, 100))

    # Add label for identification
    draw.text((100, 50), label, fill=(255, 255, 255, 200), anchor='mm')

    return img


def create_vertical_tile(color, label, pattern='stripes'):
    """Create a vertical tile (100×200) with pattern"""
    img = Image.new('RGBA', VERTICAL_TILE_SIZE, color)
    draw = ImageDraw.Draw(img)

    if pattern == 'stripes':
        # Draw vertical stripes
        for i in range(0, 100, 20):
            draw.rectangle([i, 0, i+10, 200], fill=(255, 255, 255, 100))

    # Add label for identification (rotated)
    draw.text((50, 100), label, fill=(255, 255, 255, 200), anchor='mm')

    return img


def create_corner_tile(color, label):
    """Create a corner tile (100×100) with distinctive pattern"""
    img = Image.new('RGBA', CORNER_TILE_SIZE, color)
    draw = ImageDraw.Draw(img)

    # Draw concentric rectangles
    for i in range(0, 50, 15):
        draw.rectangle([i, i, 100-i, 100-i], outline=(255, 255, 255, 150), width=2)

    # Add label for identification
    draw.text((50, 50), label, fill=(255, 255, 255, 220), anchor='mm')

    return img


def main():
    """Generate all 8 border tiles"""
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Generating test border tiles in: {OUTPUT_DIR}")

    # Generate horizontal tiles (top/bottom)
    top_tile = create_horizontal_tile((139, 69, 19, 255), 'TOP', 'stripes')  # Saddle brown
    top_tile.save(os.path.join(OUTPUT_DIR, 'top-horizontal-tile.png'))
    print("✓ Created top-horizontal-tile.png (200×100)")

    bottom_tile = create_horizontal_tile((160, 82, 45, 255), 'BOTTOM', 'stripes')  # Sienna
    bottom_tile.save(os.path.join(OUTPUT_DIR, 'bottom-horizontal-tile.png'))
    print("✓ Created bottom-horizontal-tile.png (200×100)")

    # Generate vertical tiles (left/right)
    left_tile = create_vertical_tile((218, 165, 32, 255), 'LEFT', 'stripes')  # Goldenrod
    left_tile.save(os.path.join(OUTPUT_DIR, 'left-vertical-tile.png'))
    print("✓ Created left-vertical-tile.png (100×200)")

    right_tile = create_vertical_tile((184, 134, 11, 255), 'RIGHT', 'stripes')  # Dark goldenrod
    right_tile.save(os.path.join(OUTPUT_DIR, 'right-vertical-tile.png'))
    print("✓ Created right-vertical-tile.png (100×200)")

    # Generate corner tiles (100×100)
    top_left_tile = create_corner_tile((178, 34, 34, 255), 'TL')  # Firebrick
    top_left_tile.save(os.path.join(OUTPUT_DIR, 'left-top-corner-tile.png'))
    print("✓ Created left-top-corner-tile.png (100×100)")

    top_right_tile = create_corner_tile((220, 20, 60, 255), 'TR')  # Crimson
    top_right_tile.save(os.path.join(OUTPUT_DIR, 'right-top-corner-tile.png'))
    print("✓ Created right-top-corner-tile.png (100×100)")

    bottom_left_tile = create_corner_tile((205, 92, 92, 255), 'BL')  # Indian red
    bottom_left_tile.save(os.path.join(OUTPUT_DIR, 'left-bottom-corner-tile.png'))
    print("✓ Created left-bottom-corner-tile.png (100×100)")

    bottom_right_tile = create_corner_tile((240, 128, 128, 255), 'BR')  # Light coral
    bottom_right_tile.save(os.path.join(OUTPUT_DIR, 'right-bottom-corner-tile.png'))
    print("✓ Created right-bottom-corner-tile.png (100×100)")

    print(f"\nAll 8 border tiles created successfully in: {OUTPUT_DIR}")
    print("\nTile dimensions:")
    print("  - Horizontal (top/bottom): 200×100 px")
    print("  - Vertical (left/right): 100×200 px")
    print("  - Corners: 100×100 px")


if __name__ == '__main__':
    main()
