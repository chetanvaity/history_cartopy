"""
River label alignment module.

Automatically calculates rotation angles for river labels based on
the actual river geometry from Natural Earth data.
"""

import logging
import os
import math
from shapely.geometry import Point, LineString, MultiLineString
from shapely.ops import nearest_points

logger = logging.getLogger('history_cartopy.river_alignment')

# Cache for loaded river data
_river_cache = None


def _get_rivers_path(data_dir):
    """Get path to the Natural Earth rivers shapefile."""
    return os.path.join(data_dir, 'rivers', 'ne_10m_rivers_lake_centerlines.shp')


def _load_rivers(data_dir):
    """Load river geometries from Natural Earth shapefile."""
    global _river_cache

    if _river_cache is not None:
        return _river_cache

    rivers_path = _get_rivers_path(data_dir)
    if not os.path.exists(rivers_path):
        logger.warning(f"Rivers shapefile not found at {rivers_path}")
        logger.warning("Run 'history-map --init' to download Natural Earth data")
        return None

    logger.debug(f"Loading rivers from {rivers_path}")

    import cartopy.io.shapereader as shpreader

    reader = shpreader.Reader(rivers_path)
    _river_cache = {
        'geometries': list(reader.geometries()),
        'records': list(reader.records()),
    }
    return _river_cache


def _normalize_name(name):
    """Normalize river name for matching."""
    return name.lower().strip()


def _find_river_geometry(river_name, river_data):
    """Find geometry for a river by name."""
    target = _normalize_name(river_name)

    for record, geom in zip(river_data['records'], river_data['geometries']):
        # Natural Earth uses 'name' attribute for river names
        rec_name = record.attributes.get('name', '')
        if rec_name and _normalize_name(rec_name) == target:
            return geom

    # Try partial match if exact match fails
    for record, geom in zip(river_data['records'], river_data['geometries']):
        rec_name = record.attributes.get('name', '')
        if rec_name and target in _normalize_name(rec_name):
            return geom

    return None


def _geometry_to_linestrings(geom):
    """Convert geometry to list of LineStrings."""
    if isinstance(geom, LineString):
        return [geom]
    elif isinstance(geom, MultiLineString):
        return list(geom.geoms)
    else:
        return []


def _calculate_angle_at_point(line, point, search_radius=0.5):
    """
    Calculate the tangent angle of a line at the nearest point.

    Args:
        line: LineString geometry
        point: Point to find angle at
        search_radius: Search radius in degrees (for finding segment)

    Returns:
        Angle in degrees (0 = horizontal, positive = counter-clockwise)
    """
    # Find the closest point on the line
    nearest_on_line, _ = nearest_points(line, point)

    # Get line coordinates
    coords = list(line.coords)
    if len(coords) < 2:
        return 0

    # Find the segment containing or nearest to the closest point
    min_dist = float('inf')
    best_segment = (coords[0], coords[1])

    for i in range(len(coords) - 1):
        p1, p2 = coords[i], coords[i + 1]
        seg = LineString([p1, p2])
        dist = seg.distance(nearest_on_line)
        if dist < min_dist:
            min_dist = dist
            best_segment = (p1, p2)

    # Calculate angle from the segment
    p1, p2 = best_segment
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]

    # atan2 returns radians, convert to degrees
    angle = math.degrees(math.atan2(dy, dx))

    # Normalize angle so text is always readable (between -90 and +90)
    if angle > 90:
        angle -= 180
    elif angle < -90:
        angle += 180

    return angle


def get_river_angle(river_name, coords, data_dir, search_radius=0.5):
    """
    Get the rotation angle for a river label based on river direction.

    Args:
        river_name: Name of the river (e.g., "Brahmaputra")
        coords: (lon, lat) tuple for label position
        data_dir: Path to data directory containing rivers shapefile
        search_radius: Search radius in degrees for finding nearest segment

    Returns:
        Rotation angle in degrees, or 0 if river not found
    """
    river_data = _load_rivers(data_dir)
    if river_data is None:
        return 0

    geom = _find_river_geometry(river_name, river_data)
    if geom is None:
        logger.warning(f"River '{river_name}' not found in Natural Earth data")
        return 0

    logger.debug(f"Found geometry for river '{river_name}'")

    point = Point(coords[0], coords[1])
    linestrings = _geometry_to_linestrings(geom)

    if not linestrings:
        return 0

    # Find the closest linestring to the point
    min_dist = float('inf')
    closest_line = linestrings[0]

    for line in linestrings:
        dist = line.distance(point)
        if dist < min_dist:
            min_dist = dist
            closest_line = line

    angle = _calculate_angle_at_point(closest_line, point, search_radius)
    logger.info(f"River '{river_name}' at {coords}: rotation={angle:.1f}°")
    return angle


def sample_river_positions(river_name, extent, data_dir, sample_distance=2.0, padding=0.5):
    """
    Sample candidate positions along a river's geometry within map extents.

    Args:
        river_name: Name of the river (e.g., "Brahmaputra")
        extent: [west, east, south, north] map extents in degrees
        data_dir: Path to data directory containing rivers shapefile
        sample_distance: Distance between samples in degrees (default 2.0)
        padding: Padding from map edges in degrees (default 0.5)

    Returns:
        List of (lon, lat, angle) tuples for candidate positions,
        sorted by preference (middle of river first).
        Returns empty list if river not found.
    """
    river_data = _load_rivers(data_dir)
    if river_data is None:
        return []

    geom = _find_river_geometry(river_name, river_data)
    if geom is None:
        logger.warning(f"River '{river_name}' not found for auto-placement")
        return []

    linestrings = _geometry_to_linestrings(geom)
    if not linestrings:
        return []

    west, east, south, north = extent
    # Padded extents for filtering
    padded_west = west + padding
    padded_east = east - padding
    padded_south = south + padding
    padded_north = north - padding

    candidates = []

    for line in linestrings:
        coords = list(line.coords)
        if len(coords) < 2:
            continue

        # Calculate total length of this linestring (approximate in degrees)
        total_length = line.length

        # Sample along the line
        if total_length < sample_distance:
            # Short river segment - just use midpoint
            sample_points = [0.5]
        else:
            num_samples = max(2, int(total_length / sample_distance))
            sample_points = [i / (num_samples - 1) for i in range(num_samples)]

        for fraction in sample_points:
            # Interpolate point along the line
            point = line.interpolate(fraction, normalized=True)
            lon, lat = point.x, point.y

            # Check if within padded extents
            if not (padded_west <= lon <= padded_east and
                    padded_south <= lat <= padded_north):
                continue

            # Calculate angle at this point
            angle = _calculate_angle_at_point(line, point)

            candidates.append((lon, lat, angle, fraction))

    if not candidates:
        # Fallback: find closest point on river to map center
        map_center = Point((west + east) / 2, (south + north) / 2)
        min_dist = float('inf')
        fallback = None

        for line in linestrings:
            nearest_on_line, _ = nearest_points(line, map_center)
            dist = map_center.distance(nearest_on_line)
            if dist < min_dist:
                min_dist = dist
                angle = _calculate_angle_at_point(line, nearest_on_line)
                fallback = (nearest_on_line.x, nearest_on_line.y, angle, 0.5)

        if fallback:
            candidates.append(fallback)
            logger.debug(f"River '{river_name}': using fallback position near map center")

    # Sort by preference: positions near middle of river (fraction ~0.5) are preferred
    candidates.sort(key=lambda c: abs(c[3] - 0.5))

    # Return without the fraction
    result = [(lon, lat, angle) for lon, lat, angle, fraction in candidates]
    logger.info(f"River '{river_name}': generated {len(result)} candidate positions for auto-placement")
    return result
