"""Event handling for map events."""

import logging
import math
import os

from history_cartopy.styles import apply_text
from history_cartopy.icons import render_icon, DEFAULT_ICONSET
from history_cartopy.stylemaps import EVENT_CONFIG, LABEL_STYLES
from history_cartopy.placement import LabelCandidate, PRIORITY
from history_cartopy.anchor import POSITION_ANGLES, POSITION_PRIORITY

logger = logging.getLogger('history_cartopy.events')


def _get_event_ha_from_offset(x_offset, y_offset):
    """Determine horizontal alignment based on offset position."""
    if abs(x_offset) < 0.1:
        return 'center'
    elif x_offset > 0:
        return 'left'
    else:
        return 'right'


def collect_events(gazetteer, manifest, placement_manager, data_dir=None):
    """
    Collect all event label data without rendering.

    Phase 1 of the three-phase flow: Collect -> Resolve -> Render

    Returns:
        (event_candidates, event_render_data)
        - event_candidates: list of LabelCandidate for event labels (8 positions each)
        - event_render_data: list of dicts with event render info
    """
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

    Phase 3 of the three-phase flow: Collect -> Resolve -> Render

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
