#!/usr/bin/python3

import argparse
import logging
import os
import sys
import urllib.request
import zipfile
import shutil
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER
from PIL import Image
from history_cartopy.core import load_data
from history_cartopy.labels import collect_labels, render_labels_resolved
from history_cartopy.events import collect_events, render_events_resolved
from history_cartopy.campaigns import (
    collect_arrow_candidates, collect_campaign_labels, render_campaigns_resolved
)
from history_cartopy.territories import render_territories
from history_cartopy.border_styles import render_border
from history_cartopy.placement import PlacementManager
from history_cartopy.styles import get_deg_per_pt
from history_cartopy.themes import apply_theme

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('history_cartopy')


# Natural Earth background image download URLs
BACKGROUND_DOWNLOADS = {
    'HYP_HR_SR_OB_DR.tif': {
        'url': 'https://naciscdn.org/naturalearth/10m/raster/HYP_HR_SR_OB_DR.zip',
        'description': 'High resolution Natural Earth background (~400MB)',
    },
    'HYP_LR_SR_OB_DR.tif': {
        'url': 'https://naciscdn.org/naturalearth/10m/raster/HYP_LR_SR_OB_DR.zip',
        'description': 'Medium resolution Natural Earth background (~200MB)',
    },
    'HYP_HR_SR_OB_DR_YELLOW.tif': {
        'url': 'https://home.chetanv.net/history_cartopy/HYP_HR_SR_OB_DR_YELLOW.zip',
        'description': 'High resolution yellow variant background',
    },
    'HYP_LR_SR_OB_DR_YELLOW.tif': {
        'url': 'https://home.chetanv.net/history_cartopy/HYP_LR_SR_OB_DR_YELLOW.zip',
        'description': 'Low resolution yellow variant background',
    },
    'HYP_LR_SR_OB_DR_GREY.tif': {
        'url': 'https://home.chetanv.net/history_cartopy/HYP_LR_SR_OB_DR_GREY.zip',
        'description': 'Low resolution grey variant background',
    },
    'HYP_LR_SR_OB_DR_BW.tif': {
        'url': 'https://home.chetanv.net/history_cartopy/HYP_LR_SR_OB_DR_BW.zip',
        'description': 'Low resolution black & white variant background',
    },
}

# Natural Earth vector data downloads
VECTOR_DOWNLOADS = {
    'ne_10m_rivers_lake_centerlines': {
        'url': 'https://naciscdn.org/naturalearth/10m/physical/ne_10m_rivers_lake_centerlines.zip',
        'description': 'Rivers and lake centerlines (~2MB)',
        'subdir': 'rivers',
    },
}


def _get_data_dir():
    """Get the data directory path, using package-relative path."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, '..', '..', 'data')
    return os.path.normpath(data_dir)


def download_backgrounds():
    """Download Natural Earth background images to the data/backgrounds directory."""
    # Determine backgrounds directory
    backgrounds_dir = os.path.join(_get_data_dir(), 'backgrounds')

    os.makedirs(backgrounds_dir, exist_ok=True)

    print(f"Downloading Natural Earth backgrounds to: {backgrounds_dir}")
    print()

    for tif_name, info in BACKGROUND_DOWNLOADS.items():
        tif_path = os.path.join(backgrounds_dir, tif_name)

        if os.path.exists(tif_path):
            print(f"[SKIP] {tif_name} already exists")
            continue

        print(f"[DOWNLOAD] {info['description']}")
        print(f"  URL: {info['url']}")

        zip_name = os.path.basename(info['url'])
        zip_path = os.path.join(backgrounds_dir, zip_name)

        try:
            # Download with progress
            def report_progress(block_num, block_size, total_size):
                downloaded = block_num * block_size
                if total_size > 0:
                    percent = min(100, downloaded * 100 // total_size)
                    mb_downloaded = downloaded / (1024 * 1024)
                    mb_total = total_size / (1024 * 1024)
                    print(f"\r  Progress: {percent}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)", end='', flush=True)

            urllib.request.urlretrieve(info['url'], zip_path, reporthook=report_progress)
            print()  # newline after progress

            # Extract the tif file
            print(f"  Extracting {tif_name}...")
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # Find the tif file in the archive
                tif_files = [f for f in zf.namelist() if f.endswith('.tif')]
                if not tif_files:
                    print(f"  [ERROR] No .tif file found in {zip_name}")
                    continue

                # Extract to temp location and move to proper name
                zf.extract(tif_files[0], backgrounds_dir)
                extracted_path = os.path.join(backgrounds_dir, tif_files[0])
                if extracted_path != tif_path:
                    shutil.move(extracted_path, tif_path)

            # Clean up zip file
            os.remove(zip_path)
            print(f"  [OK] {tif_name}")

        except Exception as e:
            print(f"  [ERROR] Failed to download {tif_name}: {e}")
            # Clean up partial files
            if os.path.exists(zip_path):
                os.remove(zip_path)

    print()
    print("Background download complete.")


def download_vectors():
    """Download Natural Earth vector data (rivers, etc.) to the data directory."""
    data_dir = _get_data_dir()

    for name, info in VECTOR_DOWNLOADS.items():
        target_dir = os.path.join(data_dir, info['subdir'])
        os.makedirs(target_dir, exist_ok=True)

        shp_path = os.path.join(target_dir, f"{name}.shp")
        if os.path.exists(shp_path):
            print(f"[SKIP] {name} already exists")
            continue

        print(f"[DOWNLOAD] {info['description']}")
        zip_path = os.path.join(target_dir, os.path.basename(info['url']))

        try:
            urllib.request.urlretrieve(info['url'], zip_path)
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(target_dir)
            os.remove(zip_path)
            print(f"[OK] {name}")
        except Exception as e:
            print(f"[ERROR] {name}: {e}")


def _render_scale_bar(ax, extent, position='bottom-left'):
    """
    Render a dual scale bar (km and miles) on the map.

    Args:
        ax: Matplotlib axes with cartopy projection
        extent: [west, east, south, north] in degrees
        position: 'bottom-left', 'bottom-right', 'top-left', 'top-right'
    """
    import math
    import matplotlib.patches as mpatches

    west, east, south, north = extent
    map_width_deg = east - west
    map_height_deg = north - south

    # Calculate the scale at the map center
    center_lat = (south + north) / 2

    # Distance for 1 degree of longitude at this latitude
    # Using WGS84 ellipsoid approximation
    km_per_deg = 111.32 * math.cos(math.radians(center_lat))

    # Choose a nice round scale length (aim for ~15% of map width)
    target_km = km_per_deg * map_width_deg * 0.15

    # Round to nice values
    nice_values = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000]
    scale_km = min(nice_values, key=lambda x: abs(x - target_km))
    scale_deg = scale_km / km_per_deg

    # Convert to miles
    scale_miles = scale_km * 0.621371

    # Position the scale bar
    margin = 0.03  # 3% margin from edges
    bar_height_deg = map_height_deg * 0.008

    if 'left' in position:
        bar_x = west + map_width_deg * margin
    else:
        bar_x = east - map_width_deg * margin - scale_deg

    if 'bottom' in position:
        bar_y = south + map_height_deg * margin
    else:
        bar_y = north - map_height_deg * margin - bar_height_deg * 6

    # Draw the scale bar (alternating black/white segments)
    num_segments = 4
    seg_width = scale_deg / num_segments

    for i in range(num_segments):
        color = 'black' if i % 2 == 0 else 'white'
        rect = mpatches.Rectangle(
            (bar_x + i * seg_width, bar_y),
            seg_width, bar_height_deg,
            facecolor=color, edgecolor='black', linewidth=0.5,
            transform=ccrs.PlateCarree(), zorder=10
        )
        ax.add_patch(rect)

    # Add labels
    label_y = bar_y + bar_height_deg * 1.5

    # Kilometers label
    km_text = f"{scale_km} km" if scale_km >= 1 else f"{int(scale_km * 1000)} m"
    ax.text(bar_x + scale_deg / 2, label_y, km_text,
            ha='center', va='bottom', fontsize=7, fontweight='bold',
            transform=ccrs.PlateCarree(), zorder=10)

    # Miles label (below km)
    miles_text = f"{scale_miles:.0f} miles" if scale_miles >= 1 else f"{scale_miles:.1f} miles"
    ax.text(bar_x + scale_deg / 2, bar_y - bar_height_deg * 0.5, miles_text,
            ha='center', va='top', fontsize=6, color='#555555',
            transform=ccrs.PlateCarree(), zorder=10)

    # Tick marks at ends
    for x in [bar_x, bar_x + scale_deg]:
        ax.plot([x, x], [bar_y, bar_y + bar_height_deg * 1.3],
                color='black', linewidth=0.5, transform=ccrs.PlateCarree(), zorder=10)


def _validate_dimensions(dimensions_px, dpi=300):
    """
    Validate map dimensions in pixels.

    Requirements:
        - Must be 3:2 aspect ratio (landscape)
        - Should be divisible by 300 for clean DPI conversion
        - Should be divisible by 200 for complete tile patterns

    Args:
        dimensions_px: [width, height] in pixels
        dpi: Output DPI (default 300)

    Raises:
        ValueError: If dimensions don't meet requirements
    """
    if not dimensions_px:
        return

    width_px, height_px = dimensions_px
    aspect_ratio = width_px / height_px
    expected_ratio = 1.5  # 3:2

    # Check 3:2 aspect ratio
    tolerance = 0.01
    if abs(aspect_ratio - expected_ratio) > tolerance:
        raise ValueError(
            f"Dimensions must maintain 3:2 aspect ratio.\n"
            f"Got {width_px}×{height_px} (ratio: {aspect_ratio:.3f}), "
            f"expected ratio: 1.5"
        )

    # Check divisibility by DPI (for clean inch conversion)
    if width_px % dpi != 0 or height_px % dpi != 0:
        logger.warning(f"Dimensions {width_px}x{height_px} not evenly divisible by DPI ({dpi})")
        logger.warning(f"  Fractional inches: {width_px/dpi:.2f}\" x {height_px/dpi:.2f}\"")
        logger.warning(f"  Recommended: 3600x2400, 4800x3200, 6000x4000")

    # Check divisibility by tile size (200px) for clean tiling
    tile_size = 200
    if width_px % tile_size != 0 or height_px % tile_size != 0:
        logger.warning(f"Dimensions {width_px}x{height_px} not evenly divisible by tile size ({tile_size}px)")
        logger.warning("  This may result in cropped border patterns")


def main():
    parser = argparse.ArgumentParser(description='History Map Renderer')
    parser.add_description = 'Render a historical map from a YAML manifest.'

    # 1. Positional argument for the manifest (optional if --init is used)
    parser.add_argument('manifest', nargs='?', help='Path to the map manifest YAML aaaa')

    # 2. Optional overrides
    parser.add_argument('--init', action='store_true', help='Download Natural Earth background images')
    parser.add_argument('--res', choices=['dev', 'low', 'med', 'high', 'med-yellow', 'high-yellow', 'med-grey', 'med-bw'], help='Override background resolution')
    parser.add_argument('--output', help='Override output filename')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--debug-river-candidates', action='store_true', help='Render all river label candidates')

    args = parser.parse_args()

    if args.debug:
        logging.getLogger('history_cartopy').setLevel(logging.DEBUG)

    # Handle --init: download backgrounds and vector data, then exit
    if args.init:
        download_backgrounds()
        download_vectors()
        return

    # Require manifest for normal operation
    if not args.manifest:
        parser.error('manifest is required (unless using --init)')
        return

    logger.info(f"Loading manifest: {args.manifest}")

    # Remove limit on large file sizes for high-res images
    Image.MAX_IMAGE_PIXELS = None

    data_dir = _get_data_dir()
    backgrounds_dir = os.path.join(data_dir, 'backgrounds')
    polygons_dir = os.path.join(data_dir, 'polygons')
    gazetteer_path = os.path.join(data_dir, 'city-locations.yaml')
    gazetteer, manifest = load_data(gazetteer_path, args.manifest)
    logger.debug(f"Loaded {len(gazetteer)} locations from gazetteer")

    # Apply theme (mutates stylemaps dicts in place)
    theme_name = manifest['metadata'].get('theme', 'eighties-textbook')
    theme = apply_theme(theme_name)

    # Resolve Settings (CLI > manifest > theme defaults)
    res = args.res or manifest['metadata'].get('resolution') or theme['background']
    out_file = args.output or manifest['metadata'].get('output', 'map.png')
    extent = manifest['metadata']['extent']
    border_style = manifest['metadata'].get('border_style') or theme.get('border_style')

    # Get dimensions in pixels (required)
    dimensions_px = manifest['metadata'].get('dimensions', [3600, 2400])  # Default: 3600×2400px

    # Validate dimensions if borders enabled
    if border_style:
        _validate_dimensions(dimensions_px, dpi=300)

    # Convert pixels to inches for matplotlib
    dpi = 300
    figsize = [dimensions_px[0] / dpi, dimensions_px[1] / dpi]

    # Setup Plot
    fig = plt.figure(figsize=figsize)
    ax = plt.axes(projection=ccrs.PlateCarree())
    ax.set_extent(extent, crs=ccrs.PlateCarree())

    # Background Logic (Example using Cartopy stock images)
    # Set custom backgrounds directory for Cartopy
    os.environ['CARTOPY_USER_BACKGROUNDS'] = backgrounds_dir

    if res == 'high':
        # This is magical - the hi-res maps from Natural Earth are perfect for the purpose
        ax.background_img(name='ne_hyp', resolution='high')
    elif res == 'med':
        ax.background_img(name='ne_hyp', resolution='med')
    elif res == 'high-yellow':
        ax.background_img(name='ne_hyp', resolution='high-yellow')
    elif res == 'med-yellow':
        ax.background_img(name='ne_hyp', resolution='med-yellow')
    elif res == 'med-grey':
        ax.background_img(name='ne_hyp', resolution='med-grey')
    elif res == 'med-bw':
        ax.background_img(name='ne_hyp', resolution='med-bw')
    elif res == 'low':
        ax.stock_img()
    elif res == 'dev':
        ax.coastlines(resolution='110m')

    # Graticule (lat/lon grid and labels)
    graticule = manifest['metadata'].get('graticule', False)
    if graticule:
        # Support both boolean and dict config
        if isinstance(graticule, dict):
            show_lines = graticule.get('lines', False)
            show_labels = graticule.get('labels', True)
        else:
            show_lines = False
            show_labels = True

        gl = ax.gridlines(
            crs=ccrs.PlateCarree(),
            draw_labels=show_labels,
            linewidth=0.5 if show_lines else 0,
            color='gray',
            alpha=0.5,
            linestyle='--'
        )
        gl.top_labels = False      # Labels on bottom and left only
        gl.right_labels = False
        gl.xformatter = LONGITUDE_FORMATTER
        gl.yformatter = LATITUDE_FORMATTER
        gl.xlabel_style = {'size': 8, 'color': 'gray'}
        gl.ylabel_style = {'size': 8, 'color': 'gray'}

    # Run Engine
    logger.info("Rendering territories")
    render_territories(ax, manifest, polygons_dir)

    # Create placement manager for overlap detection
    dpp = get_deg_per_pt(ax)
    logger.info(f"Degrees per point (dpp) = {dpp:.6f}")
    pm = PlacementManager(dpp)

    # =========================================================================
    # TWO-PASS LABEL PLACEMENT
    # Phase 1: COLLECT - gather city/event label candidates
    # Phase 2a: RESOLVE ARROWS - pick gap distance for campaign arrows
    # Phase 2b: COLLECT CAMPAIGN LABELS - generate labels from resolved arrows
    # Phase 2c: RESOLVE ALL LABELS - greedy algorithm picks best positions
    # Phase 3: RENDER - draw everything at resolved positions
    # =========================================================================

    # Phase 1: COLLECT (cities, rivers, regions, events)
    logger.info("Collecting labels")
    city_candidates, river_candidates, river_data, region_data, city_render_data = collect_labels(
        gazetteer, manifest, pm, data_dir=data_dir
    )

    logger.info("Collecting events")
    event_candidates, event_render_data = collect_events(
        gazetteer, manifest, pm, data_dir=data_dir
    )

    # Collect arrow candidates (with 2x, 3x, 4x gap variants)
    logger.info("Collecting campaign arrow candidates")
    arrow_candidates, campaign_render_data = collect_arrow_candidates(
        gazetteer, manifest, pm
    )

    # Phase 2a: RESOLVE ARROWS
    # City dots/icons are already in PM from collect_labels(), so arrows can avoid them
    logger.info("Resolving arrow gaps")
    resolved_arrows = pm.resolve_arrows(arrow_candidates)
    logger.info(f"Resolved {len(resolved_arrows)} arrow gaps")

    # Update campaign_render_data with resolved geometry
    for data in campaign_render_data:
        arrow_id = f"campaign_arrow_{data['idx']}"
        if arrow_id in resolved_arrows:
            data['geometry'] = resolved_arrows[arrow_id].resolved_geometry

    # Phase 2b: COLLECT CAMPAIGN LABELS (after arrows resolved)
    logger.info("Collecting campaign labels from resolved arrows")
    campaign_candidates = collect_campaign_labels(manifest, resolved_arrows, pm)

    # Phase 2c: RESOLVE ALL LABELS
    logger.info("Resolving label overlaps")
    all_candidates = city_candidates + river_candidates + campaign_candidates + event_candidates
    resolved_positions = pm.resolve_greedy(all_candidates)
    logger.info(f"Resolved {len(resolved_positions)} label positions")

    # Phase 3: RENDER
    logger.info("Rendering labels")
    render_labels_resolved(ax, city_render_data, river_data, region_data,
                           resolved_positions, gazetteer, manifest, data_dir=data_dir,
                           river_candidates=river_candidates,
                           debug_river_candidates=args.debug_river_candidates)

    logger.info("Rendering campaigns")
    render_campaigns_resolved(ax, campaign_render_data, resolved_positions)

    logger.info("Rendering events")
    render_events_resolved(ax, event_render_data, resolved_positions,
                           data_dir=data_dir, manifest=manifest)

    # Scale bar
    scale_bar = manifest['metadata'].get('scale_bar', False)
    if scale_bar:
        position = scale_bar if isinstance(scale_bar, str) else 'bottom-left'
        _render_scale_bar(ax, extent, position=position)

    # Render borders (must be after all map elements so borders are on top)
    if border_style:
        borders_dir = os.path.join(data_dir, 'borders')
        render_border(ax, fig, border_style, borders_dir, dimensions_px, dpi=dpi)

    from history_cartopy.stylemaps import TITLE_STYLE
    plt.title(
        f"{manifest['metadata']['title']} ({manifest['metadata']['year']})",
        fontsize=TITLE_STYLE.get('fontsize', 14),
        fontweight=TITLE_STYLE.get('fontweight', 'bold'),
        fontfamily=TITLE_STYLE.get('fontfamily', 'serif'),
        color=TITLE_STYLE.get('color', 'black'),
        pad=TITLE_STYLE.get('pad', 20),
    )

    # Save
    # Don't use bbox_inches='tight' - we want exact dimensions as specified
    logger.info(f"Saving map to {out_file}")
    plt.savefig(out_file, dpi=dpi)
    logger.info(f"Map saved to {out_file}")

if __name__ == "__main__":
    main()
