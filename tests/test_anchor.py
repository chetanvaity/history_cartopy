"""Tests for anchor module - attachment placement around anchor circles."""

import math
import pytest
from history_cartopy.anchor import AnchorCircle, compute_campaign_angle, DEFAULT_ANGLES


class TestAnchorCircleBasics:
    """Basic initialization and single attachment tests."""

    def test_default_city_level(self):
        """Default city level should use level 2 config."""
        ac = AnchorCircle()
        ac2 = AnchorCircle(city_level=2)
        # Default should match explicit level 2
        assert ac.radius == ac2.radius
        assert ac.radius > 0

    def test_city_level_1_larger_radius(self):
        """City level 1 should have larger radius."""
        ac1 = AnchorCircle(city_level=1)
        ac2 = AnchorCircle(city_level=2)
        assert ac1.radius > ac2.radius

    def test_city_level_3_smaller_radius(self):
        """City level 3 should have smaller radius."""
        ac2 = AnchorCircle(city_level=2)
        ac3 = AnchorCircle(city_level=3)
        assert ac3.radius < ac2.radius

    def test_invalid_city_level_uses_default(self):
        """Invalid city level should fall back to level 2."""
        ac = AnchorCircle(city_level=99)
        ac2 = AnchorCircle(city_level=2)
        assert ac.radius == ac2.radius


class TestAddAttachment:
    """Tests for add_attachment method."""

    def test_add_attachment_returns_index(self):
        """Each attachment should get a unique sequential index."""
        ac = AnchorCircle()
        idx0 = ac.add_attachment('label')
        idx1 = ac.add_attachment('icon')
        idx2 = ac.add_attachment('campaign_in')
        assert idx0 == 0
        assert idx1 == 1
        assert idx2 == 2

    def test_default_angle_for_label(self):
        """Label should default to 135 degrees (SE)."""
        ac = AnchorCircle()
        ac.add_attachment('label')
        assert ac.attachments[0]['preferred_angle'] == DEFAULT_ANGLES['label']
        assert ac.attachments[0]['preferred_angle'] == 135

    def test_default_angle_for_icon(self):
        """Icon should default to 0 degrees (N)."""
        ac = AnchorCircle()
        ac.add_attachment('icon')
        assert ac.attachments[0]['preferred_angle'] == DEFAULT_ANGLES['icon']
        assert ac.attachments[0]['preferred_angle'] == 0

    def test_custom_preferred_angle(self):
        """Custom angle should override default."""
        ac = AnchorCircle()
        ac.add_attachment('label', preferred_angle=270)
        assert ac.attachments[0]['preferred_angle'] == 270

    def test_unknown_type_default_angle(self):
        """Unknown type should get fallback angle of 45."""
        ac = AnchorCircle()
        ac.add_attachment('unknown_type')
        assert ac.attachments[0]['preferred_angle'] == 45

    def test_priority_stored(self):
        """Priority should be stored on attachment."""
        ac = AnchorCircle()
        ac.add_attachment('label', priority=100)
        assert ac.attachments[0]['priority'] == 100

    def test_adding_attachment_resets_resolved(self):
        """Adding attachment after resolve should reset resolved state."""
        ac = AnchorCircle()
        ac.add_attachment('label')
        ac.resolve()
        assert ac._resolved is True
        ac.add_attachment('icon')
        assert ac._resolved is False


class TestResolveSingleAttachment:
    """Tests for resolve with single attachment."""

    def test_single_attachment_uses_preferred_angle(self):
        """Single attachment should use its preferred angle."""
        ac = AnchorCircle()
        idx = ac.add_attachment('label', preferred_angle=90)
        ac.resolve()
        assert ac.get_angle(idx) == 90

    def test_resolve_empty(self):
        """Resolving with no attachments should not error."""
        ac = AnchorCircle()
        ac.resolve()
        assert ac._resolved is True


class TestResolveTwoAttachments:
    """Tests for resolve with two attachments."""

    def test_two_attachments_180_apart(self):
        """Two attachments should be placed 180 degrees apart."""
        ac = AnchorCircle()
        idx0 = ac.add_attachment('label', preferred_angle=0, priority=10)
        idx1 = ac.add_attachment('icon', preferred_angle=0, priority=5)
        ac.resolve()
        angle0 = ac.get_angle(idx0)
        angle1 = ac.get_angle(idx1)
        diff = abs(angle0 - angle1)
        assert diff == 180 or diff == 180  # Should be exactly 180

    def test_higher_priority_gets_preference(self):
        """Higher priority attachment should get its preferred angle."""
        ac = AnchorCircle()
        idx_low = ac.add_attachment('label', preferred_angle=90, priority=1)
        idx_high = ac.add_attachment('icon', preferred_angle=45, priority=100)
        ac.resolve()
        # High priority should get 45, low priority should get 45+180=225
        assert ac.get_angle(idx_high) == 45
        assert ac.get_angle(idx_low) == 225

    def test_equal_priority_first_added_wins(self):
        """With equal priority, implementation uses stable sort."""
        ac = AnchorCircle()
        idx0 = ac.add_attachment('label', preferred_angle=0, priority=50)
        idx1 = ac.add_attachment('icon', preferred_angle=90, priority=50)
        ac.resolve()
        # Both have same priority, sorted by -priority is stable
        # First one in sorted order gets preference
        angle0 = ac.get_angle(idx0)
        angle1 = ac.get_angle(idx1)
        assert abs(angle0 - angle1) == 180


class TestResolveThreeOrMoreAttachments:
    """Tests for resolve with 3+ attachments."""

    def test_three_attachments_120_apart(self):
        """Three attachments should be ~120 degrees apart."""
        ac = AnchorCircle()
        idx0 = ac.add_attachment('label')
        idx1 = ac.add_attachment('icon')
        idx2 = ac.add_attachment('campaign_in', preferred_angle=180)
        ac.resolve()

        angles = sorted([ac.get_angle(idx0), ac.get_angle(idx1), ac.get_angle(idx2)])
        # Should have slots at 0, 120, 240 degrees
        expected_slots = [0, 120, 240]
        assert angles == pytest.approx(expected_slots, abs=1)

    def test_campaign_gets_preferred_direction(self):
        """Campaign arrows should get priority for their natural direction."""
        ac = AnchorCircle()
        ac.add_attachment('label')
        ac.add_attachment('icon')
        campaign_idx = ac.add_attachment('campaign_in', preferred_angle=180)
        ac.resolve()

        # Campaign at 180 should snap to slot at 180 (for 3 items: 0, 120, 240)
        # Actually 360/3 = 120, so slots are 0, 120, 240
        # 180 snaps to round(180/120)*120 = round(1.5)*120 = 2*120 = 240
        campaign_angle = ac.get_angle(campaign_idx)
        assert campaign_angle == 240

    def test_four_attachments_90_apart(self):
        """Four attachments should have 90 degree slots."""
        ac = AnchorCircle()
        indices = [ac.add_attachment('item') for _ in range(4)]
        ac.resolve()

        angles = sorted([ac.get_angle(idx) for idx in indices])
        # Slots: 0, 90, 180, 270
        assert angles == pytest.approx([0, 90, 180, 270], abs=1)


class TestGetOffset:
    """Tests for get_offset - converting angles to x,y coordinates."""

    def test_north_is_up(self):
        """Angle 0 (North) should give positive y offset."""
        ac = AnchorCircle()
        idx = ac.add_attachment('label', preferred_angle=0)
        ac.resolve()
        x, y = ac.get_offset(idx)
        assert x == pytest.approx(0, abs=0.001)
        assert y > 0  # North is up

    def test_east_is_right(self):
        """Angle 90 (East) should give positive x offset."""
        ac = AnchorCircle()
        idx = ac.add_attachment('label', preferred_angle=90)
        ac.resolve()
        x, y = ac.get_offset(idx)
        assert x > 0  # East is right
        assert y == pytest.approx(0, abs=0.001)

    def test_south_is_down(self):
        """Angle 180 (South) should give negative y offset."""
        ac = AnchorCircle()
        idx = ac.add_attachment('label', preferred_angle=180)
        ac.resolve()
        x, y = ac.get_offset(idx)
        assert x == pytest.approx(0, abs=0.001)
        assert y < 0  # South is down

    def test_west_is_left(self):
        """Angle 270 (West) should give negative x offset."""
        ac = AnchorCircle()
        idx = ac.add_attachment('label', preferred_angle=270)
        ac.resolve()
        x, y = ac.get_offset(idx)
        assert x < 0  # West is left
        assert y == pytest.approx(0, abs=0.001)

    def test_offset_magnitude_equals_radius(self):
        """Offset distance should equal circle radius."""
        ac = AnchorCircle(city_level=2)  # radius = 8
        idx = ac.add_attachment('label', preferred_angle=45)
        ac.resolve()
        x, y = ac.get_offset(idx)
        distance = math.sqrt(x**2 + y**2)
        assert distance == pytest.approx(ac.radius, abs=0.001)

    def test_auto_resolve_on_get_offset(self):
        """get_offset should auto-resolve if not resolved."""
        ac = AnchorCircle()
        idx = ac.add_attachment('label', preferred_angle=90)
        # Don't call resolve()
        x, y = ac.get_offset(idx)
        assert ac._resolved is True
        assert x > 0

    def test_unknown_index_returns_zero(self):
        """Unknown attachment index should return angle 0."""
        ac = AnchorCircle()
        ac.add_attachment('label')
        ac.resolve()
        x, y = ac.get_offset(999)  # Non-existent index
        # Angle 0 = North = (0, radius)
        assert x == pytest.approx(0, abs=0.001)
        assert y == pytest.approx(ac.radius, abs=0.001)


class TestGetAngle:
    """Tests for get_angle method."""

    def test_get_angle_returns_resolved_angle(self):
        """get_angle should return the resolved angle."""
        ac = AnchorCircle()
        idx = ac.add_attachment('label', preferred_angle=123)
        ac.resolve()
        assert ac.get_angle(idx) == 123

    def test_get_angle_auto_resolves(self):
        """get_angle should auto-resolve if needed."""
        ac = AnchorCircle()
        idx = ac.add_attachment('label', preferred_angle=45)
        # Don't call resolve()
        angle = ac.get_angle(idx)
        assert angle == 45
        assert ac._resolved is True


class TestComputeCampaignAngle:
    """Tests for compute_campaign_angle function."""

    def test_north_direction(self):
        """Arrow pointing north should be ~0 degrees."""
        angle = compute_campaign_angle((0, 0), (0, 10))
        assert angle == pytest.approx(0, abs=1)

    def test_east_direction(self):
        """Arrow pointing east should be ~90 degrees."""
        angle = compute_campaign_angle((0, 0), (10, 0))
        assert angle == pytest.approx(90, abs=1)

    def test_south_direction(self):
        """Arrow pointing south should be ~180 degrees."""
        angle = compute_campaign_angle((0, 10), (0, 0))
        assert angle == pytest.approx(180, abs=1)

    def test_west_direction(self):
        """Arrow pointing west should be ~270 degrees."""
        angle = compute_campaign_angle((10, 0), (0, 0))
        assert angle == pytest.approx(270, abs=1)

    def test_northeast_direction(self):
        """Arrow pointing NE should be ~45 degrees."""
        angle = compute_campaign_angle((0, 0), (10, 10))
        assert angle == pytest.approx(45, abs=1)

    def test_southeast_direction(self):
        """Arrow pointing SE should be ~135 degrees."""
        angle = compute_campaign_angle((0, 10), (10, 0))
        assert angle == pytest.approx(135, abs=1)

    def test_angle_always_positive(self):
        """Angle should always be in range [0, 360)."""
        test_cases = [
            ((0, 0), (10, 10)),   # NE
            ((0, 0), (-10, 10)),  # NW
            ((0, 0), (-10, -10)), # SW
            ((0, 0), (10, -10)),  # SE
        ]
        for from_c, to_c in test_cases:
            angle = compute_campaign_angle(from_c, to_c)
            assert 0 <= angle < 360, f"Angle {angle} out of range for {from_c}->{to_c}"

    def test_real_coordinates(self):
        """Test with realistic lon/lat coordinates."""
        # Delhi to Agra (Agra is roughly SE of Delhi)
        delhi = (77.2, 28.6)
        agra = (78.0, 27.2)
        angle = compute_campaign_angle(delhi, agra)
        # Should be roughly SE, so around 120-150 degrees
        assert 100 < angle < 170


class TestEdgeCases:
    """Edge cases and integration scenarios."""

    def test_many_attachments(self):
        """Should handle many attachments without error."""
        ac = AnchorCircle()
        for i in range(10):
            ac.add_attachment('item', preferred_angle=i * 36)
        ac.resolve()
        angles = [ac.get_angle(i) for i in range(10)]
        # Should have 10 distinct angles
        assert len(set(angles)) == 10

    def test_all_same_preferred_angle(self):
        """Multiple attachments with same preferred angle should distribute."""
        ac = AnchorCircle()
        for _ in range(4):
            ac.add_attachment('label', preferred_angle=0)
        ac.resolve()
        angles = [ac.get_angle(i) for i in range(4)]
        # Should end up at 4 different positions
        assert len(set(angles)) == 4

    def test_campaign_and_non_campaign_mix(self):
        """Campaign arrows should get priority in angle selection."""
        ac = AnchorCircle()
        label_idx = ac.add_attachment('label', preferred_angle=180)
        icon_idx = ac.add_attachment('icon', preferred_angle=180)
        campaign_idx = ac.add_attachment('campaign_in', preferred_angle=180)
        ac.resolve()

        # Campaign should get closest slot to 180
        campaign_angle = ac.get_angle(campaign_idx)
        # With 3 items, slots are 0, 120, 240. 180 snaps to 240.
        # Campaign gets 240, others get remaining slots (0, 120)
        assert campaign_angle == 240
