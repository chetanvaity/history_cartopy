"""
In-map title cartouche for History Cartopy maps.

Renders a decorative title box (cartouche) inside the map area,
drawn on the overlay axes used by the border system.
"""

import logging
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

logger = logging.getLogger('history_cartopy.title_cartouche')

# Border width in pixels (must match border_styles.BORDER_WIDTH_PX)
BORDER_WIDTH_PX = 100


def render_title_cartouche(overlay_ax, fig, manifest, dimensions_px, cartouche_style):
    """
    Render a title cartouche on the overlay axes.

    Args:
        overlay_ax: Matplotlib axes in 0-1 coordinate space (from render_border
                    or created here). If None, one will be created.
        fig: Matplotlib figure object
        manifest: Parsed YAML manifest dict
        dimensions_px: [width, height] in pixels
        cartouche_style: Dict with styling parameters from theme
    """
    metadata = manifest['metadata']
    title = metadata.get('title', '')
    subtitle = metadata.get('subtitle', '')
    position = metadata.get('title_position', 'top-left')

    if not title:
        return

    # Create overlay axes if none provided (no border case)
    if overlay_ax is None:
        # Get the map axes position to match
        map_ax = fig.axes[0]
        overlay_ax = fig.add_axes(map_ax.get_position(), frameon=False, zorder=10)
        overlay_ax.set_xlim(0, 1)
        overlay_ax.set_ylim(0, 1)
        overlay_ax.set_xticks([])
        overlay_ax.set_yticks([])
        overlay_ax.patch.set_visible(False)

    # Unpack style
    outer_lw = cartouche_style['outer_line_width']
    inner_lw = cartouche_style['inner_line_width']
    line_gap = cartouche_style['line_gap']
    line_color = cartouche_style['line_color']
    bg_color = cartouche_style['background_color']
    padding = cartouche_style['padding']
    title_fontsize = cartouche_style['title_fontsize']
    subtitle_fontsize = cartouche_style['subtitle_fontsize']
    font_family = cartouche_style['font_family']

    renderer = fig.canvas.get_renderer()

    # Get axes dimensions in display pixels (at renderer DPI).
    # All measurements from get_window_extent() are in this space.
    ax_bbox = overlay_ax.get_window_extent(renderer=renderer)
    ax_w_dpx = ax_bbox.width
    ax_h_dpx = ax_bbox.height

    # Scale for converting output pixels (300 DPI) to axes fraction.
    # Border margin and inset are defined in output pixels, and the border
    # tiles in render_border use the same fig_width_px denominator, so we
    # must stay consistent.
    fig_width_px, fig_height_px = dimensions_px

    # Points-to-display-pixels conversion
    pts2dpx = renderer.points_to_pixels(1.0)

    # Create temporary text objects to measure (in display pixels).
    # Do NOT set visible=False — it causes get_window_extent to return zero.
    title_text = overlay_ax.text(
        0, 0, title,
        fontsize=title_fontsize, fontweight='bold', fontfamily=font_family,
    )
    title_bbox = title_text.get_window_extent(renderer=renderer)
    title_text.remove()

    subtitle_bbox = None
    if subtitle:
        subtitle_text_obj = overlay_ax.text(
            0, 0, subtitle,
            fontsize=subtitle_fontsize, fontstyle='italic', fontfamily=font_family,
        )
        subtitle_bbox = subtitle_text_obj.get_window_extent(renderer=renderer)
        subtitle_text_obj.remove()

    # Text dimensions in display pixels
    text_w_dpx = max(title_bbox.width, subtitle_bbox.width if subtitle_bbox else 0)
    text_h_dpx = title_bbox.height
    if subtitle_bbox:
        text_h_dpx += subtitle_bbox.height + 2 * pts2dpx  # small gap

    # Padding/border in display pixels
    border_total_dpx = (outer_lw + line_gap + inner_lw + padding) * pts2dpx

    # Box size in display pixels, then convert to axes fraction
    box_w_dpx = text_w_dpx + 2 * border_total_dpx
    box_h_dpx = text_h_dpx + 2 * border_total_dpx
    box_w = box_w_dpx / ax_w_dpx
    box_h = box_h_dpx / ax_h_dpx

    # Border margin and inset use output-pixel fractions (consistent with render_border)
    border_style = manifest['metadata'].get('border_style')
    has_border = border_style is not None
    if has_border:
        border_margin_x = BORDER_WIDTH_PX / fig_width_px
        border_margin_y = BORDER_WIDTH_PX / fig_height_px
    else:
        border_margin_x = 0
        border_margin_y = 0

    inset_frac = 0.03  # 3% of map width
    inset_x = inset_frac
    # Use same physical distance for y (convert from width fraction to height fraction)
    inset_y = inset_frac * fig_width_px / fig_height_px

    # Compute box origin (bottom-left corner of outer rectangle)
    if 'left' in position:
        box_x = border_margin_x + inset_x
    else:
        box_x = 1 - border_margin_x - inset_x - box_w

    if 'top' in position:
        box_y = 1 - border_margin_y - inset_y - box_h
    else:
        box_y = border_margin_y + inset_y

    # Draw white background (covers everything under the cartouche)
    bg_rect = mpatches.FancyBboxPatch(
        (box_x, box_y), box_w, box_h,
        boxstyle="square,pad=0",
        facecolor=bg_color, edgecolor='none',
        transform=overlay_ax.transAxes, zorder=8.0,
    )
    overlay_ax.add_patch(bg_rect)

    # Draw outer border rectangle
    outer_rect = mpatches.FancyBboxPatch(
        (box_x, box_y), box_w, box_h,
        boxstyle="square,pad=0",
        facecolor='none', edgecolor=line_color, linewidth=outer_lw,
        transform=overlay_ax.transAxes, zorder=8.1,
    )
    overlay_ax.add_patch(outer_rect)

    # Draw inner border rectangle (inset by gap + half line widths)
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

    # Text position: inside the inner rectangle with padding
    text_inset_x = border_total_dpx / ax_w_dpx
    text_inset_y = border_total_dpx / ax_h_dpx

    # Title text (top of text area)
    title_x = box_x + text_inset_x
    title_y = box_y + box_h - text_inset_y

    overlay_ax.text(
        title_x, title_y, title,
        fontsize=title_fontsize, fontweight='bold', fontfamily=font_family,
        color=line_color, va='top', ha='left',
        transform=overlay_ax.transAxes, zorder=8.3,
    )

    # Subtitle text (below title)
    if subtitle:
        subtitle_y = title_y - title_bbox.height / ax_h_dpx - 2 * pts2dpx / ax_h_dpx
        overlay_ax.text(
            title_x, subtitle_y, subtitle,
            fontsize=subtitle_fontsize, fontstyle='italic', fontfamily=font_family,
            color=line_color, va='top', ha='left',
            transform=overlay_ax.transAxes, zorder=8.3,
        )
