"""
Theme system for history-cartopy.

Each theme bundles: background, border, fonts, colors, campaign arrow styles,
territory styles, event styles, iconset, and title styling.

Usage in manifest:
    metadata:
      theme: bw-print

Usage in code:
    from history_cartopy.themes import apply_theme
    theme = apply_theme('bw-print')  # mutates stylemaps, returns theme dict
"""

import logging

logger = logging.getLogger('history_cartopy.themes')

THEMES = {
    # =========================================================================
    # EIGHTIES-TEXTBOOK
    # Full-color Natural Earth imagery, warm tones, the "classic" look.
    # This is the default and matches the original hardcoded values exactly.
    # =========================================================================
    'eighties-textbook': {
        'background': 'high',
        'border_style': 'double-black',
        'iconset': 'iconsets/default',

        'cartouche_style': {
            'outer_line_width': 3,       # points
            'inner_line_width': 1,       # points
            'line_gap': 3,               # points
            'line_color': 'black',
            'background_color': 'white',
            'padding': 10,               # points, inside inner line
            'title_fontsize': 16,
            'subtitle_fontsize': 11,
            'font_family': 'serif',
        },

        'title_style': {
            'fontsize': 14,
            'fontweight': 'bold',
            'fontfamily': 'serif',
            'color': 'black',
            'pad': 20,
        },

        'label_styles': {
            'city1':   {'fontsize': 10, 'weight': 'bold', 'family': 'serif', 'color': 'black', 'halo': True},
            'city2':   {'fontsize': 9, 'weight': 'normal', 'family': 'serif', 'color': '#333333', 'halo': True},
            'city3':   {'fontsize': 8, 'weight': 'normal', 'family': 'serif', 'color': '#555555', 'halo': True},
            'modern_place': {'fontsize': 7, 'style': 'italic', 'weight': 'normal', 'family': 'sans-serif', 'color': '#888888', 'halo': True},
            'river':   {'fontsize': 6, 'style': 'italic', 'family': 'serif', 'color': '#2c5d87', 'halo': False, 'ha': 'center', 'va': 'center'},
            'region':  {'fontsize': 20, 'family': 'serif', 'color': '#5d4037', 'alpha': 0.3, 'halo': False},
            'campaign_above': {'fontsize': 9, 'weight': 'normal', 'family': 'serif', 'color': 'black', 'halo': True},
            'campaign_below': {'fontsize': 8, 'weight': 'normal', 'family': 'serif', 'color': 'black', 'halo': True},
            'event_text':  {'fontsize': 9, 'weight': 'bold', 'family': 'sans-serif', 'color': '#800020', 'halo': True},
        },

        'event_config': {
            'anchor_radius': 12,
        },

        'city_levels': {
            1: {
                'dot_outer_size': 6,
                'dot_inner_size': 3,
                'dot_style': 'ring',
                'label_style': 'city1',
                'anchor_radius': 8,
                'default_icon': 'capital',
            },
            2: {
                'dot_outer_size': 4,
                'dot_inner_size': None,
                'dot_style': 'solid',
                'label_style': 'city2',
                'anchor_radius': 6,
                'default_icon': 'city',
            },
            3: {
                'dot_outer_size': 3,
                'dot_inner_size': None,
                'dot_style': 'solid',
                'label_style': 'city3',
                'anchor_radius': 5,
                'default_icon': 'city',
            },
            4: {
                'dot_outer_size': 2,
                'dot_inner_size': None,
                'dot_style': 'solid',
                'label_style': 'modern_place',
                'anchor_radius': 4,
                'default_icon': False,
            },
        },

        'campaign_styles': {
            'invasion': {
                'color': '#8b0000',
                'linewidth': 2.5,
                'linestyle': '-',
                'arrowstyle': 'fancy,head_length=5.5,head_width=5.5',
                'alpha': 0.5,
                'type': 'power',
            },
            'invasion-orange': {
                'color': '#E97451',
                'linewidth': 2.5,
                'linestyle': '-',
                'arrowstyle': 'fancy,head_length=5.5,head_width=5.5',
                'alpha': 0.5,
                'type': 'power',
            },
            'invasion-black': {
                'color': '#000000',
                'linewidth': 2.5,
                'linestyle': '-',
                'arrowstyle': 'fancy,head_length=5.5,head_width=5.5',
                'alpha': 0.5,
                'type': 'power',
            },
            'boring': {
                'color': '#d2691e',
                'linewidth': 1.5,
                'linestyle': '--',
                'arrowstyle': '-|>',
                'alpha': 0.7,
                'type': 'simple',
            },
            'retreat': {
                'color': '#4a4a4a',
                'linewidth': 1.8,
                'linestyle': (0, (3, 5, 1, 5)),
                'arrowstyle': 'simple,tail_width=0.2',
                'alpha': 0.6,
            },
            'siege-harrasment': {
                'color': 'black',
                'linewidth': 3,
                'linestyle': ':',
                'arrowstyle': '-',
                'alpha': 0.9,
            },
        },

        'narrative_style': {
            'body_fontsize': 8,
            'label_fontsize': 9,
            'font_family': 'serif',
            'text_color': '#333333',
            'box_width_frac': 0.30,
            'marker_radius': 6,       # points
            'marker_color': '#333333',
            'marker_linewidth': 1.5,
            'para_gap_factor': 0.8,    # gap = fontsize * this factor
            'wrap_width': 50,          # characters
        },

    },

    # =========================================================================
    # BW-PRINT
    # Grayscale theme for black-and-white book printing.
    # Medium-resolution BW background, all colors mapped to grays.
    # Differentiates elements via weight, size, and linestyle rather than color.
    # =========================================================================
    'bw-print': {
        'background': 'med-bw',
        'border_style': None,
        'iconset': 'iconsets/bwicons',

        'cartouche_style': {
            'outer_line_width': 2,
            'inner_line_width': 0.5,
            'line_gap': 2,
            'line_color': '#111111',
            'background_color': 'white',
            'padding': 10,
            'title_fontsize': 15,
            'subtitle_fontsize': 10,
            'font_family': 'serif',
        },

        'title_style': {
            'fontsize': 13,
            'fontweight': 'bold',
            'fontfamily': 'serif',
            'color': '#111111',
            'pad': 20,
        },

        'label_styles': {
            'city1':   {'fontsize': 10, 'weight': 'bold', 'family': 'serif', 'color': 'black', 'halo': True},
            'city2':   {'fontsize': 9, 'weight': 'normal', 'family': 'serif', 'color': '#222222', 'halo': True},
            'city3':   {'fontsize': 8, 'weight': 'normal', 'family': 'serif', 'color': '#444444', 'halo': True},
            'modern_place': {'fontsize': 7, 'style': 'italic', 'weight': 'normal', 'family': 'sans-serif', 'color': '#777777', 'halo': True},
            'river':   {'fontsize': 6, 'style': 'italic', 'family': 'serif', 'color': '#444444', 'halo': False, 'ha': 'center', 'va': 'center'},
            'region':  {'fontsize': 20, 'family': 'serif', 'color': '#333333', 'alpha': 0.2, 'halo': False},
            'campaign_above': {'fontsize': 9, 'weight': 'normal', 'family': 'serif', 'color': '#222222', 'halo': True},
            'campaign_below': {'fontsize': 8, 'weight': 'normal', 'family': 'serif', 'color': '#333333', 'halo': True},
            'event_text':  {'fontsize': 9, 'weight': 'bold', 'family': 'sans-serif', 'color': '#222222', 'halo': True},
        },

        'event_config': {
            'anchor_radius': 12,
        },

        'city_levels': {
            1: {
                'dot_outer_size': 6,
                'dot_inner_size': 3,
                'dot_style': 'ring',
                'label_style': 'city1',
                'anchor_radius': 8,
                'default_icon': 'capital',
            },
            2: {
                'dot_outer_size': 4,
                'dot_inner_size': None,
                'dot_style': 'solid',
                'label_style': 'city2',
                'anchor_radius': 6,
                'default_icon': 'city',
            },
            3: {
                'dot_outer_size': 3,
                'dot_inner_size': None,
                'dot_style': 'solid',
                'label_style': 'city3',
                'anchor_radius': 5,
                'default_icon': 'city',
            },
            4: {
                'dot_outer_size': 2,
                'dot_inner_size': None,
                'dot_style': 'solid',
                'label_style': 'modern_place',
                'anchor_radius': 4,
                'default_icon': False,
            },
        },

        'campaign_styles': {
            'invasion': {
                'color': '#333333',
                'linewidth': 2.5,
                'linestyle': '-',
                'arrowstyle': 'fancy,head_length=5.5,head_width=5.5',
                'alpha': 0.6,
                'type': 'power',
            },
            'invasion-orange': {
                'color': '#555555',
                'linewidth': 2.5,
                'linestyle': '-',
                'arrowstyle': 'fancy,head_length=5.5,head_width=5.5',
                'alpha': 0.6,
                'type': 'power',
            },
            'invasion-black': {
                'color': '#000000',
                'linewidth': 2.5,
                'linestyle': '-',
                'arrowstyle': 'fancy,head_length=5.5,head_width=5.5',
                'alpha': 0.6,
                'type': 'power',
            },
            'boring': {
                'color': '#666666',
                'linewidth': 1.5,
                'linestyle': '--',
                'arrowstyle': '-|>',
                'alpha': 0.7,
                'type': 'simple',
            },
            'retreat': {
                'color': '#888888',
                'linewidth': 1.8,
                'linestyle': (0, (3, 5, 1, 5)),
                'arrowstyle': 'simple,tail_width=0.2',
                'alpha': 0.6,
            },
            'siege-harrasment': {
                'color': '#222222',
                'linewidth': 3,
                'linestyle': ':',
                'arrowstyle': '-',
                'alpha': 0.9,
            },
        },

        'narrative_style': {
            'body_fontsize': 8,
            'label_fontsize': 9,
            'font_family': 'serif',
            'text_color': '#222222',
            'box_width_frac': 0.30,
            'marker_radius': 6,
            'marker_color': '#222222',
            'marker_linewidth': 1.5,
            'para_gap_factor': 0.8,
            'wrap_width': 50,
        },

    },
}


def apply_theme(theme_name):
    """
    Apply a theme by mutating the stylemaps module-level dicts in place.

    All modules that imported references to these dicts (labels.py, styles.py,
    events.py, etc.) will automatically see the updated values.

    Args:
        theme_name: Key in THEMES dict (e.g. 'eighties-textbook', 'bw-print')

    Returns:
        The full theme dict (for reading non-stylemaps settings like
        'background', 'title_style', 'iconset', etc.)

    Raises:
        ValueError: If theme_name is not found in THEMES
    """
    if theme_name not in THEMES:
        available = ', '.join(sorted(THEMES.keys()))
        raise ValueError(f"Unknown theme '{theme_name}'. Available: {available}")

    theme = THEMES[theme_name]
    logger.info(f"Applying theme: {theme_name}")

    import history_cartopy.stylemaps as sm

    sm.LABEL_STYLES.clear()
    sm.LABEL_STYLES.update(theme['label_styles'])

    sm.CITY_LEVELS.clear()
    sm.CITY_LEVELS.update(theme['city_levels'])

    sm.CAMPAIGN_STYLES.clear()
    sm.CAMPAIGN_STYLES.update(theme['campaign_styles'])


    sm.EVENT_CONFIG.clear()
    sm.EVENT_CONFIG.update(theme['event_config'])

    sm.TITLE_STYLE.clear()
    sm.TITLE_STYLE.update(theme['title_style'])

    return theme


def list_themes():
    """Return sorted list of available theme names."""
    return sorted(THEMES.keys())
