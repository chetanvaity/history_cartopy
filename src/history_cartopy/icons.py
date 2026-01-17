"""
Icon rendering system for historical maps.

Loads 128x128 transparent PNG icons and renders them on the map
with proper scaling and anchor point positioning.

This module is a "dumb" renderer - it takes offsets as parameters.
Placement logic (anchor circles) is handled by core.py.
"""
import os
from PIL import Image
import numpy as np
from matplotlib.transforms import offset_copy
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import cartopy.crs as ccrs

# Icon cache to avoid reloading
_icon_cache = {}

# Default icon size in points (72 points = 1 inch)
ICON_SIZE_PT = 14

# Default iconset path (relative to data directory)
DEFAULT_ICONSET = 'iconsets/default'

# Auto-assigned icons for location types
AUTO_ICONS = {
    'capital': 'capital',
    'city': 'city',
}


def load_icon(icon_name, iconset_path):
    """
    Load a PNG icon from the iconset directory.

    Args:
        icon_name: Name of the icon (without .png extension)
        iconset_path: Full path to the iconset directory

    Returns:
        PIL Image object (RGBA) or None if not found
    """
    cache_key = f"{iconset_path}/{icon_name}"
    if cache_key in _icon_cache:
        return _icon_cache[cache_key]

    icon_path = os.path.join(iconset_path, f"{icon_name}.png")
    if not os.path.exists(icon_path):
        print(f"Warning: Icon '{icon_name}' not found at {icon_path}")
        return None

    img = Image.open(icon_path).convert('RGBA')

    # Verify it's 128x128
    if img.size != (128, 128):
        print(f"Warning: Icon '{icon_name}' is {img.size}, expected (128, 128)")

    _icon_cache[cache_key] = img
    return img


def render_icon(ax, lon, lat, icon_name, iconset_path,
                x_offset=0, y_offset=0, size_pt=None, zorder=7, centered=False):
    """
    Render an icon on the map at a specific location.

    The icon's bottom-center is placed at the anchor point (after offset),
    unless centered=True, in which case the icon center is at the anchor.

    Args:
        ax: Matplotlib axes (with cartopy projection)
        lon, lat: Geographic coordinates
        icon_name: Name of the icon file (without .png)
        iconset_path: Full path to iconset directory
        x_offset: Horizontal offset in points
        y_offset: Vertical offset in points
        size_pt: Icon size in points (default: ICON_SIZE_PT)
        zorder: Drawing order (default: 7, above city dots)
        centered: If True, center icon on anchor point (default: False)

    Returns:
        AnnotationBbox object or None if icon not found
    """
    img = load_icon(icon_name, iconset_path)
    if img is None:
        return None

    if size_pt is None:
        size_pt = ICON_SIZE_PT

    # Convert PIL image to numpy array for matplotlib
    img_array = np.array(img)

    # Calculate zoom factor to achieve desired size in points
    # OffsetImage zoom is relative to the image's pixel size
    # We want the icon to appear as size_pt points tall
    dpi = ax.figure.dpi
    target_pixels = size_pt * dpi / 72  # Convert points to pixels at current DPI
    zoom = target_pixels / img.size[1]  # Scale based on height

    # Create the offset image
    imagebox = OffsetImage(img_array, zoom=zoom)
    imagebox.image.axes = ax

    # Get the geodetic transform for lon/lat coordinates
    geodetic = ccrs.PlateCarree()._as_mpl_transform(ax)

    # AnnotationBbox places the image
    # - xy=(lon,lat) is the anchor point in geodetic coords
    # - xybox=(x_offset, y_offset) offsets the box in points
    # - box_alignment controls which part of image aligns to anchor
    box_align = (0.5, 0.5) if centered else (0.5, 0)  # Center or bottom-center
    ab = AnnotationBbox(imagebox, (lon, lat),
                        xybox=(x_offset, y_offset),
                        xycoords=geodetic,
                        boxcoords="offset points",
                        box_alignment=box_align,
                        frameon=False,
                        zorder=zorder)
    ax.add_artist(ab)
    return ab
