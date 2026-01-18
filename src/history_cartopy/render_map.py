#!/usr/bin/python3

import argparse
import os
import sys
import urllib.request
import zipfile
import shutil
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER
from PIL import Image
from history_cartopy.core import load_data, render_labels, render_campaigns, render_territories, render_events
from history_cartopy.border_styles import render_border


# Natural Earth background image download URLs
BACKGROUND_DOWNLOADS = {
    'HYP_HR_SR_OB_DR.tif': {
        'url': 'https://naciscdn.org/naturalearth/10m/raster/HYP_HR_SR_OB_DR.zip',
        'description': 'High resolution Natural Earth background (~400MB)',
    },
    'HYP_LR_SR_OB_DR.tif': {
        'url': 'https://naciscdn.org/naturalearth/50m/raster/HYP_LR_SR_OB_DR.zip',
        'description': 'Medium resolution Natural Earth background (~15MB)',
    },
}


def download_backgrounds():
    """Download Natural Earth background images to the data/backgrounds directory."""
    # Determine backgrounds directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backgrounds_dir = os.path.join(script_dir, '..', '..', 'data', 'backgrounds')
    backgrounds_dir = os.path.normpath(backgrounds_dir)

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
    print()
    print("Note: The '-yellow' variants are custom files and must be created manually.")
    print("Set environment variable: export CARTOPY_USER_BACKGROUNDS=" + backgrounds_dir)


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
        print(f"Warning: Dimensions {width_px}×{height_px} not evenly divisible by DPI ({dpi}).")
        print(f"  This results in fractional inches: {width_px/dpi:.2f}\" × {height_px/dpi:.2f}\"")
        print(f"  Recommended dimensions divisible by {dpi}: 3600×2400, 4800×3200, 6000×4000")

    # Check divisibility by tile size (200px) for clean tiling
    tile_size = 200
    if width_px % tile_size != 0 or height_px % tile_size != 0:
        print(f"Warning: Dimensions {width_px}×{height_px} not evenly divisible by tile size ({tile_size}px).")
        print(f"  This may result in cropped border patterns.")
        print(f"  Recommended dimensions divisible by {tile_size}: 3000×2000, 3600×2400, 4000×2667")


def main():
    parser = argparse.ArgumentParser(description='History Map Renderer')
    parser.add_description = 'Render a historical map from a YAML manifest.'

    # 1. Positional argument for the manifest (optional if --init is used)
    parser.add_argument('manifest', nargs='?', help='Path to the map manifest YAML')

    # 2. Optional overrides
    parser.add_argument('--init', action='store_true', help='Download Natural Earth background images')
    parser.add_argument('--res', choices=['dev', 'low', 'med', 'high', 'med-yellow', 'high-yellow'], help='Override background resolution')
    parser.add_argument('--output', help='Override output filename')
    parser.add_argument('--no-show', action='store_true', help='Save file without opening window (good for SSH)')

    args = parser.parse_args()

    # Handle --init: download backgrounds and exit
    if args.init:
        download_backgrounds()
        return

    # Require manifest for normal operation
    if not args.manifest:
        parser.error('manifest is required (unless using --init)')
        return

    # Remove limit on large file sizes for high-res images
    Image.MAX_IMAGE_PIXELS = None
    
    backgrounds_dir = os.getenv("CARTOPY_USER_BACKGROUNDS")
    polygons_dir = os.path.join(backgrounds_dir, '../polygons/')
    gazetteer_path = os.path.join(backgrounds_dir, '../city-locations.yaml')    
    gazetteer, manifest = load_data(gazetteer_path, args.manifest)

    # Resolve Settings (CLI overrides Manifest)
    res = args.res or manifest['metadata'].get('resolution', 'low')
    out_file = args.output or manifest['metadata'].get('output', 'map.png')
    extent = manifest['metadata']['extent']
    border_style = manifest['metadata'].get('border_style')

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
    if res == 'high':
        # This is magical - the hi-res maps from Natural Earth are perfect for the purpose
        ax.background_img(name='ne_hyp', resolution='high')
    elif res == 'med':
        ax.background_img(name='ne_hyp', resolution='med')
    elif res == 'high-yellow':
        ax.background_img(name='ne_hyp', resolution='high-yellow')
    elif res == 'med-yellow':
        ax.background_img(name='ne_hyp', resolution='med-yellow')
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
    data_dir = os.path.join(backgrounds_dir, '..')
    render_territories(ax, manifest, polygons_dir)
    render_labels(ax, gazetteer, manifest, data_dir=data_dir)
    render_campaigns(ax, gazetteer, manifest)
    render_events(ax, gazetteer, manifest, data_dir=data_dir)

    # Scale bar
    scale_bar = manifest['metadata'].get('scale_bar', False)
    if scale_bar:
        position = scale_bar if isinstance(scale_bar, str) else 'bottom-left'
        _render_scale_bar(ax, extent, position=position)

    # Render borders (must be after all map elements so borders are on top)
    if border_style:
        borders_dir = os.path.join(backgrounds_dir, '../borders/')
        render_border(ax, fig, border_style, borders_dir, dimensions_px, dpi=dpi)

    plt.title(f"{manifest['metadata']['title']} ({manifest['metadata']['year']})")

    # Save and/or Show
    # Don't use bbox_inches='tight' - we want exact dimensions as specified
    plt.savefig(out_file, dpi=dpi)
    print(f"Map saved to {out_file}")

    if not args.no_show:
        try:
            plt.show()
        except Exception:
            print(f"Could not open display. Map saved to file.")

if __name__ == "__main__":
    main()
