"""
Narrative box and map markers for History Cartopy maps.

Renders a bordered text box with narrative paragraphs in a corner of the map,
and optional numbered/lettered circle markers on the map itself.
"""

import logging
import textwrap

import matplotlib.patches as mpatches

from history_cartopy.placement import PRIORITY

logger = logging.getLogger('history_cartopy.narrative')

# Border width in pixels (must match border_styles.BORDER_WIDTH_PX)
BORDER_WIDTH_PX = 100


def _resolve_item_coords(item, gazetteer):
    """Resolve lon/lat for a narrative item from coords or location."""
    if 'coords' in item:
        return tuple(item['coords'])
    location = item.get('location')
    if location and location in gazetteer:
        return gazetteer[location]
    if location:
        logger.warning(f"Narrative location '{location}' not found in gazetteer")
    return None


def collect_narrative_markers(manifest, gazetteer, pm, narrative_style=None):
    """
    Register narrative markers as fixed elements in the placement manager.

    Call this during Phase 1 (COLLECT) so other labels avoid these positions.

    Args:
        manifest: Parsed YAML manifest
        gazetteer: City name -> (lon, lat) dict
        pm: PlacementManager instance
        narrative_style: Style dict from theme (for marker_radius)
    """
    narrative = manifest.get('narrative')
    if not narrative:
        return

    items = narrative.get('items', [])
    priority = PRIORITY.get('narrative_marker', 85)
    marker_radius = 6
    if narrative_style:
        marker_radius = narrative_style.get('marker_radius', 6)

    marker_count = 0
    for i, item in enumerate(items):
        label = item.get('label')
        if not label or label is False:
            continue

        coords = _resolve_item_coords(item, gazetteer)
        if coords is None:
            continue

        marker_count += 1
        marker_id = f"narrative_marker_{i}"
        logger.debug(f"Registering narrative marker '{label}' at {coords}")
        pm.add_icon(
            id=marker_id,
            coords=coords,
            size_pts=marker_radius * 2,
            priority=priority,
            element_type='narrative_marker',
        )

    logger.info(f"Collected {marker_count} narrative marker(s) from {len(items)} items")


def render_narrative_markers(ax, manifest, gazetteer, narrative_style, bg_color, dpp):
    """
    Render numbered/lettered circle markers on the map.

    Args:
        ax: Map axes (geographic coordinates)
        manifest: Parsed YAML manifest
        gazetteer: City name -> (lon, lat) dict
        narrative_style: Style dict from theme
        bg_color: Background color for marker circles (matches narrative box)
        dpp: Degrees per point for coordinate conversion
    """
    narrative = manifest.get('narrative')
    if not narrative:
        return

    import cartopy.crs as ccrs

    items = narrative.get('items', [])
    marker_radius = narrative_style.get('marker_radius', 6)
    marker_color = narrative_style.get('marker_color', '#333333')
    marker_linewidth = narrative_style.get('marker_linewidth', 1.5)
    label_fontsize = narrative_style.get('label_fontsize', 9)
    font_family = narrative_style.get('font_family', 'serif')

    # Convert marker radius from points to degrees
    radius_deg = marker_radius * dpp
    rendered = 0

    for item in items:
        label = item.get('label')
        if not label or label is False:
            continue

        coords = _resolve_item_coords(item, gazetteer)
        if coords is None:
            continue

        lon, lat = coords

        circle = mpatches.Circle(
            (lon, lat), radius=radius_deg,
            facecolor=bg_color,
            edgecolor=marker_color,
            linewidth=marker_linewidth,
            transform=ccrs.PlateCarree(),
            zorder=6,
        )
        ax.add_patch(circle)

        ax.text(
            lon, lat, str(label),
            fontsize=label_fontsize,
            fontweight='bold',
            fontfamily=font_family,
            color=marker_color,
            ha='center', va='center',
            transform=ccrs.PlateCarree(),
            zorder=6.1,
        )
        rendered += 1
        logger.debug(f"Rendered narrative marker '{label}' at ({lon:.2f}, {lat:.2f})")

    logger.info(f"Rendered {rendered} narrative marker(s)")


def render_narrative_box(overlay_ax, fig, manifest, dimensions_px,
                         cartouche_style, narrative_style, title_box_bounds=None):
    """
    Render a narrative text box on the overlay axes.

    Args:
        overlay_ax: Matplotlib axes in 0-1 coordinate space
        fig: Matplotlib figure
        manifest: Parsed YAML manifest
        dimensions_px: [width, height] in pixels
        cartouche_style: Dict with border styling (shared with title cartouche)
        narrative_style: Dict with narrative-specific styling from theme
        title_box_bounds: (x, y, w, h) of title cartouche, or None
    """
    narrative = manifest.get('narrative')
    if not narrative:
        return

    items = narrative.get('items', [])
    if not items:
        return

    position = narrative.get('position', 'bottom-left')
    logger.info(f"Rendering narrative box: {len(items)} items, position={position}")

    # Create overlay axes if none provided
    if overlay_ax is None:
        map_ax = fig.axes[0]
        overlay_ax = fig.add_axes(map_ax.get_position(), frameon=False, zorder=10)
        overlay_ax.set_xlim(0, 1)
        overlay_ax.set_ylim(0, 1)
        overlay_ax.set_xticks([])
        overlay_ax.set_yticks([])
        overlay_ax.patch.set_visible(False)

    # Unpack styles
    outer_lw = cartouche_style['outer_line_width']
    inner_lw = cartouche_style['inner_line_width']
    line_gap = cartouche_style['line_gap']
    line_color = cartouche_style['line_color']
    bg_color = cartouche_style['background_color']
    padding = cartouche_style['padding']
    font_family = narrative_style.get('font_family', 'serif')
    body_fontsize = narrative.get('fontsize', narrative_style.get('body_fontsize', 8))
    text_color = narrative_style.get('text_color', '#333333')
    box_width_frac = narrative.get('width', narrative_style.get('box_width_frac', 0.30))
    para_gap_factor = narrative_style.get('para_gap_factor', 0.8)
    wrap_width = narrative_style.get('wrap_width', 50)

    renderer = fig.canvas.get_renderer()
    ax_bbox = overlay_ax.get_window_extent(renderer=renderer)
    ax_w_dpx = ax_bbox.width
    ax_h_dpx = ax_bbox.height
    pts2dpx = renderer.points_to_pixels(1.0)

    fig_width_px, fig_height_px = dimensions_px

    # Border margin
    border_style = manifest['metadata'].get('border_style')
    has_border = border_style is not None
    if has_border:
        border_margin_x = BORDER_WIDTH_PX / fig_width_px
        border_margin_y = BORDER_WIDTH_PX / fig_height_px
    else:
        border_margin_x = 0
        border_margin_y = 0

    inset_frac = 0.03
    inset_x = inset_frac
    inset_y = inset_frac * fig_width_px / fig_height_px

    border_total_dpx = (outer_lw + line_gap + inner_lw + padding) * pts2dpx

    # Calculate wrap width from box dimensions
    # Available text width = box width - 2 * border_total
    box_w_dpx = box_width_frac * ax_w_dpx
    text_avail_dpx = box_w_dpx - 2 * border_total_dpx

    # Measure average character width at the body font size
    sample_text = overlay_ax.text(0, 0, 'x' * 50, fontsize=body_fontsize, fontfamily=font_family)
    sample_bbox = sample_text.get_window_extent(renderer=renderer)
    sample_text.remove()
    char_width_dpx = sample_bbox.width / 50
    computed_wrap_width = max(20, int(text_avail_dpx / char_width_dpx))
    logger.debug(f"Narrative box: fontsize={body_fontsize}, box_width={box_width_frac:.0%}, wrap_width={computed_wrap_width} chars")

    # Build wrapped text for each paragraph
    paragraphs = []
    for item in items:
        text = item.get('text', '').strip()
        if not text:
            continue
        label = item.get('label')
        if label and label is not False:
            prefix = f"{label}. "
        else:
            prefix = ""

        wrapped = textwrap.fill(prefix + text, width=computed_wrap_width)
        paragraphs.append({'text': wrapped})

    if not paragraphs:
        return

    # Measure text height by creating temporary text objects
    para_gap_dpx = body_fontsize * para_gap_factor * pts2dpx
    total_text_h_dpx = 0
    para_heights_dpx = []

    for para in paragraphs:
        t = overlay_ax.text(
            0, 0, para['text'],
            fontsize=body_fontsize, fontfamily=font_family,
        )
        bbox = t.get_window_extent(renderer=renderer)
        para_heights_dpx.append(bbox.height)
        total_text_h_dpx += bbox.height
        t.remove()

    # Add gaps between paragraphs
    total_text_h_dpx += para_gap_dpx * (len(paragraphs) - 1)

    # Box dimensions
    box_w = box_width_frac
    box_h_dpx = total_text_h_dpx + 2 * border_total_dpx
    box_h = box_h_dpx / ax_h_dpx

    # Position the box
    if 'left' in position:
        box_x = border_margin_x + inset_x
    else:
        box_x = 1 - border_margin_x - inset_x - box_w

    if 'top' in position:
        box_y = 1 - border_margin_y - inset_y - box_h
    else:
        box_y = border_margin_y + inset_y

    # Stack with title cartouche if they share the same corner
    if title_box_bounds is not None:
        title_position = manifest['metadata'].get('title_position', 'top-left')
        if _same_corner(position, title_position):
            tx, ty, tw, th = title_box_bounds
            stacking_gap = 0.01
            if 'top' in position:
                box_y = ty - stacking_gap - box_h
            else:
                box_y = ty + th + stacking_gap

    # Draw background
    bg_rect = mpatches.FancyBboxPatch(
        (box_x, box_y), box_w, box_h,
        boxstyle="square,pad=0",
        facecolor=bg_color, edgecolor='none',
        transform=overlay_ax.transAxes, zorder=8.0,
    )
    overlay_ax.add_patch(bg_rect)

    # Draw outer border
    outer_rect = mpatches.FancyBboxPatch(
        (box_x, box_y), box_w, box_h,
        boxstyle="square,pad=0",
        facecolor='none', edgecolor=line_color, linewidth=outer_lw,
        transform=overlay_ax.transAxes, zorder=8.1,
    )
    overlay_ax.add_patch(outer_rect)

    # Draw inner border
    gap_dpx = (line_gap + outer_lw / 2 + inner_lw / 2) * pts2dpx
    gap_x = gap_dpx / ax_w_dpx
    gap_y = gap_dpx / ax_h_dpx
    inner_rect = mpatches.FancyBboxPatch(
        (box_x + gap_x, box_y + gap_y),
        box_w - 2 * gap_x, box_h - 2 * gap_y,
        boxstyle="square,pad=0",
        facecolor='none', edgecolor=line_color, linewidth=inner_lw,
        transform=overlay_ax.transAxes, zorder=8.2,
    )
    overlay_ax.add_patch(inner_rect)

    # Render paragraphs
    text_inset_x = border_total_dpx / ax_w_dpx
    text_inset_y = border_total_dpx / ax_h_dpx

    cursor_y = box_y + box_h - text_inset_y
    text_x = box_x + text_inset_x

    for i, para in enumerate(paragraphs):
        overlay_ax.text(
            text_x, cursor_y, para['text'],
            fontsize=body_fontsize,
            fontfamily=font_family,
            color=text_color,
            va='top', ha='left',
            transform=overlay_ax.transAxes,
            zorder=8.3,
        )

        # Advance cursor using pre-measured heights
        cursor_y -= para_heights_dpx[i] / ax_h_dpx
        if i < len(paragraphs) - 1:
            cursor_y -= para_gap_dpx / ax_h_dpx


def _same_corner(pos1, pos2):
    """Check if two position strings refer to the same corner."""
    def normalize(p):
        v = 'top' if 'top' in p else 'bottom'
        h = 'left' if 'left' in p else 'right'
        return (v, h)
    return normalize(pos1) == normalize(pos2)
