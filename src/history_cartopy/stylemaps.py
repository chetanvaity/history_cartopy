# Global Style Settings
LABEL_STYLES = {
    'city1':   {'fontsize': 10, 'weight': 'bold', 'family': 'serif', 'color': 'black', 'halo': True},
    'city2':   {'fontsize': 9, 'weight': 'normal', 'family': 'serif', 'color': '#333333', 'halo': True},
    'city3':   {'fontsize': 8, 'weight': 'normal', 'family': 'serif', 'color': '#555555', 'halo': True},
    'modern_place': {'fontsize': 7, 'style': 'italic', 'weight': 'normal', 'family': 'sans-serif', 'color': '#888888', 'halo': True},
    'river':   {'fontsize': 6, 'style': 'italic', 'family': 'serif', 'color': '#2c5d87', 'halo': False, 'ha': 'center', 'va': 'center'},
    'region':  {'fontsize': 20, 'family': 'serif', 'color': '#5d4037', 'alpha': 0.2, 'halo': False},
    'campaign_above': {'fontsize': 9, 'weight': 'normal', 'family': 'serif', 'color': 'black', 'halo': True},
    'campaign_below': {'fontsize': 8, 'weight': 'normal', 'family': 'serif', 'color': 'black', 'halo': True},
    'event_text':  {'fontsize': 9, 'weight': 'bold', 'family': 'sans-serif', 'color': '#800020', 'halo': True},
}

# Event configuration
EVENT_CONFIG = {
    'anchor_radius': 12,  # Radius in points for text placement when icon present
}

# City level configuration
# level 1 = major city/capital, level 2 = regular city, level 3 = small town
CITY_LEVELS = {
    1: {
        'dot_outer_size': 6,
        'dot_inner_size': 3,      # Ring style: black outer, white inner
        'dot_style': 'ring',
        'label_style': 'city1',
        'anchor_radius': 8,
        'default_icon': 'capital',
    },
    2: {
        'dot_outer_size': 4,
        'dot_inner_size': None,   # Solid style: no inner dot
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
}

CAMPAIGN_STYLES = {
    'invasion': {
        'color': '#8b0000',      # Dark Red
        'linewidth': 2.5,
        'linestyle': '-',        # Solid line for main force
        'arrowstyle': 'fancy,head_length=5.5,head_width=5.5',
        'alpha': 0.5,
        'type': 'power'
    },
    'invasion-orange': {
        'color': '#E97451',      # Orange
        'linewidth': 2.5,
        'linestyle': '-',        # Solid line for main force
        'arrowstyle': 'fancy,head_length=5.5,head_width=5.5',
        'alpha': 0.5,
        'type': 'power'
    },
    'invasion-black': {
        'color': '#000000',      # Black
        'linewidth': 2.5,
        'linestyle': '-',        # Solid line for main force
        'arrowstyle': 'fancy,head_length=5.5,head_width=5.5',
        'alpha': 0.5,
        'type': 'power'
    },
    'boring': {
        'color': '#d2691e',      # Chocolate/Orange
        'linewidth': 1.5,
        'linestyle': '--',       # Dashed for light cavalry/raids
        'arrowstyle': '-|>',
        'alpha': 0.7,
        'type': 'simple'
    },
    'retreat': {
        'color': '#4a4a4a',      # Grey
        'linewidth': 1.8,
        'linestyle': (0, (3, 5, 1, 5)), # Dash-dot
        'arrowstyle': 'simple,tail_width=0.2',
        'alpha': 0.6
    },
    'siege-harrasment': {
        'color': 'black',
        'linewidth': 3,
        'linestyle': ':',        # Dotted to show encirclement/static position
        'arrowstyle': '-',       # Often sieges are points, but we can use static arcs
        'alpha': 0.9
    }
}

# These define the colours for territories
# There are 3 "types" as well - fuzzy_fill, hatched, edge-tint (core.py)
TERRITORY_STYLES = {
    'empire': {
        'facecolor': '#ffcc00', # Golden/Imperial
        'edgecolor': '#b8860b',
        'alpha': 0.2,           # Keep it faint so terrain/cities show through
        'linewidth': 1.5,
        'linestyle': '-',
    },
    'kingdom1': {
        'facecolor': '#90ee90', # Light Green (Qutb Shahi)
        'edgecolor': '#2e8b57',
        'alpha': 0.1,
        'linewidth': 1.5
    },
    'kingdom2': {
        'facecolor': '#add8e6', # Light Blue (Adil Shahi)
        'edgecolor': '#4682b4',
        'alpha': 0.4,
        'linewidth': 1.5
    },
    'kingdom3': {
        'facecolor': '#666611', # Purple?
        'edgecolor': '#ffffff',
        'alpha': 0.4,
        'linewidth': 1.5
    },
    'kingdom-purple': {
        'facecolor': '#5d3fd3', # Purple/Violet
        'edgecolor': '#ffffff',
        'alpha': 0.2,
        'linewidth': 1.5
    }
}

TITLE_STYLE = {
    'fontsize': 14,
    'fontweight': 'bold',
    'fontfamily': 'serif',
    'color': 'black',
    'pad': 20,
}
