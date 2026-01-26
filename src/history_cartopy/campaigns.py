"""Campaign arrow and label handling."""

import logging
import numpy as np

from history_cartopy.stylemaps import CITY_LEVELS, LABEL_STYLES
from history_cartopy.placement import LabelCandidate, ArrowCandidate, PRIORITY

logger = logging.getLogger('history_cartopy.campaigns')


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
    p1 = np.array(p_from)
    p2 = np.array(p_toward)
    direction = p2 - p1
    dist = np.linalg.norm(direction)
    if dist == 0:
        return p_from
    unit = direction / dist
    return (p1 + unit * offset_deg).tolist()


def collect_arrow_candidates(gazetteer, manifest, placement_manager):
    """
    Generate arrow candidates at multiple gap distances.

    Phase 1a of the flow: Collect arrow candidates with 2x, 3x, 4x gap options.

    Args:
        gazetteer: Location lookup dict
        manifest: Map manifest
        placement_manager: PlacementManager instance

    Returns:
        (arrow_candidates, campaign_render_data)
        - arrow_candidates: List of ArrowCandidate, each with variants at 2x, 3x, 4x gap
        - campaign_render_data: List of dicts with campaign render info (without geometry yet)
    """
    from history_cartopy.campaign_styles import _get_multistop_geometry

    pm = placement_manager
    city_levels = _get_city_level_lookup(manifest)
    dpp = pm.dpp

    gap_multipliers = [2.0, 3.0, 4.0]  # Try in order: shortest first

    arrow_candidates = []
    campaign_render_data = []

    campaigns = manifest.get('campaigns', [])
    logger.debug(f"Collecting {len(campaigns)} campaign arrow candidates")

    for idx, item in enumerate(campaigns):
        # 1. Coordinate Lookup
        raw_path = item.get('path', [])
        base_coords = []
        path_city_names = []

        for p in raw_path:
            if isinstance(p, str):
                if p in gazetteer:
                    base_coords.append(list(gazetteer[p]))
                    path_city_names.append(p)
                else:
                    logger.warning(f"Campaign location '{p}' not found in gazetteer")
                    continue
            else:
                base_coords.append(list(p))
                path_city_names.append(None)

        if len(base_coords) < 2:
            logger.warning("At least 2 points required for a campaign")
            continue

        # 2. Get city info for start/end
        name1 = path_city_names[0]
        name2 = path_city_names[-1] if len(path_city_names) > 1 else None

        # Get anchor radii for endpoint cities
        radius1 = 0
        radius2 = 0
        if name1 and name1 in city_levels:
            level1 = city_levels[name1]
            radius1 = CITY_LEVELS.get(level1, CITY_LEVELS[2])['anchor_radius']
        if name2 and name2 in city_levels:
            level2 = city_levels[name2]
            radius2 = CITY_LEVELS.get(level2, CITY_LEVELS[2])['anchor_radius']

        # 3. Extract parameters
        label_above = item.get('label_above', "")
        label_below = item.get('label_below', "")
        style_key = item.get('style', 'invasion')
        path_type = item.get('path_type', 'spline')
        arrows = item.get('arrows', 'final')

        campaign_group = f"campaign_{idx}"

        # 4. Generate variants at different gap multipliers
        variants = []
        for gap_mult in gap_multipliers:
            # Copy coords and adjust endpoints
            adjusted_coords = [list(c) for c in base_coords]

            # Offset start point
            if radius1 > 0:
                next_pt = adjusted_coords[1] if len(adjusted_coords) > 1 else adjusted_coords[0]
                adjusted_coords[0] = _offset_point_toward(
                    adjusted_coords[0], next_pt, radius1 * gap_mult * dpp
                )

            # Offset end point
            if radius2 > 0:
                prev_pt = adjusted_coords[-2] if len(adjusted_coords) > 1 else adjusted_coords[-1]
                adjusted_coords[-1] = _offset_point_toward(
                    adjusted_coords[-1], prev_pt, radius2 * gap_mult * dpp
                )

            # Compute geometry with this gap
            geometry = _get_multistop_geometry(adjusted_coords, path_type=path_type)
            if geometry is None:
                continue

            variants.append({
                'gap_multiplier': gap_mult,
                'path': geometry['full_path'],
                'geometry': geometry,
            })

        if not variants:
            logger.warning(f"Failed to compute any geometry for campaign {idx}")
            continue

        arrow_candidates.append(ArrowCandidate(
            id=f"campaign_arrow_{idx}",
            campaign_idx=idx,
            priority=PRIORITY.get('campaign_arrow', 55),
            group=campaign_group,
            variants=variants,
        ))

        # Store render data (geometry will be filled in after resolution)
        campaign_render_data.append({
            'idx': idx,
            'geometry': None,  # Will be set after arrow resolution
            'label_above': label_above,
            'label_below': label_below,
            'style_key': style_key,
            'arrows': arrows,
            'group': campaign_group,
        })

    return arrow_candidates, campaign_render_data


def collect_campaign_labels(manifest, resolved_arrows, placement_manager):
    """
    Generate campaign label candidates from resolved arrow geometry.

    Must be called AFTER resolve_arrows() since label positions
    depend on the resolved arrow path.

    Args:
        manifest: Map manifest
        resolved_arrows: Dict mapping arrow ID to resolved ArrowCandidate
        placement_manager: PlacementManager instance

    Returns:
        List of LabelCandidate for campaign labels
    """
    from history_cartopy.campaign_styles import _get_label_candidates

    pm = placement_manager

    campaign_candidates = []
    campaigns = manifest.get('campaigns', [])

    logger.debug(f"Collecting campaign labels from {len(resolved_arrows)} resolved arrows")

    for idx, item in enumerate(campaigns):
        arrow_id = f"campaign_arrow_{idx}"
        if arrow_id not in resolved_arrows:
            continue

        resolved = resolved_arrows[arrow_id]
        geometry = resolved.resolved_geometry
        campaign_group = f"campaign_{idx}"

        label_above = item.get('label_above', "")
        label_below = item.get('label_below', "")

        if not label_above and not label_below:
            continue

        # Generate label candidates from resolved geometry
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

    return campaign_candidates


def render_campaigns_resolved(ax, campaign_render_data, resolved_positions):
    """
    Render campaigns using pre-resolved label positions.

    Phase 3 of the three-phase flow: Collect -> Resolve -> Render

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
