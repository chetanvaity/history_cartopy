"""
Placement manager for label and icon overlap detection.

Tracks all placed elements on the map and detects overlaps
using bounding box intersection.
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger('history_cartopy.placement')


# Priority levels for different element types
PRIORITY = {
    'city_level_1': 100,  # Capital
    'event_icon': 90,
    'city_level_2': 80,
    'city_level_3': 70,
    'event_label': 60,
    'city_level_4': 50,   # Modern place
    'river': 40,
    'region': 30,
}


@dataclass
class PlacementElement:
    """Represents a placed label or icon on the map."""
    id: str
    type: str  # 'city_label', 'city_icon', 'event_label', 'event_icon', 'river', 'region'
    coords: tuple  # (lon, lat) - anchor point
    offset: tuple  # (x_offset, y_offset) in degrees
    bbox: tuple  # (x1, y1, x2, y2) in degrees
    priority: int
    text: Optional[str] = None  # For labels
    group: Optional[str] = None  # Group ID - elements in same group don't count as overlapping

    @property
    def center(self):
        """Get center point of element (anchor + offset)."""
        return (self.coords[0] + self.offset[0], self.coords[1] + self.offset[1])


class PlacementManager:
    """
    Tracks all placed elements and detects overlaps.

    Usage:
        pm = PlacementManager(dpp)
        pm.add_label('city_dacca', (90.41, 23.81), 'Dacca', fontsize=10, ...)
        pm.add_icon('icon_dacca', (90.41, 23.81), size_pts=25, ...)
        pm.log_overlaps()
    """

    def __init__(self, dpp: float):
        """
        Initialize placement manager.

        Args:
            dpp: Degrees per point - for converting point offsets to degrees
        """
        self.dpp = dpp
        self.elements: dict[str, PlacementElement] = {}

    def add_label(
        self,
        id: str,
        coords: tuple,
        text: str,
        fontsize: float,
        x_offset_pts: float = 0,
        y_offset_pts: float = 0,
        priority: int = 50,
        element_type: str = 'city_label'
    ) -> PlacementElement:
        """
        Add a label element.

        Args:
            id: Unique identifier
            coords: (lon, lat) anchor point
            text: Label text
            fontsize: Font size in points
            x_offset_pts: X offset from anchor in points
            y_offset_pts: Y offset from anchor in points
            priority: Higher = more important
            element_type: Type of element for categorization
        """
        # Approximate text dimensions in points
        char_width = fontsize * 0.6  # Average character width
        text_width_pts = len(text) * char_width
        text_height_pts = fontsize * 1.2

        # Convert to degrees
        x_offset_deg = x_offset_pts * self.dpp
        y_offset_deg = y_offset_pts * self.dpp
        text_width_deg = text_width_pts * self.dpp
        text_height_deg = text_height_pts * self.dpp

        # Calculate bbox (label positioned with left edge at offset point, vertically centered)
        center_x = coords[0] + x_offset_deg + text_width_deg / 2
        center_y = coords[1] + y_offset_deg

        bbox = (
            center_x - text_width_deg / 2,  # x1
            center_y - text_height_deg / 2,  # y1
            center_x + text_width_deg / 2,  # x2
            center_y + text_height_deg / 2,  # y2
        )

        element = PlacementElement(
            id=id,
            type=element_type,
            coords=coords,
            offset=(x_offset_deg, y_offset_deg),
            bbox=bbox,
            priority=priority,
            text=text,
        )

        self.elements[id] = element
        logger.debug(f"Added label '{id}': {text} at {coords}")
        return element

    def add_icon(
        self,
        id: str,
        coords: tuple,
        size_pts: float = 25,
        x_offset_pts: float = 0,
        y_offset_pts: float = 0,
        priority: int = 50,
        element_type: str = 'city_icon'
    ) -> PlacementElement:
        """
        Add an icon element.

        Args:
            id: Unique identifier
            coords: (lon, lat) anchor point
            size_pts: Icon size in points (default 25 = 50px at zoom 0.5)
            x_offset_pts: X offset from anchor in points
            y_offset_pts: Y offset from anchor in points
            priority: Higher = more important
            element_type: Type of element for categorization
        """
        # Convert to degrees
        x_offset_deg = x_offset_pts * self.dpp
        y_offset_deg = y_offset_pts * self.dpp
        icon_size_deg = size_pts * self.dpp

        # Calculate bbox (icon centered at offset point)
        center_x = coords[0] + x_offset_deg
        center_y = coords[1] + y_offset_deg

        bbox = (
            center_x - icon_size_deg / 2,  # x1
            center_y - icon_size_deg / 2,  # y1
            center_x + icon_size_deg / 2,  # x2
            center_y + icon_size_deg / 2,  # y2
        )

        element = PlacementElement(
            id=id,
            type=element_type,
            coords=coords,
            offset=(x_offset_deg, y_offset_deg),
            bbox=bbox,
            priority=priority,
        )

        self.elements[id] = element
        logger.debug(f"Added icon '{id}' at {coords}")
        return element

    def add_dot(
        self,
        id: str,
        coords: tuple,
        size_pts: float = 6,
        priority: int = 100,
    ) -> PlacementElement:
        """
        Add a city dot element.

        Args:
            id: Unique identifier
            coords: (lon, lat) position
            size_pts: Dot size in points
            priority: Higher = more important
        """
        dot_size_deg = size_pts * self.dpp

        bbox = (
            coords[0] - dot_size_deg / 2,
            coords[1] - dot_size_deg / 2,
            coords[0] + dot_size_deg / 2,
            coords[1] + dot_size_deg / 2,
        )

        element = PlacementElement(
            id=id,
            type='dot',
            coords=coords,
            offset=(0, 0),
            bbox=bbox,
            priority=priority,
        )

        self.elements[id] = element
        return element

    def _bbox_intersects(self, b1: tuple, b2: tuple) -> bool:
        """
        Check if two bounding boxes intersect.

        Args:
            b1, b2: (x1, y1, x2, y2) bounding boxes
        """
        return not (
            b1[2] < b2[0] or  # b1 right edge left of b2 left edge
            b1[0] > b2[2] or  # b1 left edge right of b2 right edge
            b1[3] < b2[1] or  # b1 top edge below b2 bottom edge
            b1[1] > b2[3]     # b1 bottom edge above b2 top edge
        )

    def detect_overlaps(self) -> list[tuple[PlacementElement, PlacementElement]]:
        """
        Detect all overlapping element pairs.

        Returns:
            List of (element1, element2) tuples for overlapping pairs
        """
        overlaps = []
        elements = list(self.elements.values())

        for i, e1 in enumerate(elements):
            for e2 in elements[i + 1:]:
                if self._bbox_intersects(e1.bbox, e2.bbox):
                    overlaps.append((e1, e2))

        return overlaps

    def log_overlaps(self):
        """Detect overlaps and log warnings."""
        overlaps = self.detect_overlaps()

        if not overlaps:
            logger.debug("No overlaps detected")
            return

        logger.warning(f"Detected {len(overlaps)} overlap(s):")
        for e1, e2 in overlaps:
            e1_desc = f"{e1.type} '{e1.text or e1.id}'"
            e2_desc = f"{e2.type} '{e2.text or e2.id}'"
            logger.warning(f"  - {e1_desc} overlaps with {e2_desc}")
