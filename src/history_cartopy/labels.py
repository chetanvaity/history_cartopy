"""Label handling for cities, rivers, and regions."""

import logging
import os
import cartopy.crs as ccrs

from history_cartopy.core import get_offsets
from history_cartopy.styles import apply_text
from history_cartopy.anchor import AnchorCircle
from history_cartopy.icons import render_icon, DEFAULT_ICONSET
from history_cartopy.stylemaps import CITY_LEVELS, LABEL_STYLES
from history_cartopy.placement import LabelCandidate, PRIORITY

logger = logging.getLogger('history_cartopy.labels')


def collect_labels(gazetteer, manifest, placement_manager, data_dir=None):
    """
    Collect all label data without rendering.

    Phase 1 of the three-phase flow: Collect -> Resolve -> Render

    Returns:
        (city_candidates, river_data, region_data, city_render_data)
        - city_candidates: list of LabelCandidate with 8 positions each
        - river_data: list of dicts with river render info (fixed positions)
        - region_data: list of dicts with region render info (fixed positions)
        - city_render_data: list of dicts with city render info
    """
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


def render_labels_resolved(ax, city_render_data, river_data, region_data,
                           resolved_positions, gazetteer, manifest, data_dir=None):
    """
    Render labels using pre-resolved positions.

    Phase 3 of the three-phase flow: Collect -> Resolve -> Render

    Args:
        ax: matplotlib axes
        city_render_data: city render data from collect_labels
        river_data: river render data from collect_labels
        region_data: region render data from collect_labels
        resolved_positions: dict from resolve_greedy() mapping label IDs to PlacementElements
        manifest: the manifest for iconset lookup
        data_dir: data directory path
    """
    from history_cartopy.styles import get_deg_per_pt

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
