"""
Placement manager for label and icon overlap detection.

Tracks all placed elements on the map and detects overlaps
using bounding box intersection.
"""

import logging
import math
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger('history_cartopy.placement')


# Priority levels for different element types
# Higher priority = placed first, keeps preferred position
# Lower priority = placed later, may need to move to avoid overlaps
PRIORITY = {
    # Fixed elements (dots, icons) - high priority
    'city_level_1': 100,  # Capital dot
    'event_icon': 90,
    'city_level_2': 80,   # Major city dot
    'city_level_3': 70,   # Minor city dot
    'city_level_4': 60,   # Modern place dot
    # Campaign arrows - medium-high priority (labels avoid these)
    'campaign_arrow': 55,
    # Labels - lower priority so they can move around anchors
    'city_label_1': 48,   # Capital label
    'city_label_2': 46,   # Major city label
    'city_label_3': 44,   # Minor city label
    'city_label_4': 42,   # Modern place label
    'campaign_label': 40,
    'event_label': 38,
    'river': 35,
    'region': 30,
}


@dataclass
class LabelCandidate:
    """A label with multiple candidate positions for greedy resolution."""
    id: str
    element_type: str  # 'city_label', 'event_label', etc.
    priority: int
    group: Optional[str]
    # The different positions this label could take (in preference order)
    positions: list  # list[PlacementElement]
    # After resolution
    resolved_idx: int = -1  # Which position was chosen (-1 = not resolved)

    @property
    def resolved(self):
        """Get the resolved PlacementElement."""
        if self.resolved_idx < 0:
            raise ValueError(f"Candidate '{self.id}' not yet resolved")
        return self.positions[self.resolved_idx]


@dataclass
class ArrowCandidate:
    """A campaign arrow with multiple gap distance options."""
    id: str
    campaign_idx: int
    priority: int
    group: str
    # Arrow variants at different gap distances
    # Each has 'gap_multiplier', 'path', 'geometry'
    variants: list
    # After resolution
    resolved_idx: int = -1

    @property
    def resolved_path(self):
        """Get the resolved arrow path."""
        if self.resolved_idx < 0:
            raise ValueError(f"Arrow {self.id} not yet resolved")
        return self.variants[self.resolved_idx]['path']

    @property
    def resolved_gap(self):
        """Get the resolved gap multiplier."""
        if self.resolved_idx < 0:
            raise ValueError(f"Arrow {self.id} not yet resolved")
        return self.variants[self.resolved_idx]['gap_multiplier']

    @property
    def resolved_geometry(self):
        """Get the resolved geometry dict."""
        if self.resolved_idx < 0:
            raise ValueError(f"Arrow {self.id} not yet resolved")
        return self.variants[self.resolved_idx]['geometry']


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
        element_type: str = 'city_label',
        group: str = None,
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
            group: Group ID - elements in same group don't count as overlapping
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
            group=group,
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
        element_type: str = 'city_icon',
        group: str = None,
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
            group: Group ID - elements in same group don't count as overlapping
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
            group=group,
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
        group: str = None,
    ) -> PlacementElement:
        """
        Add a city dot element.

        Args:
            id: Unique identifier
            coords: (lon, lat) position
            size_pts: Dot size in points
            priority: Higher = more important
            group: Group ID - elements in same group don't count as overlapping
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
            group=group,
        )

        self.elements[id] = element
        return element

    def add_campaign_label(
        self,
        id: str,
        coords: tuple,
        text: str,
        fontsize: float,
        rotation: float,
        normal: tuple,
        gap_pts: float = 8,
        priority: int = None,
        group: str = None,
    ) -> PlacementElement:
        """
        Add a campaign label element (rotated text along path).

        Args:
            id: Unique identifier
            coords: (lon, lat) anchor point (segment midpoint)
            text: Label text
            fontsize: Font size in points
            rotation: Rotation angle in degrees
            normal: (nx, ny) unit normal for offset direction
            gap_pts: Offset from anchor in points
            priority: Higher = more important
            group: Elements in same group don't count as overlapping
        """
        if priority is None:
            priority = PRIORITY['campaign_label']

        # Text dimensions in points
        char_width = fontsize * 0.6
        text_width_pts = len(text) * char_width
        text_height_pts = fontsize * 1.2

        # Convert to degrees
        text_width_deg = text_width_pts * self.dpp
        text_height_deg = text_height_pts * self.dpp
        gap_deg = gap_pts * self.dpp

        # Offset along normal
        x_offset_deg = normal[0] * gap_deg
        y_offset_deg = normal[1] * gap_deg

        # Center of rotated text
        center_x = coords[0] + x_offset_deg
        center_y = coords[1] + y_offset_deg

        # AABB for rotated rectangle
        rad = math.radians(rotation)
        cos_r, sin_r = abs(math.cos(rad)), abs(math.sin(rad))
        aabb_width = text_width_deg * cos_r + text_height_deg * sin_r
        aabb_height = text_width_deg * sin_r + text_height_deg * cos_r

        bbox = (
            center_x - aabb_width / 2,
            center_y - aabb_height / 2,
            center_x + aabb_width / 2,
            center_y + aabb_height / 2,
        )

        element = PlacementElement(
            id=id,
            type='campaign_label',
            coords=coords,
            offset=(x_offset_deg, y_offset_deg),
            bbox=bbox,
            priority=priority,
            text=text,
            group=group,
        )

        self.elements[id] = element
        logger.debug(f"Added campaign label '{id}': {text}")
        return element

    def add_river_label(
        self,
        id: str,
        coords: tuple,
        text: str,
        fontsize: float,
        rotation: float = 0,
        priority: int = None,
        group: str = None,
        normal: tuple = None,
        gap_pts: float = 0,
    ) -> PlacementElement:
        """
        Add a river label element (rotated text with AABB bbox).

        Args:
            id: Unique identifier
            coords: (lon, lat) position
            text: Label text
            fontsize: Font size in points
            rotation: Rotation angle in degrees
            priority: Higher = more important
            group: Elements in same group don't count as overlapping
            normal: (nx, ny) unit normal vector perpendicular to river
            gap_pts: Offset distance in points along normal direction
        """
        if priority is None:
            priority = PRIORITY.get('river', 35)

        # Calculate offset from normal and gap
        if normal and gap_pts:
            gap_deg = gap_pts * self.dpp
            x_offset_deg = normal[0] * gap_deg
            y_offset_deg = normal[1] * gap_deg
        else:
            x_offset_deg, y_offset_deg = 0, 0

        # Text dimensions in points
        char_width = fontsize * 0.6
        text_width_pts = len(text) * char_width
        text_height_pts = fontsize * 1.2

        # Convert to degrees
        text_width_deg = text_width_pts * self.dpp
        text_height_deg = text_height_pts * self.dpp

        # Center of rotated text is at coords + offset
        center_x = coords[0] + x_offset_deg
        center_y = coords[1] + y_offset_deg

        # AABB for rotated rectangle
        rad = math.radians(rotation)
        cos_r, sin_r = abs(math.cos(rad)), abs(math.sin(rad))
        aabb_width = text_width_deg * cos_r + text_height_deg * sin_r
        aabb_height = text_width_deg * sin_r + text_height_deg * cos_r

        bbox = (
            center_x - aabb_width / 2,
            center_y - aabb_height / 2,
            center_x + aabb_width / 2,
            center_y + aabb_height / 2,
        )

        element = PlacementElement(
            id=id,
            type='river',
            coords=coords,
            offset=(x_offset_deg, y_offset_deg),
            bbox=bbox,
            priority=priority,
            text=text,
            group=group,
        )
        # Store rotation and normal for rendering
        element.rotation = rotation
        element.normal = normal

        self.elements[id] = element
        logger.debug(f"Added river label '{id}': {text} at {coords}, gap={gap_pts}pts")
        return element

    def add_campaign_arrow(
        self,
        id: str,
        path: list,
        linewidth_pts: float = 2.5,
        priority: int = None,
        group: str = None,
        segment_length: int = 10,
    ) -> list:
        """
        Add a campaign arrow path as multiple segment elements.

        Instead of one large bounding box for the entire path, we break it
        into smaller segments with tighter bounding boxes. This allows labels
        to find positions that don't overlap with the actual arrow path.

        Args:
            id: Base identifier (segments will be id_0, id_1, etc.)
            path: List of (lon, lat) coordinates forming the arrow path
            linewidth_pts: Line width in points
            priority: Higher = more important
            group: Elements in same group don't count as overlapping
            segment_length: Number of points per segment

        Returns:
            List of PlacementElements created (one per segment)
        """
        if priority is None:
            priority = PRIORITY.get('campaign_arrow', 55)

        if path is None or len(path) < 2:
            logger.warning(f"Campaign arrow '{id}' has invalid path")
            return []

        # Minimal padding for line width
        padding = linewidth_pts * self.dpp

        elements = []
        num_points = len(path)

        # Break path into segments
        for seg_start in range(0, num_points - 1, segment_length):
            seg_end = min(seg_start + segment_length + 1, num_points)
            segment = path[seg_start:seg_end]

            if len(segment) < 2:
                continue

            # Compute bounding box for this segment
            lons = [p[0] for p in segment]
            lats = [p[1] for p in segment]

            bbox = (
                min(lons) - padding,
                min(lats) - padding,
                max(lons) + padding,
                max(lats) + padding,
            )

            # Use segment midpoint as coords
            mid_idx = len(segment) // 2
            coords = tuple(segment[mid_idx])

            seg_id = f"{id}_seg{seg_start}"
            element = PlacementElement(
                id=seg_id,
                type='campaign_arrow',
                coords=coords,
                offset=(0, 0),
                bbox=bbox,
                priority=priority,
                group=group,
            )

            self.elements[seg_id] = element
            elements.append(element)

        logger.debug(f"Added campaign arrow '{id}' as {len(elements)} segments")
        return elements

    def would_overlap(self, element: PlacementElement) -> list[PlacementElement]:
        """
        Check if an element would overlap with existing elements.
        Does NOT add the element to the manager.

        Args:
            element: PlacementElement to check

        Returns:
            List of existing elements that would overlap
        """
        overlapping = []
        for existing in self.elements.values():
            # Skip same group
            if element.group and existing.group and element.group == existing.group:
                continue
            if self._bbox_intersects(element.bbox, existing.bbox):
                overlapping.append(existing)
        return overlapping

    def remove(self, id: str) -> bool:
        """
        Remove an element by ID.

        Returns:
            True if removed, False if not found
        """
        if id in self.elements:
            del self.elements[id]
            return True
        return False

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
                # Skip same group (e.g., above/below labels on same campaign)
                if e1.group and e2.group and e1.group == e2.group:
                    continue
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

    def resolve_greedy(self, candidates: list) -> dict:
        """
        Resolve label positions using priority-ordered greedy algorithm.

        For each candidate (sorted by priority), tries positions in preference
        order and picks the first that doesn't overlap with already-placed elements.

        Args:
            candidates: List of LabelCandidate with multiple positions each

        Returns:
            Dict mapping element ID to resolved PlacementElement
        """
        # Sort by priority (highest first)
        sorted_candidates = sorted(candidates, key=lambda c: -c.priority)

        resolved = {}
        unresolved = []

        for candidate in sorted_candidates:
            placed = False
            rejection_reasons = []  # Track why each position was rejected

            for idx, position in enumerate(candidate.positions):
                # Check against already-resolved elements
                overlaps = self.would_overlap(position)
                if not overlaps:
                    # Success - use this position
                    self.elements[position.id] = position
                    candidate.resolved_idx = idx
                    resolved[candidate.id] = position
                    placed = True
                    logger.debug(f"Placed '{candidate.id}' at position {idx}")
                    break
                else:
                    # Track what caused the rejection
                    overlap_ids = [o.id for o in overlaps]
                    rejection_reasons.append((idx, overlap_ids))

            if not placed:
                # All positions overlap - use first (preferred) and log warning
                position = candidate.positions[0]
                self.elements[position.id] = position
                candidate.resolved_idx = 0
                resolved[candidate.id] = position
                unresolved.append(candidate)
                logger.warning(f"Could not place '{candidate.id}' without overlap")
                # Log detailed rejection reasons
                for pos_idx, overlap_ids in rejection_reasons:
                    logger.debug(f"  Position {pos_idx} rejected due to: {overlap_ids}")

        if unresolved:
            logger.info(f"Greedy resolution: {len(resolved)} placed, {len(unresolved)} with overlaps")
        else:
            logger.debug(f"Greedy resolution: {len(resolved)} placed, all without overlap")

        return resolved

    def resolve_arrows(self, arrow_candidates: list) -> dict:
        """
        Resolve arrow gap distances using greedy algorithm.

        Tries shortest gap (2x) first, falls back to larger gaps (3x, 4x) if conflicts.

        Args:
            arrow_candidates: List of ArrowCandidate, each with variants at different gaps

        Returns:
            Dict mapping arrow ID to resolved ArrowCandidate
        """
        resolved = {}

        for candidate in arrow_candidates:
            placed = False

            for idx, variant in enumerate(candidate.variants):
                # Create temporary segment elements for overlap check
                temp_elements = self._create_arrow_segments_temp(
                    f"temp_{candidate.id}",
                    variant['path'],
                    linewidth_pts=2.5
                )

                # Check if any segment overlaps with existing elements
                has_overlap = False
                for elem in temp_elements:
                    if self.would_overlap(elem):
                        has_overlap = True
                        break

                if not has_overlap:
                    # Success - use this gap distance
                    candidate.resolved_idx = idx
                    # Add actual segments to PM
                    self.add_campaign_arrow(
                        candidate.id,
                        path=variant['path'],
                        linewidth_pts=2.5,
                        priority=candidate.priority,
                        group=candidate.group,
                    )
                    resolved[candidate.id] = candidate
                    placed = True
                    logger.debug(f"Arrow {candidate.id} placed at {variant['gap_multiplier']}x gap")
                    break

            if not placed:
                # All gaps conflict - use largest (4x) and log warning
                candidate.resolved_idx = len(candidate.variants) - 1
                variant = candidate.variants[-1]
                self.add_campaign_arrow(
                    candidate.id,
                    path=variant['path'],
                    linewidth_pts=2.5,
                    priority=candidate.priority,
                    group=candidate.group,
                )
                resolved[candidate.id] = candidate
                logger.warning(f"Arrow {candidate.id} conflicts even at {variant['gap_multiplier']}x gap")

        return resolved

    def _create_arrow_segments_temp(
        self,
        id: str,
        path: list,
        linewidth_pts: float = 2.5,
        segment_length: int = 10,
    ) -> list:
        """
        Create temporary PlacementElements for arrow segments without adding to manager.

        Used for checking overlaps before committing to a particular arrow variant.

        Args:
            id: Base identifier
            path: List of (lon, lat) coordinates
            linewidth_pts: Line width in points
            segment_length: Number of points per segment

        Returns:
            List of PlacementElements (not added to self.elements)
        """
        if path is None or len(path) < 2:
            return []

        # Minimal padding for line width
        padding = linewidth_pts * self.dpp

        elements = []
        num_points = len(path)

        # Break path into segments
        for seg_start in range(0, num_points - 1, segment_length):
            seg_end = min(seg_start + segment_length + 1, num_points)
            segment = path[seg_start:seg_end]

            if len(segment) < 2:
                continue

            # Compute bounding box for this segment
            lons = [p[0] for p in segment]
            lats = [p[1] for p in segment]

            bbox = (
                min(lons) - padding,
                min(lats) - padding,
                max(lons) + padding,
                max(lats) + padding,
            )

            # Use segment midpoint as coords
            mid_idx = len(segment) // 2
            coords = tuple(segment[mid_idx])

            seg_id = f"{id}_seg{seg_start}"
            element = PlacementElement(
                id=seg_id,
                type='campaign_arrow',
                coords=coords,
                offset=(0, 0),
                bbox=bbox,
                priority=PRIORITY.get('campaign_arrow', 55),
                group=None,  # No group for temp elements
            )

            elements.append(element)

        return elements
