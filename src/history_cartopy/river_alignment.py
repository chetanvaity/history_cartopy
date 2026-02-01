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

from . import river_search

logger = logging.getLogger('history_cartopy.river_alignment')

# Cache for loaded river data
_river_cache = None


def angle_to_normal(angle_deg):
    """
    Convert river angle to perpendicular unit normal vector.

    The normal points "above" the river (positive y direction when angle=0).

    Args:
        angle_deg: River angle in degrees (0 = horizontal, positive = counter-clockwise)

    Returns:
        (nx, ny) unit normal vector perpendicular to the river direction
    """
    # Normal is 90° rotated from tangent direction
    rad = math.radians(angle_deg + 90)
    return (math.cos(rad), math.sin(rad))


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


def _warn_river_not_found(river_name, data_dir):
    """Log warning with suggestions for similar river names."""
    logger.warning(f"River '{river_name}' not found in Natural Earth data")

    # Collect all suggestions from both search methods
    all_suggestions = {}  # name -> (score, reason)

    # Get fuzzy/phonetic matches
    results = river_search.search_rivers(river_name, data_dir, limit=10)
    for name, score, match_type in results:
        if score >= 50:
            all_suggestions[name] = (score, match_type)

    # Get spelling variation matches (may have better reasons)
    spelling = river_search.suggest_spellings(river_name, data_dir)
    for name, score, reason in spelling['suggestions']:
        if score >= 50:
            # Keep the higher score and better reason
            if name in all_suggestions:
                old_score, _ = all_suggestions[name]
                if score >= old_score:
                    all_suggestions[name] = (score, reason)
            else:
                all_suggestions[name] = (score, reason)

    # Sort by score and show top matches
    sorted_suggestions = sorted(all_suggestions.items(), key=lambda x: -x[1][0])
    if sorted_suggestions:
        for name, (score, reason) in sorted_suggestions[:5]:
            logger.warning(f"  Try: '{name}' ({reason})")


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
        _warn_river_not_found(river_name, data_dir)
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


def sample_river_positions(river_name, extent, data_dir, padding=0.5, hint_coords=None):
    """
    Sample candidate positions along a river's geometry within map extents.

    Args:
        river_name: Name of the river (e.g., "Brahmaputra")
        extent: [west, east, south, north] map extents in degrees
        data_dir: Path to data directory containing rivers shapefile
        padding: Padding from map edges in degrees (default 0.5)
        hint_coords: Optional (lon, lat) tuple to guide candidate generation.
                     When provided, candidates are only generated within 1/4
                     of the map extent around the hint position.

    Returns:
        List of (lon, lat, angle, normal) tuples for candidate positions,
        where normal is a (nx, ny) unit vector perpendicular to river direction.
        Sorted by preference (closest to hint or middle of river first).
        Returns empty list if river not found.
    """
    river_data = _load_rivers(data_dir)
    if river_data is None:
        return []

    geom = _find_river_geometry(river_name, river_data)
    if geom is None:
        _warn_river_not_found(river_name, data_dir)
        return []

    linestrings = _geometry_to_linestrings(geom)
    if not linestrings:
        return []

    west, east, south, north = extent
    map_width = east - west
    map_height = north - south

    # Determine search bounds
    if hint_coords:
        # Constrain search to ±1/4 map extent around hint
        hint_lon, hint_lat = hint_coords
        half_search_width = map_width / 4
        half_search_height = map_height / 4

        search_west = max(west + padding, hint_lon - half_search_width)
        search_east = min(east - padding, hint_lon + half_search_width)
        search_south = max(south + padding, hint_lat - half_search_height)
        search_north = min(north - padding, hint_lat + half_search_height)

        logger.info(f"River '{river_name}': hint_coords={hint_coords}, "
                    f"search bounds=[{search_west:.2f}, {search_east:.2f}, {search_south:.2f}, {search_north:.2f}]")
    else:
        # Use full map extent with padding
        search_west = west + padding
        search_east = east - padding
        search_south = south + padding
        search_north = north - padding

    # Sample distance based on search area - aim for ~10-20 samples across the search region
    search_width = search_east - search_west
    search_height = search_north - search_south
    sample_distance = min(search_width, search_height) / 10

    logger.debug(f"River '{river_name}': sample_distance={sample_distance:.3f} "
                f"(search area {search_width:.1f}° x {search_height:.1f}°)")

    candidates = []
    total_samples = 0
    filtered_out = 0

    logger.debug(f"River '{river_name}': processing {len(linestrings)} linestring(s)")

    for idx, line in enumerate(linestrings):
        coords = list(line.coords)
        if len(coords) < 2:
            continue

        # Calculate total length of this linestring (approximate in degrees)
        total_length = line.length

        # Get bounding box of this linestring
        minx, miny, maxx, maxy = line.bounds
        logger.debug(f"  Linestring {idx}: length={total_length:.2f}, "
                    f"bounds=lon[{minx:.2f}, {maxx:.2f}] lat[{miny:.2f}, {maxy:.2f}]")

        # Sample along the line
        if total_length < sample_distance:
            # Short river segment - just use midpoint
            sample_points = [0.5]
        else:
            num_samples = max(2, int(total_length / sample_distance))
            sample_points = [i / (num_samples - 1) for i in range(num_samples)]

        line_candidates = 0
        line_filtered = 0

        for fraction in sample_points:
            total_samples += 1
            # Interpolate point along the line
            point = line.interpolate(fraction, normalized=True)
            lon, lat = point.x, point.y

            # Check if within search bounds
            if not (search_west <= lon <= search_east and
                    search_south <= lat <= search_north):
                filtered_out += 1
                line_filtered += 1
                continue

            # Calculate angle at this point
            angle = _calculate_angle_at_point(line, point)
            normal = angle_to_normal(angle)

            candidates.append((lon, lat, angle, normal, fraction))
            line_candidates += 1

        if line_candidates > 0 or line_filtered > 0:
            logger.debug(f"  Linestring {idx}: {len(sample_points)} samples, "
                         f"{line_candidates} in bounds, {line_filtered} filtered out")

    logger.debug(f"River '{river_name}': {total_samples} total samples, "
                f"{len(candidates)} in bounds, {filtered_out} filtered out")

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
                normal = angle_to_normal(angle)
                fallback = (nearest_on_line.x, nearest_on_line.y, angle, normal, 0.5)

        if fallback:
            candidates.append(fallback)
            logger.debug(f"River '{river_name}': using fallback position near map center")

    # Sort by preference
    if hint_coords:
        # When hint provided, sort by distance to hint
        hint_lon, hint_lat = hint_coords
        candidates.sort(key=lambda c: (c[0] - hint_lon)**2 + (c[1] - hint_lat)**2)
    else:
        # Otherwise prefer positions near middle of river (fraction ~0.5)
        candidates.sort(key=lambda c: abs(c[4] - 0.5))  # fraction is at index 4

    # Return without the fraction (keep lon, lat, angle, normal)
    result = [(lon, lat, angle, normal) for lon, lat, angle, normal, fraction in candidates]
    logger.info(f"River '{river_name}': generated {len(result)} candidate positions for auto-placement")
    return result
