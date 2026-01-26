"""Tests for placement module - overlap detection and bounding boxes."""

import pytest
from history_cartopy.placement import PlacementManager, PlacementElement, LabelCandidate, ArrowCandidate, PRIORITY


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


class TestLabelCandidate:
    """Tests for LabelCandidate dataclass."""

    def test_label_candidate_creation(self):
        """Should create LabelCandidate with required fields."""
        positions = [
            PlacementElement(
                id='test_pos1', type='city_label',
                coords=(0, 0), offset=(0.1, 0.1),
                bbox=(0, 0, 1, 1), priority=50
            ),
            PlacementElement(
                id='test_pos2', type='city_label',
                coords=(0, 0), offset=(0.2, 0.2),
                bbox=(0, 0, 1, 1), priority=50
            ),
        ]
        candidate = LabelCandidate(
            id='test_label',
            element_type='city_label',
            priority=80,
            group='city_test',
            positions=positions,
        )
        assert candidate.id == 'test_label'
        assert candidate.element_type == 'city_label'
        assert candidate.priority == 80
        assert len(candidate.positions) == 2
        assert candidate.resolved_idx == -1

    def test_resolved_property_raises_before_resolve(self):
        """Accessing resolved before resolution should raise."""
        candidate = LabelCandidate(
            id='test',
            element_type='city_label',
            priority=50,
            group=None,
            positions=[],
        )
        with pytest.raises(ValueError, match="not yet resolved"):
            _ = candidate.resolved

    def test_resolved_property_returns_correct_element(self):
        """resolved property should return the chosen position."""
        pos1 = PlacementElement(
            id='test', type='city_label',
            coords=(0, 0), offset=(0.1, 0.1),
            bbox=(0, 0, 1, 1), priority=50, text='First'
        )
        pos2 = PlacementElement(
            id='test', type='city_label',
            coords=(0, 0), offset=(0.2, 0.2),
            bbox=(0, 0, 1, 1), priority=50, text='Second'
        )
        candidate = LabelCandidate(
            id='test',
            element_type='city_label',
            priority=50,
            group=None,
            positions=[pos1, pos2],
        )
        candidate.resolved_idx = 1
        assert candidate.resolved == pos2
        assert candidate.resolved.text == 'Second'


class TestResolveGreedy:
    """Tests for PlacementManager.resolve_greedy method."""

    @pytest.fixture
    def manager(self):
        """Create a PlacementManager with dpp=0.01."""
        return PlacementManager(dpp=0.01)

    def test_resolve_greedy_empty_list(self, manager):
        """Empty candidates list should return empty dict."""
        resolved = manager.resolve_greedy([])
        assert resolved == {}

    def test_resolve_greedy_single_candidate(self, manager):
        """Single candidate should use first position."""
        pos = PlacementElement(
            id='test', type='city_label',
            coords=(0, 0), offset=(0.1, 0.1),
            bbox=(0, 0, 0.1, 0.1), priority=50
        )
        candidate = LabelCandidate(
            id='test',
            element_type='city_label',
            priority=50,
            group=None,
            positions=[pos],
        )
        resolved = manager.resolve_greedy([candidate])
        assert 'test' in resolved
        assert candidate.resolved_idx == 0

    def test_resolve_greedy_no_overlaps(self, manager):
        """Non-overlapping candidates should all use first position."""
        # Two candidates far apart
        pos1 = PlacementElement(
            id='label1', type='city_label',
            coords=(0, 0), offset=(0, 0),
            bbox=(0, 0, 0.1, 0.1), priority=50
        )
        pos2 = PlacementElement(
            id='label2', type='city_label',
            coords=(10, 10), offset=(0, 0),
            bbox=(10, 10, 10.1, 10.1), priority=50
        )
        c1 = LabelCandidate(id='label1', element_type='city_label',
                           priority=50, group=None, positions=[pos1])
        c2 = LabelCandidate(id='label2', element_type='city_label',
                           priority=50, group=None, positions=[pos2])

        resolved = manager.resolve_greedy([c1, c2])
        assert len(resolved) == 2
        assert c1.resolved_idx == 0
        assert c2.resolved_idx == 0

    def test_resolve_greedy_picks_first_available(self, manager):
        """Should pick first non-overlapping position."""
        # Add an obstacle at position (0, 0)
        manager.add_dot('obstacle', coords=(0, 0), size_pts=100)  # 1 deg bbox

        # Create candidate with 3 positions - first overlaps, second doesn't
        pos1 = PlacementElement(
            id='test', type='city_label',
            coords=(0, 0), offset=(0, 0),
            bbox=(-0.2, -0.2, 0.2, 0.2), priority=50  # Overlaps obstacle
        )
        pos2 = PlacementElement(
            id='test', type='city_label',
            coords=(0, 0), offset=(2, 0),
            bbox=(1.8, -0.2, 2.2, 0.2), priority=50  # No overlap
        )
        pos3 = PlacementElement(
            id='test', type='city_label',
            coords=(0, 0), offset=(3, 0),
            bbox=(2.8, -0.2, 3.2, 0.2), priority=50  # No overlap
        )
        candidate = LabelCandidate(
            id='test',
            element_type='city_label',
            priority=50,
            group=None,
            positions=[pos1, pos2, pos3],
        )

        resolved = manager.resolve_greedy([candidate])
        assert candidate.resolved_idx == 1  # Second position (first non-overlapping)

    def test_resolve_greedy_priority_order(self, manager):
        """Higher priority candidates should be placed first."""
        # Create two candidates that would overlap at same position
        high_pos = PlacementElement(
            id='high', type='city_label',
            coords=(0, 0), offset=(0, 0),
            bbox=(0, 0, 1, 1), priority=100
        )
        low_pos1 = PlacementElement(
            id='low', type='city_label',
            coords=(0, 0), offset=(0, 0),
            bbox=(0, 0, 1, 1), priority=50  # Overlaps with high
        )
        low_pos2 = PlacementElement(
            id='low', type='city_label',
            coords=(0, 0), offset=(2, 0),
            bbox=(2, 0, 3, 1), priority=50  # Alternative position
        )

        high_cand = LabelCandidate(id='high', element_type='city_label',
                                   priority=100, group=None, positions=[high_pos])
        low_cand = LabelCandidate(id='low', element_type='city_label',
                                  priority=50, group=None, positions=[low_pos1, low_pos2])

        resolved = manager.resolve_greedy([low_cand, high_cand])  # Order shouldn't matter

        # High priority gets first choice (position 0)
        assert high_cand.resolved_idx == 0
        # Low priority must use alternative (position 1)
        assert low_cand.resolved_idx == 1

    def test_resolve_greedy_fallback_to_first(self, manager):
        """When all positions overlap, should use first and log warning."""
        # Add obstacle
        manager.add_dot('obstacle', coords=(0, 0), size_pts=200)

        # All positions overlap
        pos1 = PlacementElement(
            id='test', type='city_label',
            coords=(0, 0), offset=(0, 0),
            bbox=(-0.2, -0.2, 0.2, 0.2), priority=50
        )
        pos2 = PlacementElement(
            id='test', type='city_label',
            coords=(0, 0), offset=(0.1, 0),
            bbox=(-0.1, -0.2, 0.3, 0.2), priority=50
        )
        candidate = LabelCandidate(
            id='test',
            element_type='city_label',
            priority=50,
            group=None,
            positions=[pos1, pos2],
        )

        resolved = manager.resolve_greedy([candidate])
        # Should fall back to first position even though it overlaps
        assert candidate.resolved_idx == 0
        assert 'test' in resolved

    def test_resolve_greedy_respects_groups(self, manager):
        """Elements in same group should not count as overlapping."""
        # Two positions that would overlap, but same group
        pos1 = PlacementElement(
            id='label', type='city_label',
            coords=(0, 0), offset=(0, 0),
            bbox=(0, 0, 1, 1), priority=50, group='city_A'
        )
        # Add a dot in same group
        manager.add_dot('dot', coords=(0.5, 0.5), size_pts=50, group='city_A')

        candidate = LabelCandidate(
            id='label',
            element_type='city_label',
            priority=50,
            group='city_A',
            positions=[pos1],
        )

        resolved = manager.resolve_greedy([candidate])
        # Should succeed at first position (same group doesn't count as overlap)
        assert candidate.resolved_idx == 0


class TestArrowCandidate:
    """Tests for ArrowCandidate dataclass."""

    def test_arrow_candidate_creation(self):
        """Should create ArrowCandidate with required fields."""
        import numpy as np
        path_2x = np.array([[0, 0], [1, 1], [2, 2]])
        path_3x = np.array([[0.1, 0.1], [1.1, 1.1], [2.1, 2.1]])
        path_4x = np.array([[0.2, 0.2], [1.2, 1.2], [2.2, 2.2]])

        variants = [
            {'gap_multiplier': 2.0, 'path': path_2x, 'geometry': {'full_path': path_2x}},
            {'gap_multiplier': 3.0, 'path': path_3x, 'geometry': {'full_path': path_3x}},
            {'gap_multiplier': 4.0, 'path': path_4x, 'geometry': {'full_path': path_4x}},
        ]

        candidate = ArrowCandidate(
            id='campaign_arrow_0',
            campaign_idx=0,
            priority=55,
            group='campaign_0',
            variants=variants,
        )

        assert candidate.id == 'campaign_arrow_0'
        assert candidate.campaign_idx == 0
        assert candidate.priority == 55
        assert len(candidate.variants) == 3
        assert candidate.resolved_idx == -1

    def test_resolved_path_raises_before_resolve(self):
        """Accessing resolved_path before resolution should raise."""
        candidate = ArrowCandidate(
            id='test',
            campaign_idx=0,
            priority=55,
            group='campaign_0',
            variants=[],
        )
        with pytest.raises(ValueError, match="not yet resolved"):
            _ = candidate.resolved_path

    def test_resolved_gap_raises_before_resolve(self):
        """Accessing resolved_gap before resolution should raise."""
        candidate = ArrowCandidate(
            id='test',
            campaign_idx=0,
            priority=55,
            group='campaign_0',
            variants=[],
        )
        with pytest.raises(ValueError, match="not yet resolved"):
            _ = candidate.resolved_gap

    def test_resolved_properties_return_correct_values(self):
        """resolved properties should return correct variant data."""
        import numpy as np
        path_2x = np.array([[0, 0], [1, 1]])
        path_3x = np.array([[0.5, 0.5], [1.5, 1.5]])

        variants = [
            {'gap_multiplier': 2.0, 'path': path_2x, 'geometry': {'full_path': path_2x}},
            {'gap_multiplier': 3.0, 'path': path_3x, 'geometry': {'full_path': path_3x}},
        ]

        candidate = ArrowCandidate(
            id='test',
            campaign_idx=0,
            priority=55,
            group='campaign_0',
            variants=variants,
        )
        candidate.resolved_idx = 1  # Select 3x variant

        assert candidate.resolved_gap == 3.0
        assert candidate.resolved_path is path_3x
        assert candidate.resolved_geometry == {'full_path': path_3x}


class TestResolveArrows:
    """Tests for PlacementManager.resolve_arrows method."""

    @pytest.fixture
    def manager(self):
        """Create a PlacementManager with dpp=0.01."""
        return PlacementManager(dpp=0.01)

    def test_resolve_arrows_empty_list(self, manager):
        """Empty candidates list should return empty dict."""
        resolved = manager.resolve_arrows([])
        assert resolved == {}

    def test_resolve_arrows_picks_shortest(self, manager):
        """Should pick shortest gap (2x) when no conflicts."""
        import numpy as np
        # Create paths far from any obstacles
        path_2x = np.array([[10.0, 10.0], [11.0, 11.0], [12.0, 12.0]])
        path_3x = np.array([[10.5, 10.5], [11.5, 11.5], [12.5, 12.5]])
        path_4x = np.array([[11.0, 11.0], [12.0, 12.0], [13.0, 13.0]])

        variants = [
            {'gap_multiplier': 2.0, 'path': path_2x.tolist(), 'geometry': {'full_path': path_2x}},
            {'gap_multiplier': 3.0, 'path': path_3x.tolist(), 'geometry': {'full_path': path_3x}},
            {'gap_multiplier': 4.0, 'path': path_4x.tolist(), 'geometry': {'full_path': path_4x}},
        ]

        candidate = ArrowCandidate(
            id='campaign_arrow_0',
            campaign_idx=0,
            priority=55,
            group='campaign_0',
            variants=variants,
        )

        resolved = manager.resolve_arrows([candidate])

        assert 'campaign_arrow_0' in resolved
        assert candidate.resolved_idx == 0  # 2x chosen
        assert candidate.resolved_gap == 2.0

    def test_resolve_arrows_falls_back_to_larger_gap(self, manager):
        """Should fall back to 3x or 4x when 2x conflicts with obstacles."""
        import numpy as np

        # Add an obstacle that the 2x path will overlap
        manager.add_dot('obstacle', coords=(0.5, 0.5), size_pts=100)  # 1 deg bbox at (0.5, 0.5)

        # 2x path goes through obstacle, 3x path avoids it
        path_2x = np.array([[0.0, 0.0], [0.5, 0.5], [1.0, 1.0]])  # Through obstacle
        path_3x = np.array([[0.0, 2.0], [0.5, 2.5], [1.0, 3.0]])  # Avoids obstacle
        path_4x = np.array([[0.0, 3.0], [0.5, 3.5], [1.0, 4.0]])  # Also avoids

        variants = [
            {'gap_multiplier': 2.0, 'path': path_2x.tolist(), 'geometry': {'full_path': path_2x}},
            {'gap_multiplier': 3.0, 'path': path_3x.tolist(), 'geometry': {'full_path': path_3x}},
            {'gap_multiplier': 4.0, 'path': path_4x.tolist(), 'geometry': {'full_path': path_4x}},
        ]

        candidate = ArrowCandidate(
            id='campaign_arrow_0',
            campaign_idx=0,
            priority=55,
            group='campaign_0',
            variants=variants,
        )

        resolved = manager.resolve_arrows([candidate])

        assert 'campaign_arrow_0' in resolved
        assert candidate.resolved_idx == 1  # 3x chosen (first non-overlapping)
        assert candidate.resolved_gap == 3.0

    def test_resolve_arrows_uses_largest_when_all_conflict(self, manager):
        """Should use largest gap (4x) and log warning when all gaps conflict."""
        import numpy as np

        # Add a large obstacle that all paths will overlap
        manager.add_dot('big_obstacle', coords=(0.5, 0.5), size_pts=500)  # 5 deg bbox

        # All paths go through the obstacle
        path_2x = np.array([[0.0, 0.0], [0.5, 0.5], [1.0, 1.0]])
        path_3x = np.array([[0.0, 0.0], [0.5, 0.5], [1.0, 1.0]])
        path_4x = np.array([[0.0, 0.0], [0.5, 0.5], [1.0, 1.0]])

        variants = [
            {'gap_multiplier': 2.0, 'path': path_2x.tolist(), 'geometry': {'full_path': path_2x}},
            {'gap_multiplier': 3.0, 'path': path_3x.tolist(), 'geometry': {'full_path': path_3x}},
            {'gap_multiplier': 4.0, 'path': path_4x.tolist(), 'geometry': {'full_path': path_4x}},
        ]

        candidate = ArrowCandidate(
            id='campaign_arrow_0',
            campaign_idx=0,
            priority=55,
            group='campaign_0',
            variants=variants,
        )

        resolved = manager.resolve_arrows([candidate])

        assert 'campaign_arrow_0' in resolved
        assert candidate.resolved_idx == 2  # 4x (largest) chosen as fallback
        assert candidate.resolved_gap == 4.0

    def test_resolve_arrows_adds_arrow_segments_to_manager(self, manager):
        """Resolved arrows should add segment elements to the manager."""
        import numpy as np
        path = np.array([[10.0, 10.0], [11.0, 11.0], [12.0, 12.0]])

        variants = [
            {'gap_multiplier': 2.0, 'path': path.tolist(), 'geometry': {'full_path': path}},
        ]

        candidate = ArrowCandidate(
            id='campaign_arrow_0',
            campaign_idx=0,
            priority=55,
            group='campaign_0',
            variants=variants,
        )

        # Before resolve, no arrow segments
        arrow_elements_before = [e for e in manager.elements if 'campaign_arrow' in e]
        assert len(arrow_elements_before) == 0

        manager.resolve_arrows([candidate])

        # After resolve, arrow segments should be added
        arrow_elements_after = [e for e in manager.elements if 'campaign_arrow' in e]
        assert len(arrow_elements_after) > 0

    def test_resolve_arrows_multiple_campaigns(self, manager):
        """Should resolve multiple campaigns independently."""
        import numpy as np

        # Two campaigns far apart
        path1_2x = np.array([[0.0, 0.0], [1.0, 1.0]])
        path1_3x = np.array([[0.1, 0.1], [1.1, 1.1]])
        path2_2x = np.array([[10.0, 10.0], [11.0, 11.0]])
        path2_3x = np.array([[10.1, 10.1], [11.1, 11.1]])

        candidate1 = ArrowCandidate(
            id='campaign_arrow_0',
            campaign_idx=0,
            priority=55,
            group='campaign_0',
            variants=[
                {'gap_multiplier': 2.0, 'path': path1_2x.tolist(), 'geometry': {'full_path': path1_2x}},
                {'gap_multiplier': 3.0, 'path': path1_3x.tolist(), 'geometry': {'full_path': path1_3x}},
            ],
        )

        candidate2 = ArrowCandidate(
            id='campaign_arrow_1',
            campaign_idx=1,
            priority=55,
            group='campaign_1',
            variants=[
                {'gap_multiplier': 2.0, 'path': path2_2x.tolist(), 'geometry': {'full_path': path2_2x}},
                {'gap_multiplier': 3.0, 'path': path2_3x.tolist(), 'geometry': {'full_path': path2_3x}},
            ],
        )

        resolved = manager.resolve_arrows([candidate1, candidate2])

        assert len(resolved) == 2
        assert 'campaign_arrow_0' in resolved
        assert 'campaign_arrow_1' in resolved
        # Both should pick 2x (shortest) since they don't conflict
        assert candidate1.resolved_gap == 2.0
        assert candidate2.resolved_gap == 2.0
