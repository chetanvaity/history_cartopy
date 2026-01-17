import numpy as np
import matplotlib.patches as patches
import cartopy.crs as ccrs
from history_cartopy.stylemaps import CAMPAIGN_STYLES
from history_cartopy.styles import apply_text, get_deg_per_pt

def _get_campaign_geometry(p1, p2, rad):
    """Internal helper for standardized path and label anchors."""
    p1, p2 = np.array(p1), np.array(p2)
    t = np.linspace(0, 1, 50)
    
    diff = p2 - p1
    dist = np.linalg.norm(diff)
    if dist == 0: return None, None, None, None, None

    # Standardized Apex calculation for consistent curvature
    mid = (p1 + p2) / 2
    normal = np.array([diff[1], -diff[0]]) / dist
    apex = mid + (normal * (dist * rad / 2))
    
    path = (1-t)[:, None]**2 * p1 + 2*(1-t)[:, None]*t[:, None] * apex + t[:, None]**2 * p2
    arc_mid = path[len(path)//2]
    
    angle = np.degrees(np.arctan2(diff[1], diff[0]))
    if angle > 90: angle -= 180
    if angle < -90: angle += 180
    
    return path, arc_mid, normal, angle, dist

def _render_campaign_labels(ax, arc_mid, normal, angle, rad, label_above, label_below, color):
    """Shared label rendering logic."""
    side_multiplier = 1 if rad >= 0 else -1
    gap = 8

    if label_above:
        apply_text(ax, arc_mid[0], arc_mid[1], label_above, 'campaign_above',
                   color_override=color, rotation=angle,
                   x_offset=normal[0] * gap * side_multiplier,
                   y_offset=normal[1] * gap * side_multiplier,
                   ha='center', va='center')

    if label_below:
        apply_text(ax, arc_mid[0], arc_mid[1], label_below, 'campaign_below',
                   color_override=color, rotation=angle,
                   x_offset=-normal[0] * gap * side_multiplier,
                   y_offset=-normal[1] * gap * side_multiplier,
                   ha='center', va='center')

def apply_campaign_simple(ax, path_data, style, rad, label_above, label_below):
    """Style 1: Simple solid line with arrow head."""
    path, arc_mid, normal, angle, _ = path_data
    color = style.get('color', 'black')

    arrow = patches.FancyArrowPatch(
        path=patches.Path(path),
        color=color,
        arrowstyle='-|> ,head_length=5,head_width=3',
        linewidth=style.get('linewidth', 1.5),
        alpha=style.get('alpha', 0.8),
        transform=ccrs.PlateCarree(),
        zorder=4
    )
    ax.add_patch(arrow)
    _render_campaign_labels(ax, arc_mid, normal, angle, rad, label_above, label_below, color)

def apply_campaign_power(ax, path_data, style, rad, label_above, label_below, p1, p2):
    """Style 2: Tapered 'Power' Band."""
    _, arc_mid, normal, angle, _ = path_data
    dpp = get_deg_per_pt(ax)
    color = style.get('color', '#8b0000')
    
    # Calculate head setback
    head_len_deg = 12 * dpp
    # We re-calculate direction at the tip for the head
    path_full = _get_campaign_geometry(p1, p2, rad)[0]
    v_unit = (path_full[-1] - path_full[-5]) / np.linalg.norm(path_full[-1] - path_full[-5])
    p2_base = np.array(p2) - (v_unit * head_len_deg)
    
    # Body
    body_path, _, _, _, _ = _get_campaign_geometry(p1, p2_base, rad)
    # Tapering from 0.1 to 6.0 points
    widths = np.linspace(0.1, 6.0, len(body_path))
    upper, lower = [], []
    for i in range(len(body_path)):
        v = body_path[i+1]-body_path[i] if i<len(body_path)-1 else body_path[i]-body_path[i-1]
        n = np.array([v[1], -v[0]]) / np.linalg.norm(v)
        upper.append(body_path[i] + n * (widths[i]/2) * dpp)
        lower.append(body_path[i] - n * (widths[i]/2) * dpp)
    
    ax.add_patch(patches.Polygon(np.vstack([upper, lower[::-1]]), facecolor=color, 
                                 alpha=style.get('alpha', 0.8), transform=ccrs.PlateCarree(), zorder=4))
    
    # Head
    v_perp = np.array([v_unit[1], -v_unit[0]])
    ax.add_patch(patches.Polygon([p2, p2_base + (v_perp * 5*dpp), p2_base - (v_perp * 5*dpp)], 
                                 facecolor=color, alpha=style.get('alpha', 0.8), transform=ccrs.PlateCarree(), zorder=4))

    _render_campaign_labels(ax, arc_mid, normal, angle, rad, label_above, label_below, color)

    
def apply_campaign(ax, points, label_above="", label_below="", style_key="invasion", rad=0.3):
    """MAIN ROUTER: Decides which visual "type" to apply."""
    p1, p2 = points[0], points[-1]
    path_data = _get_campaign_geometry(p1, p2, rad)
    if path_data[0] is None: return

    style = CAMPAIGN_STYLES.get(style_key, {}).copy()
    render_type = style.get('type', 'simple')

    if render_type == 'power':
        apply_campaign_power(ax, path_data, style, rad, label_above, label_below, p1, p2)
    else:
        apply_campaign_simple(ax, path_data, style, rad, label_above, label_below)
