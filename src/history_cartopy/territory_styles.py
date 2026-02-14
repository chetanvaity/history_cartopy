import matplotlib.patheffects as PathEffects
from matplotlib.transforms import offset_copy
import cartopy.crs as ccrs
import matplotlib.patches as patches
import numpy as np
from history_cartopy.stylemaps import *
from history_cartopy.styles import *


def apply_fuzzy_fill_territory(ax, geometry, style_key):
    style = TERRITORY_STYLES.get(style_key).copy()
    dpp = get_deg_per_pt(ax)

    # Balanced stack: -4pt to +4pt
    for pt in [-4, -2, 0, 2, 4]:
        layer_alpha = style['alpha'] / (1 + abs(pt))
        ax.add_geometries([geometry.buffer(pt * dpp)], ccrs.PlateCarree(),
                          facecolor=style['facecolor'], alpha=layer_alpha, edgecolor='none', zorder=1)

def apply_hatched_territory(ax, geometry, style_key):
    style = TERRITORY_STYLES.get(style_key).copy()
    # 1. Background Glow (very faint)
    apply_fuzzy_fill_territory(ax, geometry, style_key) # uses alpha from style

    # 2. Sharp Hatching
    ax.add_geometries([geometry], ccrs.PlateCarree(),
                      facecolor='none', edgecolor=style['edgecolor'],
                      hatch=style.get('hatch', '////'), linewidth=0, alpha=0.3, zorder=2)


def apply_edge_tint_territory(ax, geometry, style_key):
    style = TERRITORY_STYLES.get(style_key).copy()
    dpp = get_deg_per_pt(ax)
    color = style['facecolor']
    base_alpha = style.get('alpha', 0.4)

    # We want a ribbon that is, say, 8 points wide total.
    # We will draw 4 concentric rings, each 2 points wide,
    # moving from the edge toward the center.
    steps = [0, -2, -4, -6] # pt offsets inward

    for i in range(len(steps) - 1):
        outer_pt = steps[i]
        inner_pt = steps[i+1]

        # Create the 'donut' slice for this layer
        outer_geom = geometry.buffer(outer_pt * dpp)
        inner_geom = geometry.buffer(inner_pt * dpp)
        ribbon_slice = outer_geom.difference(inner_geom)

        # Fade the alpha as we move deeper into the kingdom
        layer_alpha = base_alpha / (i + 1)

        ax.add_geometries([ribbon_slice], ccrs.PlateCarree(),
                          facecolor=color,
                          alpha=layer_alpha,
                          edgecolor='none',
                          zorder=1)

    # A crisp line exactly on the border
    ax.add_geometries([geometry], ccrs.PlateCarree(),
                      facecolor='none',
                      edgecolor=color,
                      linewidth=0.6,
                      alpha=base_alpha,
                      zorder=2)


def _darken_color(hex_color, factor=0.4):
    """Darken a hex color towards black. factor=0 gives black, factor=1 gives original."""
    from matplotlib.colors import to_rgb
    r, g, b = to_rgb(hex_color)
    return (r * factor, g * factor, b * factor)


def apply_edge_band_territory(ax, geometry, style_key):
    style = TERRITORY_STYLES.get(style_key).copy()
    dpp = get_deg_per_pt(ax)
    color = style['facecolor']

    # Inner ribbon: 10pt wide, fading inward in 5 slices
    ribbon_steps = [0, -2, -4, -6, -8, -10]
    num_slices = len(ribbon_steps) - 1
    for i in range(num_slices):
        outer_geom = geometry.buffer(ribbon_steps[i] * dpp)
        inner_geom = geometry.buffer(ribbon_steps[i + 1] * dpp)
        ribbon_slice = outer_geom.difference(inner_geom)

        # Linear fade from 0.5 at the border to 0 at the inner edge
        layer_alpha = 0.5 * (1 - i / num_slices)

        ax.add_geometries([ribbon_slice], ccrs.PlateCarree(),
                          facecolor=color,
                          alpha=layer_alpha,
                          edgecolor='none',
                          zorder=1)

    # Dark border line: 2pt, territory color darkened towards black
    dark_color = _darken_color(color)
    ax.add_geometries([geometry], ccrs.PlateCarree(),
                      facecolor='none',
                      edgecolor=dark_color,
                      linewidth=1.0,
                      alpha=1.0,
                      zorder=2)

