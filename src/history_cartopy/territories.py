"""Territory rendering."""

import json
import logging
import os

import cartopy.crs as ccrs
from shapely.geometry import shape

from history_cartopy.styles import get_deg_per_pt

logger = logging.getLogger('history_cartopy.territories')

DEFAULT_ALPHA = 0.4


# =============================================================================
# Render functions
# =============================================================================

def _darken_color(color, factor=0.4):
    """Darken a color towards black. factor=0 gives black, factor=1 gives original."""
    from matplotlib.colors import to_rgb
    r, g, b = to_rgb(color)
    return (r * factor, g * factor, b * factor)


def _fuzzy_fill(ax, geometry, color, alpha):
    dpp = get_deg_per_pt(ax)
    for pt in [-4, -2, 0, 2, 4]:
        layer_alpha = alpha / (1 + abs(pt))
        ax.add_geometries([geometry.buffer(pt * dpp)], ccrs.PlateCarree(),
                          facecolor=color, alpha=layer_alpha, edgecolor='none', zorder=1)


def _hatched(ax, geometry, color, alpha):
    _fuzzy_fill(ax, geometry, color, alpha)
    ax.add_geometries([geometry], ccrs.PlateCarree(),
                      facecolor='none', edgecolor=color,
                      hatch='////', linewidth=0, alpha=0.3, zorder=2)


def _edge_tint(ax, geometry, color, alpha):
    dpp = get_deg_per_pt(ax)
    steps = [0, -2, -4, -6]
    for i in range(len(steps) - 1):
        outer_geom = geometry.buffer(steps[i] * dpp)
        inner_geom = geometry.buffer(steps[i + 1] * dpp)
        ribbon_slice = outer_geom.difference(inner_geom)
        ax.add_geometries([ribbon_slice], ccrs.PlateCarree(),
                          facecolor=color, alpha=alpha / (i + 1),
                          edgecolor='none', zorder=1)
    ax.add_geometries([geometry], ccrs.PlateCarree(),
                      facecolor='none', edgecolor=color,
                      linewidth=0.6, alpha=alpha, zorder=2)


def _edge_band(ax, geometry, color, alpha):
    dpp = get_deg_per_pt(ax)
    ribbon_steps = [0, -2, -4, -6, -8, -10]
    num_slices = len(ribbon_steps) - 1
    for i in range(num_slices):
        outer_geom = geometry.buffer(ribbon_steps[i] * dpp)
        inner_geom = geometry.buffer(ribbon_steps[i + 1] * dpp)
        ribbon_slice = outer_geom.difference(inner_geom)
        layer_alpha = 0.5 * (1 - i / num_slices)
        ax.add_geometries([ribbon_slice], ccrs.PlateCarree(),
                          facecolor=color, alpha=layer_alpha,
                          edgecolor='none', zorder=1)
    dark_color = _darken_color(color)
    ax.add_geometries([geometry], ccrs.PlateCarree(),
                      facecolor='none', edgecolor=dark_color,
                      linewidth=1.0, alpha=1.0, zorder=2)


_RENDER_FUNCS = {
    'fuzzy-fill': _fuzzy_fill,
    'hatched':    _hatched,
    'edge-tint':  _edge_tint,
    'edge-band':  _edge_band,
}


# =============================================================================
# Public entry point
# =============================================================================

def render_territories(ax, manifest, polygons_dir):
    """
    Render territories from GeoJSON files.

    Each territory entry requires:
        file:  GeoJSON filename in polygons_dir
        color: Any HTML/W3C color string (e.g. 'steelblue', '#8B4513')
        type:  Render algorithm — fuzzy-fill, hatched, edge-tint, edge-band
        alpha: (optional) Transparency 0–1, default 0.4

    Args:
        ax: matplotlib axes
        manifest: Map manifest containing 'territories' section
        polygons_dir: Directory containing GeoJSON polygon files
    """
    if 'territories' not in manifest:
        logger.debug("No territories to render")
        return

    territories = manifest['territories']
    logger.debug(f"Processing {len(territories)} territories")

    for entry in territories:
        file_name = entry.get('file')
        color = entry.get('color', 'grey')
        alpha = entry.get('alpha', DEFAULT_ALPHA)
        render_type = entry.get('type', 'fuzzy-fill')

        render_fn = _RENDER_FUNCS.get(render_type)
        if render_fn is None:
            logger.warning(f"Unknown territory type '{render_type}' for {file_name}")
            continue

        full_path = os.path.join(polygons_dir, file_name)
        if not os.path.exists(full_path):
            logger.warning(f"Skipping: {file_name} not found at {full_path}")
            continue

        try:
            with open(full_path, 'r') as f:
                data = json.load(f)

            for feature in data['features']:
                raw_geom = shape(feature['geometry'])
                render_fn(ax, raw_geom, color, alpha)

        except (KeyError, TypeError) as e:
            logger.error(f"{file_name} is not a valid GeoJSON FeatureCollection: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading {file_name}: {e}")
