"""Tests for campaign geometry - multi-stop paths and splines."""

import math
import numpy as np
import pytest
from history_cartopy.campaign_styles import (
    _catmull_rom_segment,
    _compute_segment_info,
    _get_multistop_geometry,
    _get_label_candidates,
)


class TestCatmullRomSegment:
    """Tests for Catmull-Rom spline segment generation."""

    def test_returns_correct_shape(self):
        """Should return array with num_samples rows and 2 columns."""
        p0 = np.array([0, 0])
        p1 = np.array([1, 0])
        p2 = np.array([2, 1])
        p3 = np.array([3, 1])
        result = _catmull_rom_segment(p0, p1, p2, p3, num_samples=50)
        assert result.shape == (50, 2)

    def test_starts_at_p1(self):
        """Spline should start at p1."""
        p0 = np.array([0, 0])
        p1 = np.array([1, 0])
        p2 = np.array([2, 1])
        p3 = np.array([3, 1])
        result = _catmull_rom_segment(p0, p1, p2, p3)
        assert result[0] == pytest.approx(p1, abs=0.01)

    def test_ends_at_p2(self):
        """Spline should end at p2."""
        p0 = np.array([0, 0])
        p1 = np.array([1, 0])
        p2 = np.array([2, 1])
        p3 = np.array([3, 1])
        result = _catmull_rom_segment(p0, p1, p2, p3)
        assert result[-1] == pytest.approx(p2, abs=0.01)

    def test_straight_line_when_collinear(self):
        """Collinear points should produce straight line."""
        p0 = np.array([0, 0])
        p1 = np.array([1, 0])
        p2 = np.array([2, 0])
        p3 = np.array([3, 0])
        result = _catmull_rom_segment(p0, p1, p2, p3)
        # All y values should be 0
        assert np.allclose(result[:, 1], 0, atol=0.01)


class TestComputeSegmentInfo:
    """Tests for segment info computation."""

    def test_straight_segment_length(self):
        """Length of straight segment should be Euclidean distance."""
        path = np.array([[0, 0], [3, 4]])  # 3-4-5 triangle
        info = _compute_segment_info(path)
        assert info['length'] == pytest.approx(5.0, abs=0.01)

    def test_midpoint_of_straight_segment(self):
        """Midpoint should be at center of straight segment."""
        # Use multiple points so cumulative length works
        path = np.array([[0, 0], [2, 0], [4, 0], [6, 0], [8, 0], [10, 0]])
        info = _compute_segment_info(path)
        assert info['midpoint'] == pytest.approx([5, 0], abs=1.0)

    def test_normal_perpendicular_to_path(self):
        """Normal should be perpendicular to tangent."""
        path = np.array([[0, 0], [10, 0]])  # Horizontal
        info = _compute_segment_info(path)
        # Normal should be vertical (0, 1) or (0, -1)
        assert abs(info['normal'][0]) < 0.01
        assert abs(abs(info['normal'][1]) - 1) < 0.01

    def test_angle_horizontal_path(self):
        """Horizontal path should have angle ~0."""
        path = np.array([[0, 0], [10, 0]])
        info = _compute_segment_info(path)
        assert info['angle'] == pytest.approx(0, abs=1)

    def test_angle_vertical_path(self):
        """Vertical path should have angle ~90 or ~-90."""
        path = np.array([[0, 0], [0, 10]])
        info = _compute_segment_info(path)
        assert abs(info['angle']) == pytest.approx(90, abs=1)

    def test_zero_length_returns_none(self):
        """Zero-length segment should return None."""
        path = np.array([[5, 5], [5, 5]])
        info = _compute_segment_info(path)
        assert info is None


class TestGetMultistopGeometry:
    """Tests for multi-stop geometry computation."""

    def test_two_points_produces_one_segment(self):
        """Two waypoints should produce one segment."""
        waypoints = [[0, 0], [10, 0]]
        geom = _get_multistop_geometry(waypoints)
        assert len(geom['segments']) == 1

    def test_three_points_produces_two_segments(self):
        """Three waypoints should produce two segments."""
        waypoints = [[0, 0], [5, 5], [10, 0]]
        geom = _get_multistop_geometry(waypoints)
        assert len(geom['segments']) == 2

    def test_segments_path_type(self):
        """path_type='segments' should produce straight lines."""
        waypoints = [[0, 0], [5, 5], [10, 0]]
        geom = _get_multistop_geometry(waypoints, path_type='segments')
        # Check that midpoint of first segment is on the line
        seg = geom['segments'][0]
        mid = seg['midpoint']
        # For line from (0,0) to (5,5), midpoint should be ~(2.5, 2.5)
        assert mid[0] == pytest.approx(2.5, abs=0.5)
        assert mid[1] == pytest.approx(2.5, abs=0.5)

    def test_spline_passes_through_waypoints(self):
        """Spline should pass through all waypoints."""
        waypoints = [[0, 0], [5, 2], [10, 0]]
        geom = _get_multistop_geometry(waypoints, path_type='spline')
        path = geom['full_path']
        # Check start
        assert path[0] == pytest.approx([0, 0], abs=0.1)
        # Check end
        assert path[-1] == pytest.approx([10, 0], abs=0.1)

    def test_total_length_is_sum_of_segments(self):
        """Total length should equal sum of segment lengths."""
        waypoints = [[0, 0], [5, 0], [10, 0]]
        geom = _get_multistop_geometry(waypoints, path_type='segments')
        sum_lengths = sum(s['length'] for s in geom['segments'])
        assert geom['total_length'] == pytest.approx(sum_lengths, abs=0.01)

    def test_waypoints_stored(self):
        """Original waypoints should be stored."""
        waypoints = [[1, 2], [3, 4], [5, 6]]
        geom = _get_multistop_geometry(waypoints)
        assert np.allclose(geom['waypoints'], waypoints)

    def test_single_point_returns_none(self):
        """Single waypoint should return None."""
        geom = _get_multistop_geometry([[0, 0]])
        assert geom is None

    def test_empty_returns_none(self):
        """Empty waypoints should return None."""
        geom = _get_multistop_geometry([])
        assert geom is None


class TestGetLabelCandidates:
    """Tests for label candidate ranking."""

    def test_sorted_by_length_descending(self):
        """Candidates should be sorted longest first."""
        waypoints = [[0, 0], [10, 0], [12, 0]]  # First segment longer
        geom = _get_multistop_geometry(waypoints, path_type='segments')
        candidates = _get_label_candidates(geom)
        lengths = [c['length'] for c in candidates]
        assert lengths == sorted(lengths, reverse=True)

    def test_all_segments_included(self):
        """All segments should be in candidates."""
        waypoints = [[0, 0], [5, 0], [10, 0], [15, 0]]
        geom = _get_multistop_geometry(waypoints, path_type='segments')
        candidates = _get_label_candidates(geom)
        assert len(candidates) == 3

    def test_longest_first(self):
        """Longest segment should be first candidate."""
        waypoints = [[0, 0], [2, 0], [12, 0]]  # Second segment is longer
        geom = _get_multistop_geometry(waypoints, path_type='segments')
        candidates = _get_label_candidates(geom)
        # Second segment (2,0)->(12,0) length=10 should be first
        assert candidates[0]['length'] == pytest.approx(10, abs=0.5)


class TestMultistopEdgeCases:
    """Edge cases for multi-stop geometry."""

    def test_two_points_straight_segment(self):
        """Two points should always be straight (no spline possible)."""
        waypoints = [[0, 0], [10, 5]]
        geom_spline = _get_multistop_geometry(waypoints, path_type='spline')
        geom_seg = _get_multistop_geometry(waypoints, path_type='segments')
        # Both should have same length
        assert geom_spline['total_length'] == pytest.approx(
            geom_seg['total_length'], abs=0.1
        )

    def test_many_waypoints(self):
        """Should handle many waypoints."""
        waypoints = [[i, i % 2] for i in range(10)]
        geom = _get_multistop_geometry(waypoints, path_type='spline')
        assert len(geom['segments']) == 9
        assert geom['full_path'] is not None

    def test_real_coordinates(self):
        """Should work with real lon/lat coordinates."""
        # Delhi -> Agra -> Jaipur (roughly)
        waypoints = [[77.2, 28.6], [78.0, 27.2], [75.8, 26.9]]
        geom = _get_multistop_geometry(waypoints, path_type='spline')
        assert geom is not None
        assert len(geom['segments']) == 2
