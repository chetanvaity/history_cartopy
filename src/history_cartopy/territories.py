"""Territory rendering."""

import json
import logging
import os

from shapely.geometry import shape

from history_cartopy.territory_styles import (
    apply_fuzzy_fill_territory,
    apply_hatched_territory,
    apply_edge_tint_territory,
    apply_edge_band_territory,
)

logger = logging.getLogger('history_cartopy.territories')


def render_territories(ax, manifest, polygons_dir):
    """
    Render territories from GeoJSON files.

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
        style_key = entry.get('style', 'kingdom1')
        render_type = entry.get('type', 'fuzzy_fill')  # Default type

        full_path = os.path.join(polygons_dir, file_name)
        if not os.path.exists(full_path):
            logger.warning(f"Skipping: {file_name} not found at {full_path}")
            continue

        try:
            with open(full_path, 'r') as f:
                data = json.load(f)

            # Strict Enforcement: Assume FeatureCollection (GeoJSON)
            # This allows a single file to contain multiple "islands" of one kingdom
            for feature in data['features']:
                # Load the raw geometry
                raw_geom = shape(feature['geometry'])
                # TBD: Automatic Smoothening
                smooth_geom = raw_geom

                # Route to the specialized functions in styles.py
                if render_type == 'fuzzy-fill':
                    apply_fuzzy_fill_territory(ax, smooth_geom, style_key)
                elif render_type == 'hatched':
                    apply_hatched_territory(ax, smooth_geom, style_key)
                elif render_type == 'edge-tint':
                    apply_edge_tint_territory(ax, smooth_geom, style_key)
                elif render_type == 'edge-band':
                    apply_edge_band_territory(ax, smooth_geom, style_key)
                else:
                    logger.warning(f"Unknown territory type: {render_type}")

        except (KeyError, TypeError) as e:
            logger.error(f"{file_name} is not a valid GeoJSON FeatureCollection: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading {file_name}: {e}")
