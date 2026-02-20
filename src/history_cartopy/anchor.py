"""
Anchor Circle System for automatic placement of city attachments.

Each location has an invisible anchor circle. Attachments (labels, icons,
campaign arrows) terminate on this circle's perimeter, distributed evenly.
"""
import math
import numpy as np

from history_cartopy.themes import CITY_LEVELS

# Default angles for attachment types (degrees, 0 = North/Up, clockwise)
DEFAULT_ANGLES = {
    'icon': 0,      # Above (North)
    'label': 135,   # Southeast
}

# Position angles for 8-position Imhof model (degrees from North, clockwise)
POSITION_ANGLES = {
    'NE': 45,    # Priority 1 (Imhof's preferred)
    'E': 90,     # Priority 2
    'NW': 315,   # Priority 3
    'W': 270,    # Priority 4
    'SE': 135,   # Priority 5
    'SW': 225,   # Priority 6
    'N': 0,      # Priority 7
    'S': 180,    # Priority 8
}

# Position names in priority order (Imhof's preference)
POSITION_PRIORITY = ['NE', 'E', 'NW', 'W', 'SE', 'SW', 'N', 'S']

# Text alignment for each position (ha, va)
# This ensures text extends away from the anchor point
POSITION_ALIGNMENT = {
    'N':  ('center', 'bottom'),  # Text centered above
    'S':  ('center', 'top'),     # Text centered below
    'E':  ('left', 'center'),    # Text to the right
    'W':  ('right', 'center'),   # Text to the left
    'NE': ('left', 'bottom'),    # Text to upper-right
    'NW': ('right', 'bottom'),   # Text to upper-left
    'SE': ('left', 'top'),       # Text to lower-right
    'SW': ('right', 'top'),      # Text to lower-left
}


class AnchorCircle:
    """
    Manages attachment placement around a location's anchor circle.

    The circle is conceptual - it exists in "offset space" (points, not degrees).
    Attachments register themselves, then resolve() distributes them evenly.
    """

    def __init__(self, city_level=2):
        """
        Args:
            city_level: 1, 2, or 3 - determines circle radius from CITY_LEVELS
        """
        level_config = CITY_LEVELS.get(city_level, CITY_LEVELS[2])
        self.radius = level_config['anchor_radius']
        self.attachments = []  # List of (type, priority, preferred_angle)
        self._resolved = False
        self._angles = {}  # Maps attachment index to final angle

    def add_attachment(self, attachment_type, preferred_angle=None, priority=0):
        """
        Register an attachment to be placed on the circle.

        Args:
            attachment_type: 'label', 'icon', or 'campaign_in'/'campaign_out'
            preferred_angle: Desired angle in degrees (0=N, 90=E, 180=S, 270=W)
                            If None, uses default for attachment_type
            priority: Higher priority attachments get their preferred angles

        Returns:
            Index of this attachment (used to retrieve final position)
        """
        if preferred_angle is None:
            preferred_angle = DEFAULT_ANGLES.get(attachment_type, 45)

        idx = len(self.attachments)
        self.attachments.append({
            'type': attachment_type,
            'preferred_angle': preferred_angle,
            'priority': priority,
            'index': idx
        })
        self._resolved = False
        return idx

    def resolve(self):
        """
        Calculate final angles for all attachments.

        Algorithm:
        - 1 item: use its preferred angle
        - 2 items: place 180 degrees apart, starting from first item's preference
        - 3+ items: distribute evenly, respecting campaign arrow directions
        """
        n = len(self.attachments)
        if n == 0:
            self._resolved = True
            return

        if n == 1:
            # Single attachment: use preferred angle
            self._angles[0] = self.attachments[0]['preferred_angle']

        elif n == 2:
            # Two attachments: 180 degrees apart
            # Sort by priority to give higher priority item its preference
            sorted_items = sorted(self.attachments, key=lambda x: -x['priority'])
            first_angle = sorted_items[0]['preferred_angle']
            self._angles[sorted_items[0]['index']] = first_angle
            self._angles[sorted_items[1]['index']] = (first_angle + 180) % 360

        else:
            # 3+ items: distribute evenly starting from 0 (North)
            # Campaign arrows get priority for their natural direction
            campaigns = [a for a in self.attachments if 'campaign' in a['type']]
            others = [a for a in self.attachments if 'campaign' not in a['type']]

            # Assign campaigns their preferred angles first
            used_angles = set()
            for c in campaigns:
                angle = c['preferred_angle']
                # Snap to nearest available slot
                slot_size = 360 / n
                snapped = round(angle / slot_size) * slot_size
                while snapped in used_angles:
                    snapped = (snapped + slot_size) % 360
                self._angles[c['index']] = snapped
                used_angles.add(snapped)

            # Distribute remaining items in unused slots
            all_slots = set(i * (360 / n) for i in range(n))
            free_slots = sorted(all_slots - used_angles)

            for i, item in enumerate(others):
                if i < len(free_slots):
                    self._angles[item['index']] = free_slots[i]
                else:
                    # Fallback: squeeze in at end
                    self._angles[item['index']] = (max(used_angles) + 30) % 360

        self._resolved = True

    def get_offset(self, attachment_index):
        """
        Get the x, y offset in points for an attachment.

        Args:
            attachment_index: Index returned by add_attachment()

        Returns:
            (x_offset, y_offset) in points
        """
        if not self._resolved:
            self.resolve()

        angle_deg = self._angles.get(attachment_index, 0)
        # Convert to radians (0 = North, clockwise)
        # Math convention: 0 = East, counter-clockwise
        # So we adjust: math_angle = 90 - our_angle
        angle_rad = math.radians(90 - angle_deg)

        x = self.radius * math.cos(angle_rad)
        y = self.radius * math.sin(angle_rad)

        return x, y

    def get_angle(self, attachment_index):
        """Get the resolved angle for an attachment in degrees."""
        if not self._resolved:
            self.resolve()
        return self._angles.get(attachment_index, 0)

    def get_candidate_offsets(self, gap_pts: float = 0, text_height_pts: float = 0) -> list[tuple]:
        """
        Generate 8 candidate label offsets around the anchor circle.

        Uses Imhof's 8-position model in priority order (NE, E, NW, W, SE, SW, N, S).

        Args:
            gap_pts: Additional gap between anchor edge and label start (in points)
            text_height_pts: Height of the label text (used to adjust vertical positions)

        Returns:
            List of (position_name, x_offset_pts, y_offset_pts, ha, va) in priority order
        """
        candidates = []
        total_radius = self.radius + gap_pts

        for pos_name in POSITION_PRIORITY:
            angle_deg = POSITION_ANGLES[pos_name]
            # Convert to radians (0 = North, clockwise)
            # Math convention: 0 = East, counter-clockwise
            # So we adjust: math_angle = 90 - our_angle
            angle_rad = math.radians(90 - angle_deg)

            x_offset = total_radius * math.cos(angle_rad)
            y_offset = total_radius * math.sin(angle_rad)

            # Get alignment for this position
            ha, va = POSITION_ALIGNMENT[pos_name]

            candidates.append((pos_name, x_offset, y_offset, ha, va))

        return candidates


def compute_campaign_angle(from_coords, to_coords):
    """
    Compute the natural angle for a campaign arrow endpoint.

    Args:
        from_coords: (lon, lat) of arrow origin
        to_coords: (lon, lat) of arrow destination

    Returns:
        Angle in degrees (0=N, 90=E, 180=S, 270=W)
    """
    dx = to_coords[0] - from_coords[0]
    dy = to_coords[1] - from_coords[1]

    # atan2 gives angle from East, counter-clockwise
    math_angle = math.degrees(math.atan2(dy, dx))
    # Convert to 0=North, clockwise
    our_angle = (90 - math_angle) % 360

    return our_angle
