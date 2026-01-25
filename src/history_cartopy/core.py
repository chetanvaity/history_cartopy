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
from history_cartopy.placement import PlacementManager, PlacementElement, LabelCandidate, PRIORITY

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


def collect_labels(gazetteer, manifest, placement_manager, data_dir=None):
    """
    Collect all label data without rendering.

    Phase 1 of the three-phase flow: Collect → Resolve → Render

    Returns:
        (city_candidates, river_data, region_data, city_render_data)
        - city_candidates: list of LabelCandidate with 8 positions each
        - river_data: list of dicts with river render info (fixed positions)
        - region_data: list of dicts with region render info (fixed positions)
        - city_render_data: list of dicts with city render info
    """
    from history_cartopy.anchor import AnchorCircle

    labels = manifest.get('labels', {})
    pm = placement_manager

    # Resolve iconset path
    iconset_name = manifest.get('metadata', {}).get('iconset', DEFAULT_ICONSET)
    iconset_path = os.path.join(data_dir, iconset_name) if data_dir else None

    city_candidates = []
    city_render_data = []
    river_data = []
    region_data = []

    # 1. Collect Cities
    cities = labels.get('cities', [])
    logger.debug(f"Collecting {len(cities)} cities for candidate generation")

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

        # Calculate icon offset (fixed position)
        icon_ox, icon_oy = 0, 0
        icon_name = None
        if has_icon:
            icon_name = icon_setting if isinstance(icon_setting, str) else level_config['default_icon']
            if icon_name:
                icon_ox, icon_oy = anchor.get_offset(icon_idx)

        # Get label style info
        label_style = LABEL_STYLES.get(level_config['label_style'], {})
        fontsize = label_style.get('fontsize', 9)
        city_group = f"city_{name}"
        # Separate priorities: dots/icons are fixed (high), labels can move (lower)
        dot_priority = PRIORITY.get(f'city_level_{level}', 60)
        label_priority = PRIORITY.get(f'city_label_{level}', 44)

        # Store render data
        city_render_data.append({
            'name': name,
            'display': display,
            'level': level,
            'level_config': level_config,
            'coords': (lon, lat),
            'icon_name': icon_name,
            'icon_offset': (icon_ox, icon_oy),
            'use_manual_offset': use_manual_offset,
            'manual_offset': (manual_ox, manual_oy),
            'fontsize': fontsize,
            'group': city_group,
        })

        # If manual offset, don't generate candidates - use fixed position
        if use_manual_offset:
            # Create single-position candidate with manual offset
            element = pm.add_label(
                f"city_label_{name}",
                (lon, lat),
                display,
                fontsize=fontsize,
                x_offset_pts=manual_ox,
                y_offset_pts=manual_oy,
                priority=label_priority,
                element_type='city_label',
                group=city_group,
            )
            # Remove from pm.elements - we'll add back during resolve
            pm.remove(f"city_label_{name}")

            candidate = LabelCandidate(
                id=f"city_label_{name}",
                element_type='city_label',
                priority=label_priority,
                group=city_group,
                positions=[element],
            )
            city_candidates.append(candidate)
        else:
            # Generate candidate positions at multiple distance tiers
            # Tier 1: 1x radius (8 positions) - preferred, closest to city
            # Tier 2: 1.5x radius (8 positions) - fallback
            # Tier 3: 2x radius (8 positions) - last resort
            positions = []
            distance_multipliers = [1.0, 1.5, 2.0]

            for multiplier in distance_multipliers:
                # gap_pts adds to the base radius
                extra_gap = anchor.radius * (multiplier - 1.0)
                candidate_offsets = anchor.get_candidate_offsets(gap_pts=extra_gap, text_height_pts=fontsize)

                for pos_name, x_off, y_off, ha, va in candidate_offsets:
                    tier_suffix = f"_t{int(multiplier*10)}"  # e.g., _t10, _t15, _t20
                    element = pm.add_label(
                        f"city_label_{name}_{pos_name}{tier_suffix}",
                        (lon, lat),
                        display,
                        fontsize=fontsize,
                        x_offset_pts=x_off,
                        y_offset_pts=y_off,
                        priority=label_priority,
                        element_type='city_label',
                        group=city_group,
                    )
                    element.id = f"city_label_{name}"
                    # Store alignment info for rendering
                    element.ha = ha
                    element.va = va
                    pm.remove(f"city_label_{name}_{pos_name}{tier_suffix}")
                    positions.append(element)

            candidate = LabelCandidate(
                id=f"city_label_{name}",
                element_type='city_label',
                priority=label_priority,
                group=city_group,
                positions=positions,
            )
            city_candidates.append(candidate)

        # Add fixed elements (dots, icons) - these don't move
        pm.add_dot(
            f"city_dot_{name}",
            (lon, lat),
            size_pts=level_config['dot_outer_size'],
            priority=dot_priority,
            group=city_group,
        )
        if icon_name:
            pm.add_icon(
                f"city_icon_{name}",
                (lon, lat),
                size_pts=25,
                x_offset_pts=icon_ox,
                y_offset_pts=icon_oy,
                priority=dot_priority,
                element_type='city_icon',
                group=city_group,
            )

    # 2. Collect Rivers (fixed positions - no candidates)
    rivers = labels.get('rivers', [])
    logger.debug(f"Collecting {len(rivers)} rivers")
    for item in rivers:
        lon, lat = item['coords']
        rotation = item.get('rotation')
        if rotation is None and data_dir:
            from history_cartopy.river_alignment import get_river_angle
            rotation = get_river_angle(item['name'], (lon, lat), data_dir)

        river_data.append({
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

    # 3. Collect Regions (fixed positions - no candidates)
    for item in labels.get('regions', []):
        lon, lat = item['coords']
        region_data.append({
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

    return city_candidates, river_data, region_data, city_render_data


# All labels
def render_labels(ax, gazetteer, manifest, placement_manager, data_dir=None):
    labels = manifest.get('labels', {})

    # Resolve iconset path
    iconset_name = manifest.get('metadata', {}).get('iconset', DEFAULT_ICONSET)
    iconset_path = os.path.join(data_dir, iconset_name) if data_dir else None

    # Use provided placement manager
    pm = placement_manager

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
        city_group = f"city_{name}"
        pm.add_label(
            f"city_label_{name}",
            (lon, lat),
            display,
            fontsize=label_style.get('fontsize', 9),
            x_offset_pts=label_ox,
            y_offset_pts=label_oy,
            priority=PRIORITY.get(f'city_level_{level}', 50),
            element_type='city_label',
            group=city_group,
        )
        pm.add_dot(
            f"city_dot_{name}",
            (lon, lat),
            size_pts=level_config['dot_outer_size'],
            priority=PRIORITY.get(f'city_level_{level}', 50) + 10,
            group=city_group,
        )
        if icon_name:
            pm.add_icon(
                f"city_icon_{name}",
                (lon, lat),
                size_pts=25,
                x_offset_pts=icon_ox,
                y_offset_pts=icon_oy,
                priority=PRIORITY.get(f'city_level_{level}', 50),
                element_type='city_icon',
                group=city_group,
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
    # PASS 2: Render everything (overlap detection happens after all rendering)
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


def render_labels_resolved(ax, city_render_data, river_data, region_data,
                           resolved_positions, gazetteer, manifest, data_dir=None):
    """
    Render labels using pre-resolved positions.

    Phase 3 of the three-phase flow: Collect → Resolve → Render

    Args:
        ax: matplotlib axes
        city_render_data: city render data from collect_labels
        river_data: river render data from collect_labels
        region_data: region render data from collect_labels
        resolved_positions: dict from resolve_greedy() mapping label IDs to PlacementElements
        manifest: the manifest for iconset lookup
        data_dir: data directory path
    """
    # Resolve iconset path
    iconset_name = manifest.get('metadata', {}).get('iconset', DEFAULT_ICONSET)
    iconset_path = os.path.join(data_dir, iconset_name) if data_dir else None

    # Render Cities
    for city in city_render_data:
        lon, lat = city['coords']
        level_config = city['level_config']

        # Draw dot (fixed position)
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

        # Draw icon (fixed position)
        if city['icon_name']:
            render_icon(ax, lon, lat, city['icon_name'], iconset_path,
                        x_offset=city['icon_offset'][0],
                        y_offset=city['icon_offset'][1])

        # Draw label at resolved position
        label_id = f"city_label_{city['name']}"
        if label_id in resolved_positions:
            resolved = resolved_positions[label_id]
            # The resolved element stores offset in degrees, but apply_text expects points
            # We need to convert back, or use the offset stored on the element
            # Actually, looking at PlacementElement, offset is stored in degrees
            # But we track the pts offset in the positions list
            # Let's get the offset from the PlacementElement
            # offset is in degrees, so we need to convert to points
            # But actually we stored x_offset_pts and y_offset_pts when creating the element
            # The PlacementElement stores (x_offset_deg, y_offset_deg)
            # We need to convert back: pts = deg / dpp
            # But we don't have dpp here... let's think about this
            #
            # Actually, looking at the code again, the offset in PlacementElement is in degrees
            # But apply_text expects points. We need to figure out the conversion.
            #
            # Looking at add_label():
            #   x_offset_deg = x_offset_pts * self.dpp
            # So to convert back: x_offset_pts = x_offset_deg / dpp
            #
            # But we don't have access to dpp here. We could:
            # 1. Pass dpp to this function
            # 2. Store the pts offset on the PlacementElement or in a separate field
            #
            # Let me look at how we can get this info. The cleanest approach is to
            # store the point offsets somewhere. Since we're generating candidates,
            # we can store both.
            #
            # Actually, looking more carefully at the collect_labels function I wrote,
            # we create PlacementElements with add_label() which takes pts and converts to deg.
            # The PlacementElement.offset is stored in degrees.
            #
            # For rendering, we need points. We could:
            # - Compute offset from the bbox (which is in degrees) back to points
            # - Or store point offsets in some metadata
            # - Or compute dpp from the ax
            #
            # Let's compute dpp from ax and convert back.
            from history_cartopy.styles import get_deg_per_pt
            dpp = get_deg_per_pt(ax)
            x_offset_pts = resolved.offset[0] / dpp
            y_offset_pts = resolved.offset[1] / dpp

            # Use alignment from resolved element (stored during candidate generation)
            ha = getattr(resolved, 'ha', 'left')
            va = getattr(resolved, 'va', 'top')

            apply_text(ax, lon, lat, city['display'], level_config['label_style'],
                       x_offset=x_offset_pts, y_offset=y_offset_pts,
                       ha=ha, va=va)
        else:
            # Fallback: use manual offset if specified, otherwise default position
            if city['use_manual_offset']:
                x_off, y_off = city['manual_offset']
            else:
                # Default to first candidate position (NE)
                x_off, y_off = 5, 5  # Default offset
            apply_text(ax, lon, lat, city['display'], level_config['label_style'],
                       x_offset=x_off, y_offset=y_off,
                       ha='left', va='bottom')  # NE position default

    # Render Rivers (fixed positions)
    for river in river_data:
        apply_text(ax, river['coords'][0], river['coords'][1],
                   river['name'], 'river', rotation=river['rotation'])

    # Render Regions (fixed positions)
    for region in region_data:
        apply_text(ax, region['coords'][0], region['coords'][1],
                   region['name'], 'region', rotation=region['rotation'])

    # Render standalone icons
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


def collect_events(gazetteer, manifest, placement_manager, data_dir=None):
    """
    Collect all event label data without rendering.

    Phase 1 of the three-phase flow: Collect → Resolve → Render

    Returns:
        (event_candidates, event_render_data)
        - event_candidates: list of LabelCandidate for event labels (8 positions each)
        - event_render_data: list of dicts with event render info
    """
    import math
    from history_cartopy.anchor import AnchorCircle, POSITION_ANGLES, POSITION_PRIORITY

    pm = placement_manager

    # Resolve iconset path
    iconset_name = manifest.get('metadata', {}).get('iconset', DEFAULT_ICONSET)
    iconset_path = os.path.join(data_dir, iconset_name) if data_dir else None

    event_candidates = []
    event_render_data = []

    events = manifest.get('events', [])
    logger.debug(f"Collecting {len(events)} events for candidate generation")

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

        # Create event ID and group
        event_id = text or date or f"event_{lon}_{lat}"
        event_group = f"event_{event_id}"
        priority = PRIORITY.get('event_label', 60)

        # Store render data
        has_icon = icon_name and iconset_path
        event_render_data.append({
            'event_id': event_id,
            'text': text,
            'date': date,
            'coords': (lon, lat),
            'rotation': rotation,
            'icon_name': icon_name if has_icon else None,
            'icon_centered': item.get('icon_centered', False),
            'group': event_group,
            'has_icon': has_icon,
        })

        # Add fixed icon element if present
        if has_icon:
            pm.add_icon(
                f"event_icon_{event_id}",
                (lon, lat),
                size_pts=25,
                priority=PRIORITY.get('event_icon', 90),
                element_type='event_icon',
                group=event_group,
            )

            # Generate 8 candidate positions for text label
            anchor_radius = EVENT_CONFIG['anchor_radius']

            if text:
                text_positions = []
                fontsize = LABEL_STYLES.get('event_text', {}).get('fontsize', 9)

                for pos_name in POSITION_PRIORITY:
                    angle_deg = POSITION_ANGLES[pos_name]
                    angle_rad = math.radians(90 - angle_deg)
                    x_off = anchor_radius * math.cos(angle_rad)
                    y_off = anchor_radius * math.sin(angle_rad) + 2  # +2 for text above

                    # Create PlacementElement for this position
                    element = pm.add_label(
                        f"event_text_{event_id}_{pos_name}",
                        (lon, lat),
                        text,
                        fontsize=fontsize,
                        x_offset_pts=x_off,
                        y_offset_pts=y_off,
                        priority=priority,
                        element_type='event_label',
                        group=event_group,
                    )
                    element.id = f"event_text_{event_id}"
                    pm.remove(f"event_text_{event_id}_{pos_name}")
                    text_positions.append(element)

                event_candidates.append(LabelCandidate(
                    id=f"event_text_{event_id}",
                    element_type='event_label',
                    priority=priority,
                    group=event_group,
                    positions=text_positions,
                ))

            if date:
                date_positions = []
                fontsize = LABEL_STYLES.get('event_date', {}).get('fontsize', 8)

                for pos_name in POSITION_PRIORITY:
                    angle_deg = POSITION_ANGLES[pos_name]
                    angle_rad = math.radians(90 - angle_deg)
                    x_off = anchor_radius * math.cos(angle_rad)
                    y_off = anchor_radius * math.sin(angle_rad) - 2  # -2 for date below

                    element = pm.add_label(
                        f"event_date_{event_id}_{pos_name}",
                        (lon, lat),
                        date,
                        fontsize=fontsize,
                        x_offset_pts=x_off,
                        y_offset_pts=y_off,
                        priority=priority,
                        element_type='event_label',
                        group=event_group,
                    )
                    element.id = f"event_date_{event_id}"
                    pm.remove(f"event_date_{event_id}_{pos_name}")
                    date_positions.append(element)

                event_candidates.append(LabelCandidate(
                    id=f"event_date_{event_id}",
                    element_type='event_label',
                    priority=priority,
                    group=event_group,
                    positions=date_positions,
                ))
        else:
            # No icon - fixed positions at center
            if text:
                element = pm.add_label(
                    f"event_text_{event_id}",
                    (lon, lat),
                    text,
                    fontsize=LABEL_STYLES.get('event_text', {}).get('fontsize', 9),
                    y_offset_pts=3,
                    priority=priority,
                    element_type='event_label',
                    group=event_group,
                )
                pm.remove(f"event_text_{event_id}")
                event_candidates.append(LabelCandidate(
                    id=f"event_text_{event_id}",
                    element_type='event_label',
                    priority=priority,
                    group=event_group,
                    positions=[element],  # Single fixed position
                ))

            if date:
                element = pm.add_label(
                    f"event_date_{event_id}",
                    (lon, lat),
                    date,
                    fontsize=LABEL_STYLES.get('event_date', {}).get('fontsize', 8),
                    y_offset_pts=-3,
                    priority=priority,
                    element_type='event_label',
                    group=event_group,
                )
                pm.remove(f"event_date_{event_id}")
                event_candidates.append(LabelCandidate(
                    id=f"event_date_{event_id}",
                    element_type='event_label',
                    priority=priority,
                    group=event_group,
                    positions=[element],  # Single fixed position
                ))

    return event_candidates, event_render_data


def render_events_resolved(ax, event_render_data, resolved_positions, data_dir=None, manifest=None):
    """
    Render events using pre-resolved label positions.

    Phase 3 of the three-phase flow: Collect → Resolve → Render

    Args:
        ax: matplotlib axes
        event_render_data: event render data from collect_events
        resolved_positions: dict from resolve_greedy() mapping label IDs to PlacementElements
        data_dir: data directory path
        manifest: the manifest for iconset lookup
    """
    from history_cartopy.styles import get_deg_per_pt

    # Resolve iconset path
    if manifest:
        iconset_name = manifest.get('metadata', {}).get('iconset', DEFAULT_ICONSET)
        iconset_path = os.path.join(data_dir, iconset_name) if data_dir else None
    else:
        iconset_path = None

    dpp = get_deg_per_pt(ax)

    for event in event_render_data:
        lon, lat = event['coords']
        event_id = event['event_id']
        rotation = event['rotation']

        # Render icon if present (fixed position)
        if event['icon_name'] and iconset_path:
            render_icon(ax, lon, lat, event['icon_name'], iconset_path,
                        centered=event['icon_centered'])

        # Render text at resolved position
        if event['text']:
            text_id = f"event_text_{event_id}"
            if text_id in resolved_positions:
                resolved = resolved_positions[text_id]
                x_offset_pts = resolved.offset[0] / dpp
                y_offset_pts = resolved.offset[1] / dpp

                # Determine ha based on angle
                ha = _get_event_ha_from_offset(x_offset_pts, y_offset_pts)

                apply_text(ax, lon, lat, event['text'], 'event_text',
                           x_offset=x_offset_pts, y_offset=y_offset_pts,
                           rotation=rotation, ha=ha, va='bottom')
            else:
                # Fallback
                if event['has_icon']:
                    apply_text(ax, lon, lat, event['text'], 'event_text',
                               x_offset=15, y_offset=2,
                               rotation=rotation, ha='left', va='bottom')
                else:
                    apply_text(ax, lon, lat, event['text'], 'event_text',
                               y_offset=3, rotation=rotation, ha='center', va='bottom')

        # Render date at resolved position
        if event['date']:
            date_id = f"event_date_{event_id}"
            if date_id in resolved_positions:
                resolved = resolved_positions[date_id]
                x_offset_pts = resolved.offset[0] / dpp
                y_offset_pts = resolved.offset[1] / dpp

                ha = _get_event_ha_from_offset(x_offset_pts, y_offset_pts)

                apply_text(ax, lon, lat, event['date'], 'event_date',
                           x_offset=x_offset_pts, y_offset=y_offset_pts,
                           rotation=rotation, ha=ha, va='top')
            else:
                # Fallback
                if event['has_icon']:
                    apply_text(ax, lon, lat, event['date'], 'event_date',
                               x_offset=15, y_offset=-2,
                               rotation=rotation, ha='left', va='top')
                else:
                    apply_text(ax, lon, lat, event['date'], 'event_date',
                               y_offset=-3, rotation=rotation, ha='center', va='top')


def _get_event_ha_from_offset(x_offset, y_offset):
    """Determine horizontal alignment based on offset position."""
    import math
    if abs(x_offset) < 0.1:
        return 'center'
    elif x_offset > 0:
        return 'left'
    else:
        return 'right'


def _get_city_level_lookup(manifest):
    """Build a dict mapping city names to their levels from manifest."""
    lookup = {}
    for item in manifest.get('labels', {}).get('cities', []):
        name = item.get('name')
        if name:
            lookup[name] = item.get('level', 2)
    return lookup


def _offset_point_toward_internal(p_from, p_toward, offset_deg):
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


def collect_campaigns(gazetteer, manifest, placement_manager):
    """
    Collect all campaign data without rendering.

    Phase 1 of the three-phase flow: Collect → Resolve → Render

    Returns:
        (campaign_candidates, campaign_render_data)
        - campaign_candidates: list of LabelCandidate for campaign labels
        - campaign_render_data: list of dicts with campaign render info
    """
    from history_cartopy.styles import get_deg_per_pt
    from history_cartopy.campaign_styles import _get_multistop_geometry, _get_label_candidates

    pm = placement_manager
    city_levels = _get_city_level_lookup(manifest)

    # We need dpp but don't have ax yet - we'll get it from pm
    dpp = pm.dpp

    campaign_candidates = []
    campaign_render_data = []

    campaigns = manifest.get('campaigns', [])
    logger.debug(f"Collecting {len(campaigns)} campaigns for candidate generation")

    for idx, item in enumerate(campaigns):
        # 1. Coordinate Lookup
        raw_path = item.get('path', [])
        processed_coords = []
        path_city_names = []

        for p in raw_path:
            if isinstance(p, str):
                if p in gazetteer:
                    processed_coords.append(gazetteer[p])
                    path_city_names.append(p)
                else:
                    logger.warning(f"Campaign location '{p}' not found in gazetteer")
                    continue
            else:
                processed_coords.append(list(p))
                path_city_names.append(None)

        if len(processed_coords) < 2:
            logger.warning("At least 2 points required for a campaign")
            continue

        # 2. Adjust start/end points to anchor circle edges
        name1 = path_city_names[0]
        name2 = path_city_names[-1] if len(path_city_names) > 1 else None

        # Offset arrows from cities - use larger multiplier to leave room for labels
        arrow_gap_multiplier = 2.0  # Start at 2x, can increase up to 4x if needed  # Push arrows further from city centers

        if name1 and name1 in city_levels:
            level1 = city_levels[name1]
            radius1 = CITY_LEVELS.get(level1, CITY_LEVELS[2])['anchor_radius']
            next_pt = processed_coords[1] if len(processed_coords) > 1 else processed_coords[0]
            processed_coords[0] = _offset_point_toward_internal(
                processed_coords[0], next_pt, radius1 * arrow_gap_multiplier * dpp
            )

        if name2 and name2 in city_levels:
            level2 = city_levels[name2]
            radius2 = CITY_LEVELS.get(level2, CITY_LEVELS[2])['anchor_radius']
            prev_pt = processed_coords[-2] if len(processed_coords) > 1 else processed_coords[-1]
            processed_coords[-1] = _offset_point_toward_internal(
                processed_coords[-1], prev_pt, radius2 * arrow_gap_multiplier * dpp
            )

        # 3. Extract parameters
        label_above = item.get('label_above', "")
        label_below = item.get('label_below', "")
        style_key = item.get('style', 'invasion')
        path_type = item.get('path_type', 'spline')
        arrows = item.get('arrows', 'final')

        # 4. Compute geometry
        geometry = _get_multistop_geometry(processed_coords, path_type=path_type)
        if geometry is None:
            logger.warning(f"Failed to compute geometry for campaign {idx}")
            continue

        campaign_group = f"campaign_{idx}"

        # 5. Add arrow path to placement manager (fixed element)
        full_path = geometry['full_path']
        pm.add_campaign_arrow(
            f"campaign_arrow_{idx}",
            path=full_path,
            linewidth_pts=2.5,
            priority=PRIORITY.get('campaign_arrow', 55),
            group=campaign_group,
        )

        # 6. Store render data
        campaign_render_data.append({
            'idx': idx,
            'geometry': geometry,
            'label_above': label_above,
            'label_below': label_below,
            'style_key': style_key,
            'arrows': arrows,
            'group': campaign_group,
        })

        # 7. Generate label candidates from segments
        if label_above or label_below:
            candidates = _get_label_candidates(geometry)
            fontsize_above = LABEL_STYLES.get('campaign_above', {}).get('fontsize', 9)
            fontsize_below = LABEL_STYLES.get('campaign_below', {}).get('fontsize', 8)
            priority = PRIORITY.get('campaign_label', 45)

            if label_above:
                above_positions = []
                for seg_idx, candidate in enumerate(candidates):
                    element = pm.add_campaign_label(
                        id=f"campaign_{idx}_above_seg{seg_idx}",
                        coords=tuple(candidate['midpoint']),
                        text=label_above,
                        fontsize=fontsize_above,
                        rotation=candidate['angle'],
                        normal=tuple(candidate['normal']),
                        group=campaign_group,
                    )
                    element.id = f"campaign_{idx}_above"
                    # Store segment info for rendering
                    element.segment_idx = seg_idx
                    pm.remove(f"campaign_{idx}_above_seg{seg_idx}")
                    above_positions.append(element)

                campaign_candidates.append(LabelCandidate(
                    id=f"campaign_{idx}_above",
                    element_type='campaign_label',
                    priority=priority,
                    group=campaign_group,
                    positions=above_positions,
                ))

            if label_below:
                below_positions = []
                for seg_idx, candidate in enumerate(candidates):
                    element = pm.add_campaign_label(
                        id=f"campaign_{idx}_below_seg{seg_idx}",
                        coords=tuple(candidate['midpoint']),
                        text=label_below,
                        fontsize=fontsize_below,
                        rotation=candidate['angle'],
                        normal=(-candidate['normal'][0], -candidate['normal'][1]),
                        group=campaign_group,
                    )
                    element.id = f"campaign_{idx}_below"
                    element.segment_idx = seg_idx
                    pm.remove(f"campaign_{idx}_below_seg{seg_idx}")
                    below_positions.append(element)

                campaign_candidates.append(LabelCandidate(
                    id=f"campaign_{idx}_below",
                    element_type='campaign_label',
                    priority=priority,
                    group=campaign_group,
                    positions=below_positions,
                ))

    return campaign_candidates, campaign_render_data


def render_campaigns_resolved(ax, campaign_render_data, resolved_positions):
    """
    Render campaigns using pre-resolved label positions.

    Phase 3 of the three-phase flow: Collect → Resolve → Render

    Args:
        ax: matplotlib axes
        campaign_render_data: campaign render data from collect_campaigns
        resolved_positions: dict from resolve_greedy() mapping label IDs to PlacementElements
    """
    from history_cartopy.campaign_styles import apply_campaign, _get_label_candidates

    for campaign in campaign_render_data:
        idx = campaign['idx']
        geometry = campaign['geometry']
        label_above = campaign['label_above']
        label_below = campaign['label_below']
        style_key = campaign['style_key']
        arrows = campaign['arrows']

        # Determine which segment to use for labels
        # Default to first (longest) segment
        label_segment = geometry['segments'][0]

        # Check if we have resolved positions for the labels
        above_id = f"campaign_{idx}_above"
        below_id = f"campaign_{idx}_below"

        # Get the resolved segment index
        resolved_seg_idx = None
        if above_id in resolved_positions:
            resolved = resolved_positions[above_id]
            if hasattr(resolved, 'segment_idx'):
                resolved_seg_idx = resolved.segment_idx
        elif below_id in resolved_positions:
            resolved = resolved_positions[below_id]
            if hasattr(resolved, 'segment_idx'):
                resolved_seg_idx = resolved.segment_idx

        # Use resolved segment if available
        if resolved_seg_idx is not None:
            candidates = _get_label_candidates(geometry)
            if resolved_seg_idx < len(candidates):
                label_segment = candidates[resolved_seg_idx]

        # Render campaign with resolved label segment
        apply_campaign(
            ax,
            geometry=geometry,
            label_segment=label_segment,
            label_above=label_above,
            label_below=label_below,
            style_key=style_key,
            arrows=arrows,
        )


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


def render_campaigns(ax, gazetteer, manifest, placement_manager):
    from history_cartopy.styles import get_deg_per_pt
    from history_cartopy.campaign_styles import (
        _get_multistop_geometry, _get_label_candidates, apply_campaign
    )
    from history_cartopy.stylemaps import LABEL_STYLES

    # Build city level lookup for anchor radius calculation
    city_levels = _get_city_level_lookup(manifest)
    dpp = get_deg_per_pt(ax)
    pm = placement_manager

    campaigns = manifest.get('campaigns', [])
    logger.debug(f"Processing {len(campaigns)} campaigns")
    for idx, item in enumerate(campaigns):
        # 1. Coordinate Lookup
        raw_path = item.get('path', [])
        processed_coords = []
        path_city_names = []

        for p in raw_path:
            if isinstance(p, str):
                if p in gazetteer:
                    processed_coords.append(gazetteer[p])
                    path_city_names.append(p)
                else:
                    logger.warning(f"Campaign location '{p}' not found in gazetteer")
                    continue
            else:
                processed_coords.append(list(p))
                path_city_names.append(None)

        if len(processed_coords) < 2:
            logger.warning("At least 2 points required for a campaign")
            continue

        # 2. Adjust start/end points to anchor circle edges
        name1 = path_city_names[0]
        name2 = path_city_names[-1] if len(path_city_names) > 1 else None

        # Offset arrows from cities - use larger multiplier to leave room for labels
        arrow_gap_multiplier = 2.0  # Start at 2x, can increase up to 4x if needed

        if name1 and name1 in city_levels:
            level1 = city_levels[name1]
            radius1 = CITY_LEVELS.get(level1, CITY_LEVELS[2])['anchor_radius']
            next_pt = processed_coords[1] if len(processed_coords) > 1 else processed_coords[0]
            processed_coords[0] = _offset_point_toward(
                processed_coords[0], next_pt, radius1 * arrow_gap_multiplier * dpp
            )

        if name2 and name2 in city_levels:
            level2 = city_levels[name2]
            radius2 = CITY_LEVELS.get(level2, CITY_LEVELS[2])['anchor_radius']
            prev_pt = processed_coords[-2] if len(processed_coords) > 1 else processed_coords[-1]
            processed_coords[-1] = _offset_point_toward(
                processed_coords[-1], prev_pt, radius2 * arrow_gap_multiplier * dpp
            )

        # 3. Extract parameters
        label_above = item.get('label_above', "")
        label_below = item.get('label_below', "")
        style_key = item.get('style', 'invasion')
        path_type = item.get('path_type', 'spline')
        arrows = item.get('arrows', 'final')

        # 4. Compute geometry
        geometry = _get_multistop_geometry(processed_coords, path_type=path_type)
        if geometry is None:
            logger.warning(f"Failed to compute geometry for campaign {idx}")
            continue

        # 5. Find best segment for labels (longest that doesn't overlap)
        label_segment = geometry['segments'][0]  # Default to longest (first after sort)

        if label_above or label_below:
            candidates = _get_label_candidates(geometry)
            fontsize_above = LABEL_STYLES.get('campaign_above', {}).get('fontsize', 9)
            fontsize_below = LABEL_STYLES.get('campaign_below', {}).get('fontsize', 8)
            campaign_group = f"campaign_{idx}"

            for candidate in candidates:
                # Check if this segment's labels would overlap
                overlaps = False

                if label_above:
                    test_elem = pm.add_campaign_label(
                        id=f"_test_above_{idx}",
                        coords=tuple(candidate['midpoint']),
                        text=label_above,
                        fontsize=fontsize_above,
                        rotation=candidate['angle'],
                        normal=tuple(candidate['normal']),
                        group=campaign_group,
                    )
                    if pm.would_overlap(test_elem):
                        overlaps = True
                    pm.remove(f"_test_above_{idx}")

                if label_below and not overlaps:
                    test_elem = pm.add_campaign_label(
                        id=f"_test_below_{idx}",
                        coords=tuple(candidate['midpoint']),
                        text=label_below,
                        fontsize=fontsize_below,
                        rotation=candidate['angle'],
                        normal=(-candidate['normal'][0], -candidate['normal'][1]),
                        group=campaign_group,
                    )
                    if pm.would_overlap(test_elem):
                        overlaps = True
                    pm.remove(f"_test_below_{idx}")

                if not overlaps:
                    label_segment = candidate
                    break
            else:
                # All segments overlap - use longest anyway
                label_segment = candidates[0]
                logger.debug(f"Campaign {idx}: all label positions overlap, using longest segment")

            # Add final label placements
            if label_above:
                pm.add_campaign_label(
                    id=f"campaign_{idx}_above",
                    coords=tuple(label_segment['midpoint']),
                    text=label_above,
                    fontsize=fontsize_above,
                    rotation=label_segment['angle'],
                    normal=tuple(label_segment['normal']),
                    group=campaign_group,
                )
            if label_below:
                pm.add_campaign_label(
                    id=f"campaign_{idx}_below",
                    coords=tuple(label_segment['midpoint']),
                    text=label_below,
                    fontsize=fontsize_below,
                    rotation=label_segment['angle'],
                    normal=(-label_segment['normal'][0], -label_segment['normal'][1]),
                    group=campaign_group,
                )

        # 6. Render campaign
        apply_campaign(
            ax,
            geometry=geometry,
            label_segment=label_segment,
            label_above=label_above,
            label_below=label_below,
            style_key=style_key,
            arrows=arrows,
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


def render_events(ax, gazetteer, manifest, placement_manager, data_dir=None):
    """Render event labels with optional icon, text above and date below."""
    # Resolve iconset path
    iconset_name = manifest.get('metadata', {}).get('iconset', DEFAULT_ICONSET)
    iconset_path = os.path.join(data_dir, iconset_name) if data_dir else None
    pm = placement_manager

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

        # Create event group for placement tracking
        event_id = text or date or f"event_{lon}_{lat}"
        event_group = f"event_{event_id}"

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

            # Track icon in placement manager
            pm.add_icon(
                f"event_icon_{event_id}",
                (lon, lat),
                size_pts=25,
                priority=PRIORITY.get('event_icon', 90),
                element_type='event_icon',
                group=event_group,
            )

            # Render icon at the location
            icon_centered = item.get('icon_centered', False)
            render_icon(ax, lon, lat, icon_name, iconset_path, centered=icon_centered)

            # Track and render text/date offset from icon
            if text:
                pm.add_label(
                    f"event_text_{event_id}",
                    (lon, lat),
                    text,
                    fontsize=LABEL_STYLES.get('event_text', {}).get('fontsize', 9),
                    x_offset_pts=label_ox,
                    y_offset_pts=label_oy + 2,
                    priority=PRIORITY.get('event_label', 60),
                    element_type='event_label',
                    group=event_group,
                )
                apply_text(ax, lon, lat, text, 'event_text',
                           x_offset=label_ox, y_offset=label_oy + 2,
                           rotation=rotation, ha=ha, va='bottom')
            if date:
                pm.add_label(
                    f"event_date_{event_id}",
                    (lon, lat),
                    date,
                    fontsize=LABEL_STYLES.get('event_date', {}).get('fontsize', 8),
                    x_offset_pts=label_ox,
                    y_offset_pts=label_oy - 2,
                    priority=PRIORITY.get('event_label', 60),
                    element_type='event_label',
                    group=event_group,
                )
                apply_text(ax, lon, lat, date, 'event_date',
                           x_offset=label_ox, y_offset=label_oy - 2,
                           rotation=rotation, ha=ha, va='top')
        else:
            # No icon: render text/date centered at location
            if text:
                pm.add_label(
                    f"event_text_{event_id}",
                    (lon, lat),
                    text,
                    fontsize=LABEL_STYLES.get('event_text', {}).get('fontsize', 9),
                    y_offset_pts=3,
                    priority=PRIORITY.get('event_label', 60),
                    element_type='event_label',
                    group=event_group,
                )
                apply_text(ax, lon, lat, text, 'event_text',
                           y_offset=3, rotation=rotation, ha='center', va='bottom')
            if date:
                pm.add_label(
                    f"event_date_{event_id}",
                    (lon, lat),
                    date,
                    fontsize=LABEL_STYLES.get('event_date', {}).get('fontsize', 8),
                    y_offset_pts=-3,
                    priority=PRIORITY.get('event_label', 60),
                    element_type='event_label',
                    group=event_group,
                )
                apply_text(ax, lon, lat, date, 'event_date',
                           y_offset=-3, rotation=rotation, ha='center', va='top')
