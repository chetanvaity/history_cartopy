"""Detect and pair co-located city and event labels for cooperative placement.

When a battle/event occurs very close to a named city, their labels compete
for the same Imhof positions. This module detects such pairs and generates
PairedLabelCandidate objects that place both labels cooperatively, with the
event labels expanded to 3 distance tiers (matching city candidates).
"""

import math
import logging
from copy import copy

from history_cartopy.placement import PairedLabelCandidate
from history_cartopy.anchor import AnchorCircle
from history_cartopy.themes import EVENT_CONFIG, LABEL_STYLES

logger = logging.getLogger('history_cartopy.pairing')

# Maximum distance (in typographic points) between a city dot and an event marker
# for them to be considered co-located and eligible for cooperative label placement.
# At typical map scales, 10pt ≈ a few kilometres — tight enough that only events
# essentially on top of a city get paired.
PAIR_THRESHOLD_PTS = 10


def _haversine_km(lon1, lat1, lon2, lat2):
    """Approximate great-circle distance in km between two lon/lat points."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def _make_event_positions_3tier(event_cand, event_subtext, event_subtext_fontsize, pm):
    """
    Generate 3-tier event label positions (24 total) matching city candidates.

    The existing event_cand has 8 positions (1 tier). We generate all 3 tiers
    so paired placement has richer options.

    Returns:
        List of 24 PlacementElements (group unchanged — caller sets paired group)
    """
    event_anchor_radius = EVENT_CONFIG['anchor_radius']
    event_fontsize = LABEL_STYLES.get('event_text', {}).get('fontsize', 9)
    event_subtext_fontsize = event_subtext_fontsize or LABEL_STYLES.get('event_subtext', {}).get('fontsize', 7)

    event_lon, event_lat = event_cand.positions[0].coords
    event_text = event_cand.positions[0].text

    anchor = AnchorCircle(city_level=2)
    anchor.radius = event_anchor_radius

    positions = []
    distance_multipliers = [1.0, 1.3, 1.6]

    for multiplier in distance_multipliers:
        extra_gap = event_anchor_radius * (multiplier - 1.0)
        candidate_offsets = anchor.get_candidate_offsets(
            gap_pts=extra_gap, text_height_pts=event_fontsize
        )
        for pos_name, x_off, y_off, ha, va in candidate_offsets:
            tier_suffix = f"_t{int(multiplier * 10)}"
            temp_id = f"pair_evt_{event_cand.id}_{pos_name}{tier_suffix}"
            element = pm.add_label(
                temp_id,
                (event_lon, event_lat),
                event_text,
                fontsize=event_fontsize,
                x_offset_pts=x_off,
                y_offset_pts=y_off,
                priority=event_cand.priority,
                element_type='event_label',
                group=event_cand.group,
                ha=ha,
                va=va,
                subtext=event_subtext,
                subtext_fontsize=event_subtext_fontsize if event_subtext else None,
            )
            element.id = event_cand.id   # Preserve original ID for resolved_positions lookup
            element.ha = ha
            element.va = va
            pm.remove(temp_id)
            positions.append(element)

    return positions


def detect_and_pair(city_candidates, event_candidates, event_render_data, pm,
                    threshold_pts=PAIR_THRESHOLD_PTS):
    """
    Detect close city+event pairs and generate PairedLabelCandidate objects.

    For each city+event pair within threshold_pts, generates combined candidates
    where both labels are placed cooperatively. Event candidates are expanded to
    3 distance tiers for richer pair combinations (24 city × 24 event = up to 576
    pairs, filtered to those where the two bboxes don't overlap each other).

    Args:
        city_candidates:  List of LabelCandidate for city labels
        event_candidates: List of LabelCandidate for event labels
        event_render_data: List of event render dicts (provides subtext info)
        pm:               PlacementManager (provides dpp and bbox utilities)
        threshold_pts:    Proximity threshold in typographic points

    Returns:
        (paired_candidates, remaining_city_candidates, remaining_event_candidates)
    """
    threshold_deg = threshold_pts * pm.dpp

    # Build subtext lookup from event render data
    subtext_lookup = {}   # event_id -> (subtext, subtext_fontsize)
    subtext_fontsize = LABEL_STYLES.get('event_subtext', {}).get('fontsize', 7)
    for ev in event_render_data:
        subtext_lookup[ev['event_id']] = (
            ev.get('subtext', ''),
            subtext_fontsize,
        )

    paired_city_ids = set()
    paired_event_ids = set()
    paired_candidates = []

    for city_cand in city_candidates:
        if not city_cand.positions:
            continue
        city_coords = city_cand.positions[0].coords  # (lon, lat)

        for event_cand in event_candidates:
            if event_cand.id in paired_event_ids:
                continue
            if not event_cand.positions:
                continue

            event_coords = event_cand.positions[0].coords  # (lon, lat)
            dist = math.sqrt(
                (city_coords[0] - event_coords[0]) ** 2 +
                (city_coords[1] - event_coords[1]) ** 2
            )

            if dist >= threshold_deg:
                continue

            # Extract event ID from candidate ID (format: "event_text_{event_id}")
            event_id = event_cand.id.replace('event_text_', '', 1)
            event_subtext, event_subtext_fontsize = subtext_lookup.get(event_id, ('', subtext_fontsize))

            # Generate 3-tier event positions
            event_positions = _make_event_positions_3tier(
                event_cand, event_subtext or None, event_subtext_fontsize, pm
            )

            # Build all (city, event) pairs where the two bboxes don't intersect.
            # City positions: indices 0-7 = tier 1 (1.0x), 8-15 = tier 2 (1.3x), 16-23 = tier 3 (1.6x)
            paired_group = f"paired_{city_cand.id}_{event_cand.id}"
            paired_positions = []
            fallback_idx = None  # First pair from city 1.3x tier

            for city_idx, city_elem in enumerate(city_cand.positions):
                for event_elem in event_positions:
                    if pm._bbox_intersects(city_elem.bbox, event_elem.bbox):
                        continue
                    c = copy(city_elem)
                    e = copy(event_elem)
                    c.group = paired_group
                    e.group = paired_group
                    if fallback_idx is None and city_idx >= 8:
                        fallback_idx = len(paired_positions)  # First pair in 1.3x city tier
                    paired_positions.append([c, e])

            if not paired_positions:
                logger.warning(
                    f"No non-overlapping pairs found for '{city_cand.id}' + '{event_cand.id}'"
                )
                continue

            priority = max(city_cand.priority, event_cand.priority)
            paired_cand = PairedLabelCandidate(
                id=f"paired_{city_cand.id}_{event_cand.id}",
                element_type='paired_label',
                priority=priority,
                group=paired_group,
                positions=paired_positions,
                fallback_idx=fallback_idx if fallback_idx is not None else 0,
            )
            paired_candidates.append(paired_cand)
            paired_city_ids.add(city_cand.id)
            paired_event_ids.add(event_cand.id)

            dist_km = _haversine_km(city_coords[0], city_coords[1], event_coords[0], event_coords[1])
            logger.info(
                f"Paired '{city_cand.id}' + '{event_cand.id}' "
                f"(dist={dist / pm.dpp:.0f}pt, ~{dist_km:.0f}km, {len(paired_positions)} position pairs)"
            )
            break  # Each city pairs with at most one event

    remaining_city = [c for c in city_candidates if c.id not in paired_city_ids]
    remaining_event = [c for c in event_candidates if c.id not in paired_event_ids]

    return paired_candidates, remaining_city, remaining_event
