import matplotlib.patheffects as PathEffects
from matplotlib.transforms import offset_copy
import cartopy.crs as ccrs
import matplotlib.patches as patches
import numpy as np
import json
from shapely.geometry import shape
import cartopy.feature as cfeature
from history_cartopy.stylemaps import *

def apply_text(ax, lon, lat, text, style_key, color_override=None, rotation=0, x_offset=0, y_offset=0, **kwargs):
    style = LABEL_STYLES.get(style_key, {}).copy()
    if color_override:
        style['color'] = color_override
    style.update(kwargs)

    use_halo = style.pop('halo', False)

    # --- INTELLIGENT OFFSET LOGIC ---
    # 1. Start with the Geodetic transform (Lat/Lon)
    geodetic = ccrs.PlateCarree()._as_mpl_transform(ax)

    # 2. Create an offset transform (measured in Points, not degrees)
    # 72 points = 1 inch. This stays consistent at any zoom.
    offset_transform = offset_copy(geodetic, fig=ax.figure,
                                   x= x_offset,
                                   y= y_offset,
                                   units='points')

    # Note: We pass transform=offset_transform, NOT ccrs.PlateCarree()
    t = ax.text(lon, lat, text, transform=offset_transform,
                rotation=rotation, **style)

    if use_halo:
        t.set_path_effects([PathEffects.withStroke(linewidth=2, foreground='white', alpha=0.7)])
    return t


# Utility
def get_deg_per_pt(ax):
    """Utility to keep our 'fuzziness' scale-independent."""
    bbox = ax.get_window_extent().transformed(ax.figure.dpi_scale_trans.inverted())
    width_deg = ax.get_extent()[1] - ax.get_extent()[0]
    return width_deg / (bbox.width * 72)
