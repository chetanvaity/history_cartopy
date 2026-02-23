"""
Multi-stop campaign path rendering with smart label placement.

Supports N-waypoint paths with spline or segment interpolation.
"""
import numpy as np
import matplotlib.patches as patches
import cartopy.crs as ccrs
from history_cartopy.themes import CAMPAIGN_STYLES
from history_cartopy.styles import apply_text, get_deg_per_pt


def _catmull_rom_segment(p0, p1, p2, p3, num_samples=50):
    """
    Generate Catmull-Rom spline segment between p1 and p2.

    Uses p0 and p3 as control points for tangent calculation.

    Args:
        p0, p1, p2, p3: Control points as (x, y) arrays
        num_samples: Number of points to generate

    Returns:
        np.array of shape (num_samples, 2)
    """
    t = np.linspace(0, 1, num_samples)[:, None]

    # Catmull-Rom basis matrix (tension = 0.5)
    # P(t) = 0.5 * [(2*p1) + (-p0 + p2)*t + (2*p0 - 5*p1 + 4*p2 - p3)*t^2 + (-p0 + 3*p1 - 3*p2 + p3)*t^3]
    return 0.5 * (
        2 * p1 +
        (-p0 + p2) * t +
        (2 * p0 - 5 * p1 + 4 * p2 - p3) * t**2 +
        (-p0 + 3 * p1 - 3 * p2 + p3) * t**3
    )


def _quadratic_bezier(p0, p2, curvature=0.0, num_samples=50):
    """
    Generate quadratic Bezier curve between p0 and p2.

    Control point is placed perpendicular to midpoint at a distance
    proportional to segment length times curvature.

    Args:
        p0: Start point as (x, y) array
        p2: End point as (x, y) array
        curvature: Perpendicular offset as fraction of segment length.
                   Positive = curve left (facing p2 from p0)
                   Negative = curve right
                   0 = straight line
        num_samples: Number of points to generate

    Returns:
        np.array of shape (num_samples, 2)
    """
    p0 = np.asarray(p0)
    p2 = np.asarray(p2)

    # Direction vector
    direction = p2 - p0
    length = np.linalg.norm(direction)

    if length == 0:
        return np.tile(p0, (num_samples, 1))

    # Midpoint
    midpoint = (p0 + p2) / 2

    # Perpendicular unit vector (90 degrees counter-clockwise)
    perp = np.array([-direction[1], direction[0]]) / length

    # Control point offset from midpoint
    p1 = midpoint + perp * length * curvature

    # Quadratic Bezier: B(t) = (1-t)^2 * P0 + 2*(1-t)*t * P1 + t^2 * P2
    t = np.linspace(0, 1, num_samples)[:, None]
    curve = (1 - t)**2 * p0 + 2 * (1 - t) * t * p1 + t**2 * p2

    return curve


def _compute_segment_info(path):
    """
    Compute segment metadata from a path array.

    Args:
        path: np.array of shape (N, 2)

    Returns:
        dict with 'path', 'length', 'midpoint', 'normal', 'angle'
    """
    # Compute arc length
    diffs = np.diff(path, axis=0)
    segment_lengths = np.linalg.norm(diffs, axis=1)
    total_length = np.sum(segment_lengths)

    if total_length == 0:
        return None

    # Find midpoint (by arc length)
    cumulative = np.cumsum(segment_lengths)
    half_length = total_length / 2
    mid_idx = np.searchsorted(cumulative, half_length)
    mid_idx = min(mid_idx, len(path) - 1)
    midpoint = path[mid_idx]

    # Compute tangent at midpoint
    if mid_idx > 0 and mid_idx < len(path) - 1:
        tangent = path[mid_idx + 1] - path[mid_idx - 1]
    elif mid_idx < len(path) - 1:
        tangent = path[mid_idx + 1] - path[mid_idx]
    else:
        tangent = path[mid_idx] - path[mid_idx - 1]

    tangent_len = np.linalg.norm(tangent)
    if tangent_len > 0:
        tangent = tangent / tangent_len

    # Normal is perpendicular to tangent
    normal = np.array([tangent[1], -tangent[0]])

    # Angle for label rotation (constrained to readable range)
    angle = np.degrees(np.arctan2(tangent[1], tangent[0]))
    if angle > 90:
        angle -= 180
    if angle < -90:
        angle += 180

    return {
        'path': path,
        'length': total_length,
        'midpoint': midpoint,
        'normal': normal,
        'angle': angle
    }


def _get_multistop_geometry(waypoints, path_type='spline', num_samples=50, curvature=0.0):
    """
    Compute geometry for multi-waypoint campaign.

    Args:
        waypoints: List of (lon, lat) coordinates (minimum 2)
        path_type: 'spline' or 'segments'
        num_samples: Points per segment for spline
        curvature: For 2-point paths, perpendicular offset as fraction of length.
                   Positive = curve left, negative = curve right, 0 = straight.

    Returns:
        dict with:
            'full_path': np.array of all points
            'segments': list of segment info dicts
            'total_length': float
            'waypoints': original waypoints as np.array
    """
    points = np.array(waypoints)
    n = len(points)

    if n < 2:
        return None

    segments = []

    if path_type == 'segments':
        # Straight line segments between waypoints
        all_paths = []
        for i in range(n - 1):
            t = np.linspace(0, 1, num_samples)[:, None]
            seg_path = points[i] + t * (points[i + 1] - points[i])
            seg_info = _compute_segment_info(seg_path)
            if seg_info:
                segments.append(seg_info)
                all_paths.append(seg_path)

        if not all_paths:
            return None
        full_path = np.vstack(all_paths)

    elif n == 2:
        # Two points: use quadratic Bezier with curvature
        seg_path = _quadratic_bezier(points[0], points[1], curvature, num_samples)
        seg_info = _compute_segment_info(seg_path)
        if seg_info is None:
            return None
        segments.append(seg_info)
        full_path = seg_path

    else:
        # Catmull-Rom spline through all waypoints
        all_paths = []
        for i in range(n - 1):
            # Get control points (extend at boundaries)
            p0 = points[i - 1] if i > 0 else 2 * points[0] - points[1]
            p1 = points[i]
            p2 = points[i + 1]
            p3 = points[i + 2] if i + 2 < n else 2 * points[-1] - points[-2]

            seg_path = _catmull_rom_segment(p0, p1, p2, p3, num_samples)
            seg_info = _compute_segment_info(seg_path)
            if seg_info:
                segments.append(seg_info)
                all_paths.append(seg_path)

        if not all_paths:
            return None
        full_path = np.vstack(all_paths)

    total_length = sum(s['length'] for s in segments)

    return {
        'full_path': full_path,
        'segments': segments,
        'total_length': total_length,
        'waypoints': points
    }


def _get_label_candidates(geometry):
    """
    Return segments ranked by length (longest first).

    Args:
        geometry: dict from _get_multistop_geometry()

    Returns:
        list of segment dicts, sorted by length descending
    """
    return sorted(geometry['segments'], key=lambda s: -s['length'])


def _render_campaign_labels(ax, segment, label_above, label_below, color):
    """
    Render campaign labels at segment midpoint.

    Args:
        ax: matplotlib axes
        segment: segment info dict with midpoint, normal, angle
        label_above: text for above label
        label_below: text for below label
        color: label color
    """
    midpoint = segment['midpoint']
    normal = segment['normal']
    angle = segment['angle']
    gap = 8

    if label_above:
        apply_text(ax, midpoint[0], midpoint[1], label_above, 'campaign_above',
                   color_override=color, rotation=angle,
                   x_offset=normal[0] * gap,
                   y_offset=normal[1] * gap,
                   ha='center', va='center')

    if label_below:
        apply_text(ax, midpoint[0], midpoint[1], label_below, 'campaign_below',
                   color_override=color, rotation=angle,
                   x_offset=-normal[0] * gap,
                   y_offset=-normal[1] * gap,
                   ha='center', va='center')


def _render_arrowhead(ax, path, color, alpha, dpp, head_length_pts=12, head_width_pts=5):
    """
    Render triangular arrowhead at end of path.

    Args:
        ax: matplotlib axes
        path: np.array path ending where arrow should point
        color: arrow color
        alpha: transparency
        dpp: degrees per point
        head_length_pts: arrowhead length in points
        head_width_pts: arrowhead half-width in points
    """
    # Direction at tip
    v = path[-1] - path[-5] if len(path) >= 5 else path[-1] - path[0]
    v_len = np.linalg.norm(v)
    if v_len == 0:
        return
    v_unit = v / v_len
    v_perp = np.array([v_unit[1], -v_unit[0]])

    tip = path[-1]
    base = tip - v_unit * head_length_pts * dpp

    triangle = [
        tip,
        base + v_perp * head_width_pts * dpp,
        base - v_perp * head_width_pts * dpp
    ]

    ax.add_patch(patches.Polygon(
        triangle,
        facecolor=color,
        alpha=alpha,
        transform=ccrs.PlateCarree(),
        zorder=4
    ))


def apply_campaign_march(ax, geometry, label_segment, style, label_above, label_below, arrows='final'):
    """
    Render a march (secondary movement) arrow: thin solid line with arrowhead.

    Args:
        ax: matplotlib axes
        geometry: dict from _get_multistop_geometry()
        label_segment: segment dict for label placement
        style: style dict from CAMPAIGN_STYLES
        label_above, label_below: label text
        arrows: 'final' or 'all'
    """
    color = style.get('color', 'black')
    linewidth = style.get('linewidth', 1.5)
    alpha = style.get('alpha', 0.8)

    full_path = geometry['full_path']

    arrow = patches.FancyArrowPatch(
        path=patches.Path(full_path),
        color=color,
        arrowstyle='-|>,head_length=5,head_width=3',
        linewidth=linewidth,
        alpha=alpha,
        transform=ccrs.PlateCarree(),
        zorder=4
    )
    ax.add_patch(arrow)

    if arrows == 'all' and len(geometry['segments']) > 1:
        dpp = get_deg_per_pt(ax)
        for seg in geometry['segments'][:-1]:
            _render_arrowhead(ax, seg['path'], color, alpha, dpp,
                              head_length_pts=4, head_width_pts=2)

    _render_campaign_labels(ax, label_segment, label_above, label_below, color)


def apply_campaign_retreat(ax, geometry, label_segment, style, label_above, label_below, arrows='final'):
    """
    Render a retreat arrow: dotted line with arrowhead, lighter weight.

    Args:
        ax: matplotlib axes
        geometry: dict from _get_multistop_geometry()
        label_segment: segment dict for label placement
        style: style dict from CAMPAIGN_STYLES
        label_above, label_below: label text
        arrows: 'final' or 'all'
    """
    color = style.get('color', 'black')
    linewidth = style.get('linewidth', 1.5)
    alpha = style.get('alpha', 0.8)

    full_path = geometry['full_path']

    arrow = patches.FancyArrowPatch(
        path=patches.Path(full_path),
        color=color,
        arrowstyle='-|>,head_length=5,head_width=3',
        linewidth=linewidth,
        linestyle=':',
        alpha=alpha,
        transform=ccrs.PlateCarree(),
        zorder=4
    )
    ax.add_patch(arrow)

    if arrows == 'all' and len(geometry['segments']) > 1:
        dpp = get_deg_per_pt(ax)
        for seg in geometry['segments'][:-1]:
            _render_arrowhead(ax, seg['path'], color, alpha, dpp,
                              head_length_pts=4, head_width_pts=2)

    _render_campaign_labels(ax, label_segment, label_above, label_below, color)


def apply_campaign_power(ax, geometry, label_segment, style, label_above, label_below, arrows='final'):
    """
    Style 2: Tapered 'Power' band with triangular head.

    Args:
        ax: matplotlib axes
        geometry: dict from _get_multistop_geometry()
        label_segment: segment dict for label placement
        style: style dict from CAMPAIGN_STYLES
        label_above, label_below: label text
        arrows: 'final' or 'all'
    """
    dpp = get_deg_per_pt(ax)
    color = style.get('color', '#8b0000')
    alpha = style.get('alpha', 0.8)

    full_path = geometry['full_path']

    # Shorten path for arrowhead
    head_len_deg = 12 * dpp
    v = full_path[-1] - full_path[-5] if len(full_path) >= 5 else full_path[-1] - full_path[0]
    v_len = np.linalg.norm(v)
    if v_len == 0:
        return
    v_unit = v / v_len
    end_base = full_path[-1] - v_unit * head_len_deg

    # Find where to cut the path
    distances = np.linalg.norm(full_path - end_base, axis=1)
    cut_idx = np.argmin(distances)
    body_path = full_path[:max(cut_idx + 1, 2)]

    # Tapering widths
    widths = np.linspace(0.1, 6.0, len(body_path))
    upper, lower = [], []

    for i in range(len(body_path)):
        if i < len(body_path) - 1:
            v = body_path[i + 1] - body_path[i]
        else:
            v = body_path[i] - body_path[i - 1]

        v_norm = np.linalg.norm(v)
        if v_norm > 0:
            n = np.array([v[1], -v[0]]) / v_norm
        else:
            n = np.array([0, 1])

        upper.append(body_path[i] + n * (widths[i] / 2) * dpp)
        lower.append(body_path[i] - n * (widths[i] / 2) * dpp)

    # Draw body
    ax.add_patch(patches.Polygon(
        np.vstack([upper, lower[::-1]]),
        facecolor=color,
        alpha=alpha,
        transform=ccrs.PlateCarree(),
        zorder=4
    ))

    # Draw main arrowhead
    _render_arrowhead(ax, full_path, color, alpha, dpp)

    # Additional arrowheads at waypoints if arrows='all'
    if arrows == 'all' and len(geometry['segments']) > 1:
        for seg in geometry['segments'][:-1]:
            _render_arrowhead(ax, seg['path'], color, alpha, dpp,
                              head_length_pts=8, head_width_pts=4)

    # Labels
    _render_campaign_labels(ax, label_segment, label_above, label_below, color)


def apply_campaign(ax, geometry, label_segment, label_above="", label_below="",
                   style_key="power", arrows="final", color_override=None):
    """
    Main campaign rendering router.

    Args:
        ax: matplotlib axes
        geometry: dict from _get_multistop_geometry()
        label_segment: segment dict for label placement (from _get_label_candidates)
        label_above, label_below: label text
        style_key: 'power', 'march', or 'retreat'
        arrows: 'final' (only at end) or 'all' (at each waypoint)
        color_override: optional hex color string to override the style's default color
    """
    if geometry is None or geometry['full_path'] is None:
        return

    style = CAMPAIGN_STYLES.get(style_key, {}).copy()
    if color_override:
        style['color'] = color_override

    if style_key == 'power':
        apply_campaign_power(ax, geometry, label_segment, style, label_above, label_below, arrows)
    elif style_key == 'retreat':
        apply_campaign_retreat(ax, geometry, label_segment, style, label_above, label_below, arrows)
    else:  # 'march' and any unknown fallback
        apply_campaign_march(ax, geometry, label_segment, style, label_above, label_below, arrows)
