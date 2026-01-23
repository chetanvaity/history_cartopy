"""Tests for placement module - overlap detection and bounding boxes."""

import pytest
from history_cartopy.placement import PlacementManager, PlacementElement, PRIORITY


class TestPlacementElement:
    """Tests for PlacementElement dataclass."""

    def test_center_property(self):
        """Center should be coords + offset."""
        elem = PlacementElement(
            id='test',
            type='city_label',
            coords=(10.0, 20.0),
            offset=(1.0, 2.0),
            bbox=(0, 0, 1, 1),
            priority=50,
        )
        assert elem.center == (11.0, 22.0)

    def test_center_with_zero_offset(self):
        """Center equals coords when offset is zero."""
        elem = PlacementElement(
            id='test',
            type='dot',
            coords=(5.0, 10.0),
            offset=(0, 0),
            bbox=(0, 0, 1, 1),
            priority=100,
        )
        assert elem.center == (5.0, 10.0)


class TestPlacementManager:
    """Tests for PlacementManager."""

    @pytest.fixture
    def manager(self):
        """Create a PlacementManager with dpp=0.01 (1 point = 0.01 degrees)."""
        return PlacementManager(dpp=0.01)

    # --- add_label tests ---

    def test_add_label_creates_element(self, manager):
        """add_label should create and store an element."""
        elem = manager.add_label(
            id='city_london',
            coords=(0.0, 51.5),
            text='London',
            fontsize=10,
        )
        assert 'city_london' in manager.elements
        assert elem.text == 'London'
        assert elem.coords == (0.0, 51.5)

    def test_add_label_calculates_bbox(self, manager):
        """Label bbox should be based on text dimensions."""
        elem = manager.add_label(
            id='test',
            coords=(0.0, 0.0),
            text='ABC',  # 3 chars
            fontsize=10,
            x_offset_pts=0,
            y_offset_pts=0,
        )
        # char_width = 10 * 0.6 = 6 pts
        # text_width = 3 * 6 = 18 pts = 0.18 deg
        # text_height = 10 * 1.2 = 12 pts = 0.12 deg
        # bbox centered at (0 + 0.18/2, 0) = (0.09, 0)
        assert elem.bbox[0] == pytest.approx(0.0, abs=0.001)  # x1
        assert elem.bbox[2] == pytest.approx(0.18, abs=0.001)  # x2
        width = elem.bbox[2] - elem.bbox[0]
        assert width == pytest.approx(0.18, abs=0.001)

    def test_add_label_with_offset(self, manager):
        """Offset should shift the bbox."""
        elem = manager.add_label(
            id='test',
            coords=(0.0, 0.0),
            text='X',
            fontsize=10,
            x_offset_pts=10,  # 0.1 deg
            y_offset_pts=5,   # 0.05 deg
        )
        # Label positioned at offset point
        assert elem.offset == (0.1, 0.05)

    def test_add_label_uses_priority(self, manager):
        """Priority should be stored on element."""
        elem = manager.add_label(
            id='test',
            coords=(0, 0),
            text='Test',
            fontsize=10,
            priority=PRIORITY['city_level_1'],
        )
        assert elem.priority == 100

    # --- add_icon tests ---

    def test_add_icon_creates_square_bbox(self, manager):
        """Icon bbox should be square, centered on position."""
        elem = manager.add_icon(
            id='icon_test',
            coords=(10.0, 20.0),
            size_pts=20,  # 0.2 deg
            x_offset_pts=0,
            y_offset_pts=0,
        )
        # Centered at (10, 20), size 0.2 deg
        assert elem.bbox == pytest.approx((9.9, 19.9, 10.1, 20.1), abs=0.001)

    def test_add_icon_with_offset(self, manager):
        """Icon offset should shift bbox."""
        elem = manager.add_icon(
            id='icon_test',
            coords=(0.0, 0.0),
            size_pts=10,  # 0.1 deg
            x_offset_pts=100,  # 1.0 deg
            y_offset_pts=50,   # 0.5 deg
        )
        # Center at (1.0, 0.5)
        assert elem.bbox[0] == pytest.approx(0.95, abs=0.001)  # x1
        assert elem.bbox[1] == pytest.approx(0.45, abs=0.001)  # y1

    # --- add_dot tests ---

    def test_add_dot_centered_on_coords(self, manager):
        """Dot should be centered exactly on coords with no offset."""
        elem = manager.add_dot(
            id='dot_test',
            coords=(5.0, 5.0),
            size_pts=10,  # 0.1 deg
        )
        assert elem.offset == (0, 0)
        assert elem.bbox == pytest.approx((4.95, 4.95, 5.05, 5.05), abs=0.001)

    def test_add_dot_type_is_dot(self, manager):
        """Dot element type should be 'dot'."""
        elem = manager.add_dot(id='test', coords=(0, 0))
        assert elem.type == 'dot'


class TestBboxIntersection:
    """Tests for bounding box intersection logic."""

    @pytest.fixture
    def manager(self):
        return PlacementManager(dpp=0.01)

    def test_non_overlapping_horizontal(self, manager):
        """Boxes separated horizontally should not intersect."""
        b1 = (0, 0, 1, 1)
        b2 = (2, 0, 3, 1)
        assert manager._bbox_intersects(b1, b2) is False

    def test_non_overlapping_vertical(self, manager):
        """Boxes separated vertically should not intersect."""
        b1 = (0, 0, 1, 1)
        b2 = (0, 2, 1, 3)
        assert manager._bbox_intersects(b1, b2) is False

    def test_overlapping_boxes(self, manager):
        """Overlapping boxes should intersect."""
        b1 = (0, 0, 2, 2)
        b2 = (1, 1, 3, 3)
        assert manager._bbox_intersects(b1, b2) is True

    def test_touching_edges_intersect(self, manager):
        """Boxes sharing an edge should intersect (not strictly less than)."""
        b1 = (0, 0, 1, 1)
        b2 = (1, 0, 2, 1)  # Shares right edge of b1
        # Current implementation: b1[2] < b2[0] is 1 < 1 = False, so they intersect
        assert manager._bbox_intersects(b1, b2) is True

    def test_contained_box(self, manager):
        """Box fully inside another should intersect."""
        b1 = (0, 0, 10, 10)
        b2 = (2, 2, 4, 4)
        assert manager._bbox_intersects(b1, b2) is True

    def test_identical_boxes(self, manager):
        """Identical boxes should intersect."""
        b1 = (5, 5, 10, 10)
        assert manager._bbox_intersects(b1, b1) is True

    def test_diagonal_separation(self, manager):
        """Diagonally separated boxes should not intersect."""
        b1 = (0, 0, 1, 1)
        b2 = (2, 2, 3, 3)
        assert manager._bbox_intersects(b1, b2) is False


class TestOverlapDetection:
    """Tests for detect_overlaps functionality."""

    @pytest.fixture
    def manager(self):
        return PlacementManager(dpp=0.01)

    def test_no_elements_no_overlaps(self, manager):
        """Empty manager should return no overlaps."""
        assert manager.detect_overlaps() == []

    def test_single_element_no_overlaps(self, manager):
        """Single element cannot overlap with itself in the result."""
        manager.add_dot('dot1', coords=(0, 0))
        assert manager.detect_overlaps() == []

    def test_two_separate_elements_no_overlap(self, manager):
        """Non-overlapping elements should return empty list."""
        manager.add_dot('dot1', coords=(0, 0), size_pts=10)
        manager.add_dot('dot2', coords=(10, 10), size_pts=10)
        assert manager.detect_overlaps() == []

    def test_two_overlapping_elements(self, manager):
        """Overlapping elements should be detected."""
        manager.add_dot('dot1', coords=(0, 0), size_pts=100)  # 1 deg radius
        manager.add_dot('dot2', coords=(0.5, 0), size_pts=100)  # overlaps
        overlaps = manager.detect_overlaps()
        assert len(overlaps) == 1
        ids = {overlaps[0][0].id, overlaps[0][1].id}
        assert ids == {'dot1', 'dot2'}

    def test_three_elements_multiple_overlaps(self, manager):
        """Three mutually overlapping elements should produce 3 pairs."""
        # Create three overlapping dots at same location
        manager.add_dot('dot1', coords=(0, 0), size_pts=100)
        manager.add_dot('dot2', coords=(0, 0), size_pts=100)
        manager.add_dot('dot3', coords=(0, 0), size_pts=100)
        overlaps = manager.detect_overlaps()
        assert len(overlaps) == 3  # (1,2), (1,3), (2,3)

    def test_chain_of_overlaps(self, manager):
        """A->B overlaps, B->C overlaps, but A->C doesn't."""
        # A at 0, B at 0.5, C at 1.0 with size 0.6 deg each
        manager.add_dot('A', coords=(0, 0), size_pts=60)
        manager.add_dot('B', coords=(0.5, 0), size_pts=60)
        manager.add_dot('C', coords=(1.0, 0), size_pts=60)
        overlaps = manager.detect_overlaps()
        # A-B overlap, B-C overlap, but A-C don't
        assert len(overlaps) == 2
        overlap_pairs = {(o[0].id, o[1].id) for o in overlaps}
        assert ('A', 'B') in overlap_pairs
        assert ('B', 'C') in overlap_pairs

    def test_label_icon_overlap(self, manager):
        """Labels and icons can overlap."""
        manager.add_label('label1', coords=(0, 0), text='Test', fontsize=10)
        manager.add_icon('icon1', coords=(0, 0), size_pts=50)
        overlaps = manager.detect_overlaps()
        assert len(overlaps) == 1


class TestPriorityConstants:
    """Tests for PRIORITY dictionary."""

    def test_priority_ordering(self):
        """City level 1 should have highest priority."""
        assert PRIORITY['city_level_1'] > PRIORITY['city_level_2']
        assert PRIORITY['city_level_2'] > PRIORITY['city_level_3']
        assert PRIORITY['city_level_3'] > PRIORITY['city_level_4']

    def test_events_between_cities(self):
        """Event icons should be between level 1 and level 2 cities."""
        assert PRIORITY['city_level_1'] > PRIORITY['event_icon']
        assert PRIORITY['event_icon'] > PRIORITY['city_level_2']

    def test_rivers_and_regions_lowest(self):
        """Rivers and regions should have lowest priorities."""
        assert PRIORITY['river'] < PRIORITY['city_level_4']
        assert PRIORITY['region'] < PRIORITY['river']
