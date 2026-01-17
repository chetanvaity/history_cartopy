#!/usr/bin/env python3
"""
Generate placeholder 128x128 PNG icons for testing.
These are simple colored squares with text labels.
Replace with real icons later.
"""
from PIL import Image, ImageDraw, ImageFont
import os

# Icon definitions: name -> background color
ICONS = {
    'capital': '#8B0000',      # Dark red
    'city': '#4169E1',         # Royal blue
    'battle': '#FF4500',       # Orange red
    'infantry': '#228B22',     # Forest green
    'cavalry': '#DAA520',      # Goldenrod
    'canons': '#696969',       # Dim gray
    'treasure': '#FFD700',     # Gold
    'letter': '#DEB887',       # Burlywood
    'fort': '#8B4513',         # Saddle brown
    'hill-fort': '#A0522D',    # Sienna
}

def generate_icon(name, color, output_dir, size=128):
    """Generate a simple placeholder icon."""
    # Create transparent image
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw a filled circle
    margin = 8
    draw.ellipse([margin, margin, size-margin, size-margin], fill=color)

    # Draw border
    draw.ellipse([margin, margin, size-margin, size-margin], outline='white', width=3)

    # Add text label (abbreviated)
    label = name[:3].upper()
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
    except:
        font = ImageFont.load_default()

    # Center the text
    bbox = draw.textbbox((0, 0), label, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (size - text_width) // 2
    y = (size - text_height) // 2

    draw.text((x, y), label, fill='white', font=font)

    # Save
    output_path = os.path.join(output_dir, f"{name}.png")
    img.save(output_path, 'PNG')
    print(f"Created: {output_path}")

def main():
    output_dir = os.path.join(os.path.dirname(__file__),
                              '../data/iconsets/default')
    os.makedirs(output_dir, exist_ok=True)

    for name, color in ICONS.items():
        generate_icon(name, color, output_dir)

    print(f"\nGenerated {len(ICONS)} placeholder icons in {output_dir}")

if __name__ == '__main__':
    main()
