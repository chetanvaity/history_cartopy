import logging
import yaml
import cartopy.crs as ccrs
import json
import os
from shapely.geometry import shape

from history_cartopy.styles import *
from history_cartopy.campaign_styles import *
from history_cartopy.territory_styles import *
from history_cartopy.anchor import AnchorCircle
from history_cartopy.icons import render_icon, DEFAULT_ICONSET
from history_cartopy.stylemaps import CITY_LEVELS, EVENT_CONFIG, LABEL_STYLES
from history_cartopy.placement import PlacementManager, PRIORITY

logger = logging.getLogger('history_cartopy.core')


def load_data(gazetteer_path, manifest_path):
    with open(gazetteer_path, 'r') as f:
        gazetteer = yaml.safe_load(f)['locations']

    with open(manifest_path, 'r') as f:
        manifest = yaml.safe_load(f)

    return gazetteer, manifest

# Helper to extract x/y offsets from YAML
def get_offsets(item):
    # Default to 0,0 - no offset
    offset = item.get('offset', [0, 0])
    return offset[0], offset[1]

# All labels
def render_labels(ax, gazetteer, manifest, data_dir=None):
    labels = manifest.get('labels', {})

    # Resolve iconset path
    iconset_name = manifest.get('metadata', {}).get('iconset', DEFAULT_ICONSET)
    iconset_path = os.path.join(data_dir, iconset_name) if data_dir else None

    # Initialize placement manager for overlap detection
    dpp = get_deg_per_pt(ax)
    pm = PlacementManager(dpp)

    # =========================================================================
    # PASS 1: Collect all placement data
    # =========================================================================

    # Collected data for rendering
    city_render_data = []
    river_render_data = []
    region_render_data = []

    # 1a. Collect Cities
    cities = labels.get('cities', [])
    logger.debug(f"Collecting {len(cities)} cities")
    for item in cities:
        name = item['name']
        display = item.get('display_as', name)
        level = item.get('level', 2)

        level_config = CITY_LEVELS.get(level, CITY_LEVELS[2])

        if name not in gazetteer:
            logger.warning(f"City '{name}' not found in gazetteer")
            continue
        lon, lat = gazetteer[name]

        # Create anchor circle for this location
        anchor = AnchorCircle(city_level=level)

        icon_setting = item.get('icon', None)
        has_icon = icon_setting is not False and iconset_path is not None

        if has_icon:
            icon_idx = anchor.add_attachment('icon', preferred_angle=0)
        label_idx = anchor.add_attachment('label', preferred_angle=45)

        manual_ox, manual_oy = get_offsets(item)
        use_manual_offset = not (manual_ox == 0.0 and manual_oy == 0.0)

        anchor.resolve()

        # Calculate offsets
        if use_manual_offset:
            label_ox, label_oy = manual_ox, manual_oy
        else:
            label_ox, label_oy = anchor.get_offset(label_idx)

        icon_ox, icon_oy = 0, 0
        icon_name = None
        if has_icon:
            icon_name = icon_setting if isinstance(icon_setting, str) else level_config['default_icon']
            if icon_name:
                icon_ox, icon_oy = anchor.get_offset(icon_idx)

        # Store for rendering
        city_render_data.append({
            'name': name,
            'display': display,
            'level': level,
            'level_config': level_config,
            'coords': (lon, lat),
            'label_offset': (label_ox, label_oy),
            'icon_name': icon_name,
            'icon_offset': (icon_ox, icon_oy),
        })

        # Track in placement manager
        label_style = LABEL_STYLES.get(level_config['label_style'], {})
        pm.add_label(
            f"city_label_{name}",
            (lon, lat),
            display,
            fontsize=label_style.get('fontsize', 9),
            x_offset_pts=label_ox,
            y_offset_pts=label_oy,
            priority=PRIORITY.get(f'city_level_{level}', 50),
            element_type='city_label'
        )
        pm.add_dot(
            f"city_dot_{name}",
            (lon, lat),
            size_pts=level_config['dot_outer_size'],
            priority=PRIORITY.get(f'city_level_{level}', 50) + 10
        )
        if icon_name:
            pm.add_icon(
                f"city_icon_{name}",
                (lon, lat),
                size_pts=25,
                x_offset_pts=icon_ox,
                y_offset_pts=icon_oy,
                priority=PRIORITY.get(f'city_level_{level}', 50),
                element_type='city_icon'
            )

    # 1b. Collect Rivers
    rivers = labels.get('rivers', [])
    logger.debug(f"Collecting {len(rivers)} rivers")
    for item in rivers:
        lon, lat = item['coords']
        rotation = item.get('rotation')
        if rotation is None and data_dir:
            from history_cartopy.river_alignment import get_river_angle
            rotation = get_river_angle(item['name'], (lon, lat), data_dir)

        river_render_data.append({
            'name': item['name'],
            'coords': (lon, lat),
            'rotation': rotation or 0,
        })

        river_style = LABEL_STYLES.get('river', {})
        pm.add_label(
            f"river_{item['name']}",
            (lon, lat),
            item['name'],
            fontsize=river_style.get('fontsize', 10),
            priority=PRIORITY.get('river', 40),
            element_type='river'
        )

    # 1c. Collect Regions
    for item in labels.get('regions', []):
        lon, lat = item['coords']
        region_render_data.append({
            'name': item['name'],
            'coords': (lon, lat),
            'rotation': item.get('rotation', 0),
        })

        region_style = LABEL_STYLES.get('region', {})
        pm.add_label(
            f"region_{item['name']}",
            (lon, lat),
            item['name'],
            fontsize=region_style.get('fontsize', 20),
            priority=PRIORITY.get('region', 30),
            element_type='region'
        )

    # =========================================================================
    # PASS 2: Detect overlaps
    # =========================================================================
    pm.log_overlaps()

    # =========================================================================
    # PASS 3: Render everything
    # =========================================================================

    # 3a. Render Cities
    for city in city_render_data:
        lon, lat = city['coords']
        level_config = city['level_config']

        # Draw dot
        if level_config['dot_style'] == 'ring':
            ax.plot(lon, lat, marker='o', color='black',
                    markersize=level_config['dot_outer_size'],
                    transform=ccrs.PlateCarree(), zorder=5)
            ax.plot(lon, lat, marker='o', color='white',
                    markersize=level_config['dot_inner_size'],
                    transform=ccrs.PlateCarree(), zorder=6)
        else:
            ax.plot(lon, lat, marker='o', color='black',
                    markersize=level_config['dot_outer_size'],
                    markeredgecolor='white', markeredgewidth=1,
                    transform=ccrs.PlateCarree(), zorder=5)

        # Draw icon
        if city['icon_name']:
            render_icon(ax, lon, lat, city['icon_name'], iconset_path,
                        x_offset=city['icon_offset'][0],
                        y_offset=city['icon_offset'][1])

        # Draw label
        apply_text(ax, lon, lat, city['display'], level_config['label_style'],
                   x_offset=city['label_offset'][0],
                   y_offset=city['label_offset'][1],
                   ha='left', va='top')

    # 3b. Render Rivers
    for river in river_render_data:
        apply_text(ax, river['coords'][0], river['coords'][1],
                   river['name'], 'river', rotation=river['rotation'])

    # 3c. Render Regions
    for region in region_render_data:
        apply_text(ax, region['coords'][0], region['coords'][1],
                   region['name'], 'region', rotation=region['rotation'])

    # 4. Process standalone icons
    if iconset_path:
        for item in manifest.get('icons', []):
            icon_name = item.get('type')
            if not icon_name:
                continue

            # Get coordinates
            if 'coords' in item:
                lon, lat = item['coords']
            elif 'location' in item:
                loc_name = item['location']
                if loc_name not in gazetteer:
                    logger.warning(f"Icon location '{loc_name}' not in gazetteer")
                    continue
                lon, lat = gazetteer[loc_name]
            else:
                continue

            offset = item.get('offset', [0, 0])
            render_icon(ax, lon, lat, icon_name, iconset_path,
                        x_offset=offset[0], y_offset=offset[1])


def _get_city_level_lookup(manifest):
    """Build a dict mapping city names to their levels from manifest."""
    lookup = {}
    for item in manifest.get('labels', {}).get('cities', []):
        name = item.get('name')
        if name:
            lookup[name] = item.get('level', 2)
    return lookup


def _offset_point_toward(p_from, p_toward, offset_deg):
    """
    Offset p_from toward p_toward by offset_deg degrees.
    Returns adjusted (lon, lat).
    """
    import numpy as np
    p1 = np.array(p_from)
    p2 = np.array(p_toward)
    direction = p2 - p1
    dist = np.linalg.norm(direction)
    if dist == 0:
        return p_from
    unit = direction / dist
    return (p1 + unit * offset_deg).tolist()


def render_campaigns(ax, gazetteer, manifest):
    from history_cartopy.styles import get_deg_per_pt

    # Build city level lookup for anchor radius calculation
    city_levels = _get_city_level_lookup(manifest)
    dpp = get_deg_per_pt(ax)

    campaigns = manifest.get('campaigns', [])
    logger.debug(f"Processing {len(campaigns)} campaigns")
    for item in campaigns:
        # 1. Coordinate Lookup: Path can be ['CityName', 'CityName'] or [[lon, lat], [lon, lat]]
        raw_path = item.get('path', [])
        processed_coords = []
        path_city_names = []  # Track which entries are city names

        for p in raw_path:
            if isinstance(p, str):
                # Look up city name in the master gazetteer
                if p in gazetteer:
                    processed_coords.append(gazetteer[p])
                    path_city_names.append(p)
                else:
                    logger.warning(f"Campaign location '{p}' not found in gazetteer")
                    continue
            else:
                # It's already a [lon, lat] list/tuple
                processed_coords.append(p)
                path_city_names.append(None)

        # We need at least a start and end to draw an arrow
        if len(processed_coords) < 2:
            logger.warning("At least 2 points required for a campaign")
            continue

        # 2. Adjust start/end points to anchor circle edges
        p1, p2 = processed_coords[0], processed_coords[-1]
        name1, name2 = path_city_names[0], path_city_names[-1] if len(path_city_names) > 1 else None

        # Offset start point (toward destination)
        if name1 and name1 in city_levels:
            level1 = city_levels[name1]
            radius1 = CITY_LEVELS.get(level1, CITY_LEVELS[2])['anchor_radius']
            offset1_deg = radius1 * dpp
            p1 = _offset_point_toward(p1, p2, offset1_deg)

        # Offset end point (toward source, i.e., away from destination)
        if name2 and name2 in city_levels:
            level2 = city_levels[name2]
            radius2 = CITY_LEVELS.get(level2, CITY_LEVELS[2])['anchor_radius']
            offset2_deg = radius2 * dpp
            p2 = _offset_point_toward(p2, p1, offset2_deg)

        adjusted_coords = [p1, p2]

        # 3. Extract specific parameters for this campaign
        label_top = item.get('label_above', "")
        label_bot = item.get('label_below', "")
        style = item.get('style', 'invasion')
        curvature = item.get('rad', 0.3)  # Default curvature

        # 4. Call the style function with adjusted coordinates
        apply_campaign(
            ax,
            points=adjusted_coords,
            label_above=label_top,
            label_below=label_bot,
            style_key=style,
            rad=curvature
        )


# Territories
def render_territories(ax, manifest, polygons_dir):
    if 'territories' not in manifest:
        logger.debug("No territories to render")
        return

    territories = manifest['territories']
    logger.debug(f"Processing {len(territories)} territories")
    for entry in territories:
        file_name = entry.get('file')
        style_key = entry.get('style', 'kingdom1')
        render_type = entry.get('type', 'fuzzy_fill') # Default type

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
                elif render_type == 'edge-tint-fill':
                    apply_edge_tint_fill_territory(ax, smooth_geom, style_key)
                else:
                    logger.warning(f"Unknown territory type: {render_type}")

        except (KeyError, TypeError) as e:
            logger.error(f"{file_name} is not a valid GeoJSON FeatureCollection: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading {file_name}: {e}")


def render_events(ax, gazetteer, manifest, data_dir=None):
    """Render event labels with optional icon, text above and date below."""
    # Resolve iconset path
    iconset_name = manifest.get('metadata', {}).get('iconset', DEFAULT_ICONSET)
    iconset_path = os.path.join(data_dir, iconset_name) if data_dir else None

    events = manifest.get('events', [])
    logger.debug(f"Processing {len(events)} events")
    for item in events:
        text = item.get('text', '')
        date = item.get('date', '')
        icon_name = item.get('icon')

        # Get coordinates - either direct coords or from gazetteer
        if 'coords' in item:
            lon, lat = item['coords']
        elif 'location' in item:
            loc_name = item['location']
            if loc_name not in gazetteer:
                logger.warning(f"Event location '{loc_name}' not found in gazetteer")
                continue
            lon, lat = gazetteer[loc_name]
        else:
            logger.warning(f"Event '{text}' has no coords or location")
            continue

        # Optional rotation
        rotation = item.get('rotation', 0)

        # Calculate text offsets
        if icon_name and iconset_path:
            # With icon: use anchor circle for text placement
            import math
            anchor_radius = EVENT_CONFIG['anchor_radius']
            angle_deg = item.get('label_angle', 90)  # Default: East/right
            angle_rad = math.radians(90 - angle_deg)
            label_ox = anchor_radius * math.cos(angle_rad)
            label_oy = anchor_radius * math.sin(angle_rad)

            # Pick text alignment based on angle quadrant
            # Normalize angle to 0-360
            norm_angle = angle_deg % 360
            if 45 <= norm_angle < 135:
                ha = 'left'   # East: text extends right
            elif 225 <= norm_angle < 315:
                ha = 'right'  # West: text extends left
            else:
                ha = 'center' # North/South: text centered

            # Render icon at the location
            icon_centered = item.get('icon_centered', False)
            render_icon(ax, lon, lat, icon_name, iconset_path, centered=icon_centered)

            # Render text/date offset from icon
            if text:
                apply_text(ax, lon, lat, text, 'event_text',
                           x_offset=label_ox, y_offset=label_oy + 2,
                           rotation=rotation, ha=ha, va='bottom')
            if date:
                apply_text(ax, lon, lat, date, 'event_date',
                           x_offset=label_ox, y_offset=label_oy - 2,
                           rotation=rotation, ha=ha, va='top')
        else:
            # No icon: render text/date centered at location
            if text:
                apply_text(ax, lon, lat, text, 'event_text',
                           y_offset=3, rotation=rotation, ha='center', va='bottom')
            if date:
                apply_text(ax, lon, lat, date, 'event_date',
                           y_offset=-3, rotation=rotation, ha='center', va='top')
