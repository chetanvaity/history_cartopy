"""
Tiled PNG border rendering for History Cartopy maps.

This module loads 8 PNG tiles (4 edges + 4 corners) from data/borders/<style>/
and composites them around the map edges using matplotlib's image display.
"""

import os
import numpy as np
from PIL import Image


# Required tile filenames
REQUIRED_TILES = {
    'left': 'left-vertical-tile.png',
    'right': 'right-vertical-tile.png',
    'top': 'top-horizontal-tile.png',
    'bottom': 'bottom-horizontal-tile.png',
    'top_left': 'left-top-corner-tile.png',
    'top_right': 'right-top-corner-tile.png',
    'bottom_left': 'left-bottom-corner-tile.png',
    'bottom_right': 'right-bottom-corner-tile.png'
}

# Standard border width in pixels
BORDER_WIDTH_PX = 100


def _list_available_styles(borders_dir):
    """
    List available border styles (directory names in borders_dir).

    Args:
        borders_dir: Path to data/borders/ directory

    Returns:
        list: Available border style names
    """
    if not os.path.exists(borders_dir):
        return []
    return [d for d in os.listdir(borders_dir)
            if os.path.isdir(os.path.join(borders_dir, d))]


def _load_border_tiles(border_style_name, borders_dir):
    """
    Load all 8 border tiles from the specified style directory.

    Args:
        border_style_name: Name of border style (e.g., "medieval-islamic")
        borders_dir: Path to data/borders/ directory

    Returns:
        dict: Tiles with keys 'left', 'right', 'top', 'bottom',
              'top_left', 'top_right', 'bottom_left', 'bottom_right'
              Each value is a PIL Image (RGBA)

    Raises:
        FileNotFoundError: If style directory doesn't exist
        ValueError: If any required PNG files are missing
    """
    style_path = os.path.join(borders_dir, border_style_name)

    # Validate directory exists
    if not os.path.exists(style_path):
        available = _list_available_styles(borders_dir)
        available_str = ', '.join(available) if available else 'none'
        raise FileNotFoundError(
            f"Border style '{border_style_name}' not found.\n"
            f"Expected directory: {style_path}\n"
            f"Available styles: {available_str}"
        )

    # Load each required tile as RGBA
    tiles = {}
    missing = []

    for key, filename in REQUIRED_TILES.items():
        tile_path = os.path.join(style_path, filename)
        if not os.path.exists(tile_path):
            missing.append(filename)
        else:
            try:
                tiles[key] = Image.open(tile_path).convert('RGBA')
            except Exception as e:
                raise IOError(
                    f"Failed to load border tile: {tile_path}\n"
                    f"Error: {str(e)}"
                )

    if missing:
        raise ValueError(
            f"Border style '{border_style_name}' is incomplete.\n"
            f"Missing files: {', '.join(missing)}"
        )

    return tiles


def _repeat_tile_horizontal(tile, target_width_px):
    """
    Repeat tile horizontally to fill target width.

    Args:
        tile: PIL Image (RGBA)
        target_width_px: Total width to fill in pixels

    Returns:
        PIL Image (RGBA): Tiled image
    """
    tile_array = np.array(tile)
    tile_width = tile.width

    # Calculate number of repeats (should divide evenly for standard sizes)
    # For 200px tiles and 3000px width: 3000 ÷ 200 = 15 complete tiles
    num_repeats = target_width_px // tile_width

    # Handle case where target doesn't divide evenly (add one more and crop)
    if target_width_px % tile_width != 0:
        num_repeats += 1

    # Tile along width axis (axis=1)
    tiled = np.tile(tile_array, (1, num_repeats, 1))

    # Crop to exact target width
    tiled = tiled[:, :target_width_px, :]

    return Image.fromarray(tiled.astype('uint8'))


def _repeat_tile_vertical(tile, target_height_px):
    """
    Repeat tile vertically to fill target height.

    Args:
        tile: PIL Image (RGBA)
        target_height_px: Total height to fill in pixels

    Returns:
        PIL Image (RGBA): Tiled image
    """
    tile_array = np.array(tile)
    tile_height = tile.height

    # Calculate number of repeats (should divide evenly for standard sizes)
    # For 200px tiles and 2000px height: 2000 ÷ 200 = 10 complete tiles
    num_repeats = target_height_px // tile_height

    # Handle case where target doesn't divide evenly (add one more and crop)
    if target_height_px % tile_height != 0:
        num_repeats += 1

    # Tile along height axis (axis=0)
    tiled = np.tile(tile_array, (num_repeats, 1, 1))

    # Crop to exact target height
    tiled = tiled[:target_height_px, :, :]

    return Image.fromarray(tiled.astype('uint8'))


def render_border(ax, fig, border_style_name, borders_dir, dimensions_px, dpi=300):
    """
    Render tiled PNG borders around the map.

    Args:
        ax: Matplotlib axes object (with PlateCarree projection)
        fig: Matplotlib figure object
        border_style_name: Name of border style (e.g., "medieval-islamic")
        borders_dir: Path to data/borders/ directory
        dimensions_px: [width, height] in pixels
        dpi: Output DPI (default 300)

    The borders are rendered on an overlay axes that sits on top of the map.
    This overlay uses transAxes coordinates (0-1 range), keeping borders fixed
    relative to figure edges regardless of map geographic extent or zoom.

    Rendering order:
        - Edges at zorder=7.0
        - Corners at zorder=7.5 (overlay on edges)
    """
    # Load all 8 tiles
    tiles = _load_border_tiles(border_style_name, borders_dir)

    # Create an overlay axes for the borders (non-geo axes on top of map)
    # This axes covers the entire figure and is transparent except for borders
    overlay_ax = fig.add_axes(ax.get_position(), frameon=False, zorder=10)
    overlay_ax.set_xlim(0, 1)
    overlay_ax.set_ylim(0, 1)
    overlay_ax.set_xticks([])
    overlay_ax.set_yticks([])
    overlay_ax.patch.set_visible(False)  # Transparent background

    # Get pixel dimensions
    fig_width_px, fig_height_px = dimensions_px

    # Calculate border dimensions in axes coordinates (0-1 range)
    border_width_axes_x = BORDER_WIDTH_PX / fig_width_px
    border_width_axes_y = BORDER_WIDTH_PX / fig_height_px

    # === RENDER EDGES (with tiling) ===

    # Top edge
    top_tiled = _repeat_tile_horizontal(tiles['top'], fig_width_px)
    overlay_ax.imshow(top_tiled,
                      extent=[0, 1, 1 - border_width_axes_y, 1],
                      zorder=7.0,
                      clip_on=False,
                      aspect='auto')

    # Bottom edge
    bottom_tiled = _repeat_tile_horizontal(tiles['bottom'], fig_width_px)
    overlay_ax.imshow(bottom_tiled,
                      extent=[0, 1, 0, border_width_axes_y],
                      zorder=7.0,
                      clip_on=False,
                      aspect='auto')

    # Left edge
    left_tiled = _repeat_tile_vertical(tiles['left'], fig_height_px)
    overlay_ax.imshow(left_tiled,
                      extent=[0, border_width_axes_x, 0, 1],
                      zorder=7.0,
                      clip_on=False,
                      aspect='auto')

    # Right edge
    right_tiled = _repeat_tile_vertical(tiles['right'], fig_height_px)
    overlay_ax.imshow(right_tiled,
                      extent=[1 - border_width_axes_x, 1, 0, 1],
                      zorder=7.0,
                      clip_on=False,
                      aspect='auto')

    # === RENDER CORNERS (on top of edges) ===

    # Top-left corner
    corner = tiles['top_left']
    corner_width_axes = corner.width / fig_width_px
    corner_height_axes = corner.height / fig_height_px
    overlay_ax.imshow(corner,
                      extent=[0, corner_width_axes, 1 - corner_height_axes, 1],
                      zorder=7.5,
                      clip_on=False,
                      aspect='auto')

    # Top-right corner
    corner = tiles['top_right']
    corner_width_axes = corner.width / fig_width_px
    corner_height_axes = corner.height / fig_height_px
    overlay_ax.imshow(corner,
                      extent=[1 - corner_width_axes, 1, 1 - corner_height_axes, 1],
                      zorder=7.5,
                      clip_on=False,
                      aspect='auto')

    # Bottom-left corner
    corner = tiles['bottom_left']
    corner_width_axes = corner.width / fig_width_px
    corner_height_axes = corner.height / fig_height_px
    overlay_ax.imshow(corner,
                      extent=[0, corner_width_axes, 0, corner_height_axes],
                      zorder=7.5,
                      clip_on=False,
                      aspect='auto')

    # Bottom-right corner
    corner = tiles['bottom_right']
    corner_width_axes = corner.width / fig_width_px
    corner_height_axes = corner.height / fig_height_px
    overlay_ax.imshow(corner,
                      extent=[1 - corner_width_axes, 1, 0, corner_height_axes],
                      zorder=7.5,
                      clip_on=False,
                      aspect='auto')
