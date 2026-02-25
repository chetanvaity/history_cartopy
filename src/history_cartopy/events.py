"""Event handling for map events.

Events are standalone markers for battles, treaties, crossings, etc.
They behave like cities: an imaginary anchor point with text labels
placed using the 8-position Imhof model. Icons, if present, are centered
at the location.
"""

import logging
import os

from history_cartopy.styles import apply_text
from history_cartopy.icons import render_icon, DEFAULT_ICONSET, ICON_SIZE_PT
from history_cartopy.anchor import AnchorCircle
from history_cartopy.themes import EVENT_CONFIG, LABEL_STYLES, ICONSET
from history_cartopy.placement import LabelCandidate, PRIORITY

logger = logging.getLogger('history_cartopy.events')


def collect_events(gazetteer, manifest, placement_manager, data_dir=None):
    """
    Collect all event label data without rendering.

    Phase 1 of the three-phase flow: Collect -> Resolve -> Render

    Events behave like cities:
    - An imaginary anchor point at the location
    - Text labels with 8 candidate positions around the anchor
    - Optional icon centered at the location

    Returns:
        (event_candidates, event_render_data)
        - event_candidates: list of LabelCandidate for event labels (8 positions each)
        - event_render_data: list of dicts with event render info
    """
    pm = placement_manager

    # Resolve iconset path
    iconset_name = manifest.get('metadata', {}).get('iconset') or ICONSET.get('path', DEFAULT_ICONSET)
    iconset_path = os.path.join(data_dir, iconset_name) if data_dir else None

    event_candidates = []
    event_render_data = []

    events = manifest.get('events', [])
    logger.debug(f"Collecting {len(events)} events for candidate generation")

    for item in events:
        text = item.get('text', '')
        subtext = item.get('subtext', '')
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

        # Optional rotation for the text
        rotation = item.get('rotation', 0)

        # Create event ID and group
        event_id = text or f"event_{lon}_{lat}"
        event_group = f"event_{event_id}"
        priority = PRIORITY.get('event_label', 60)

        # Determine if we have an icon
        has_icon = icon_name and iconset_path

        # Store render data
        event_render_data.append({
            'event_id': event_id,
            'text': text,
            'subtext': subtext,
            'coords': (lon, lat),
            'rotation': rotation,
            'icon_name': icon_name if has_icon else None,
            'group': event_group,
            'has_icon': has_icon,
        })

        # Add fixed icon element if present (centered at location)
        if has_icon:
            pm.add_icon(
                f"event_icon_{event_id}",
                (lon, lat),
                size_pts=ICON_SIZE_PT,
                priority=PRIORITY.get('event_icon', 90),
                element_type='event_icon',
                group=event_group,
            )

        # Generate 8 candidate positions for text label using AnchorCircle
        if text:
            # Create anchor circle for this event
            # Use a custom radius from EVENT_CONFIG
            anchor_radius = EVENT_CONFIG['anchor_radius']

            # Create a simple anchor for candidate generation
            anchor = AnchorCircle(city_level=2)  # Use level 2 as base
            anchor.radius = anchor_radius  # Override with event-specific radius

            fontsize = LABEL_STYLES.get('event_text', {}).get('fontsize', 9)
            subtext_fontsize = LABEL_STYLES.get('event_subtext', {}).get('fontsize', 7)
            block_height = fontsize + subtext_fontsize + 2 if subtext else fontsize
            candidate_offsets = anchor.get_candidate_offsets(gap_pts=0, text_height_pts=block_height)

            logger.debug(f"Event '{event_id}' at ({lon:.2f}, {lat:.2f}): generating {len(candidate_offsets)} candidate positions")

            text_positions = []
            for pos_name, x_off, y_off, ha, va in candidate_offsets:
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
                    ha=ha,
                    va=va,
                    subtext=subtext if subtext else None,
                    subtext_fontsize=subtext_fontsize if subtext else None,
                )
                element.id = f"event_text_{event_id}"
                element.ha = ha
                element.va = va
                logger.debug(f"  Position {pos_name}: offset=({x_off:.1f}, {y_off:.1f})pts, ha={ha}, va={va}, "
                           f"bbox=({element.bbox[0]:.3f}, {element.bbox[1]:.3f}, "
                           f"{element.bbox[2]:.3f}, {element.bbox[3]:.3f})")
                pm.remove(f"event_text_{event_id}_{pos_name}")
                text_positions.append(element)

            event_candidates.append(LabelCandidate(
                id=f"event_text_{event_id}",
                element_type='event_label',
                priority=priority,
                group=event_group,
                positions=text_positions,
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
        iconset_name = manifest.get('metadata', {}).get('iconset') or ICONSET.get('path', DEFAULT_ICONSET)
        iconset_path = os.path.join(data_dir, iconset_name) if data_dir else None
    else:
        iconset_path = None

    dpp = get_deg_per_pt(ax)

    for event in event_render_data:
        lon, lat = event['coords']
        event_id = event['event_id']
        rotation = event['rotation']

        # Render icon if present (always centered at location)
        if event['icon_name'] and iconset_path:
            render_icon(ax, lon, lat, event['icon_name'], iconset_path,
                        centered=True)

        # Render text at resolved position
        if event['text']:
            main_fontsize = LABEL_STYLES.get('event_text', {}).get('fontsize', 9)
            line_height = main_fontsize + 2  # pts between text centers

            text_id = f"event_text_{event_id}"
            if text_id in resolved_positions:
                resolved = resolved_positions[text_id]
                x_offset_pts = resolved.offset[0] / dpp
                y_offset_pts = resolved.offset[1] / dpp

                # Use alignment from resolved element
                ha = getattr(resolved, 'ha', 'left')
                va = getattr(resolved, 'va', 'bottom')

                apply_text(ax, lon, lat, event['text'], 'event_text',
                           x_offset=x_offset_pts, y_offset=y_offset_pts,
                           rotation=rotation, ha=ha, va=va)
                if event.get('subtext'):
                    apply_text(ax, lon, lat, event['subtext'], 'event_subtext',
                               x_offset=x_offset_pts,
                               y_offset=y_offset_pts - line_height,
                               rotation=rotation, ha=ha, va=va)
            else:
                # Fallback: default position (NE)
                apply_text(ax, lon, lat, event['text'], 'event_text',
                           x_offset=10, y_offset=10,
                           rotation=rotation, ha='left', va='bottom')
                if event.get('subtext'):
                    apply_text(ax, lon, lat, event['subtext'], 'event_subtext',
                               x_offset=10, y_offset=10 - line_height,
                               rotation=rotation, ha='left', va='bottom')
