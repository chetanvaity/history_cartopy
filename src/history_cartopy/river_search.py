"""
River name search and fuzzy matching module.

Helps find rivers in Natural Earth data when the exact spelling is unknown.
Provides fuzzy string matching and phonetic (similar-sounding) matching.
"""

import os
import re
from difflib import SequenceMatcher
from collections import defaultdict


def _load_river_names(data_dir):
    """Load all river names from Natural Earth shapefile."""
    rivers_path = os.path.join(data_dir, 'rivers', 'ne_10m_rivers_lake_centerlines.shp')
    if not os.path.exists(rivers_path):
        return []

    import cartopy.io.shapereader as shpreader
    reader = shpreader.Reader(rivers_path)

    names = set()
    for record in reader.records():
        name = record.attributes.get('name', '')
        if name:
            names.add(name)

    return sorted(names)


def _metaphone(word):
    """
    Simple Metaphone-like phonetic encoding.

    Groups similar-sounding consonants and removes vowels (except leading).
    This helps match names like "Godavari" vs "Godawari" or "Krishna" vs "Krsna".
    """
    if not word:
        return ''

    word = word.upper()

    # Keep only letters
    word = re.sub(r'[^A-Z]', '', word)

    if not word:
        return ''

    # Phonetic substitutions (similar sounds grouped)
    substitutions = {
        'B': 'P', 'F': 'P', 'P': 'P', 'V': 'P',  # labials
        'C': 'K', 'G': 'K', 'J': 'K', 'K': 'K', 'Q': 'K',  # gutturals
        'D': 'T', 'T': 'T',  # dentals
        'L': 'L', 'R': 'L',  # liquids (important for Indian rivers)
        'M': 'M', 'N': 'M',  # nasals
        'S': 'S', 'X': 'S', 'Z': 'S',  # sibilants
        'W': 'W', 'Y': 'W',  # semivowels
        'H': '',  # often silent or aspirate
    }

    # Vowel groups (for matching similar vowel sounds)
    vowels = set('AEIOU')

    # Normalize first letter too (so K and C match)
    first_code = substitutions.get(word[0], word[0])
    result = [first_code] if first_code else []
    prev_code = first_code

    for char in word[1:]:
        if char in vowels:
            # Skip vowels except to break up repeated consonants
            prev_code = ''
            continue

        code = substitutions.get(char, char)
        if code and code != prev_code:
            result.append(code)
            prev_code = code

    return ''.join(result)


def _soundex(word):
    """
    Classic Soundex encoding (4-character code).

    Less aggressive than metaphone, useful as a secondary match.
    """
    if not word:
        return '0000'

    word = word.upper()
    word = re.sub(r'[^A-Z]', '', word)

    if not word:
        return '0000'

    # Soundex coding
    codes = {
        'B': '1', 'F': '1', 'P': '1', 'V': '1',
        'C': '2', 'G': '2', 'J': '2', 'K': '2', 'Q': '2', 'S': '2', 'X': '2', 'Z': '2',
        'D': '3', 'T': '3',
        'L': '4',
        'M': '5', 'N': '5',
        'R': '6',
    }

    result = word[0]
    prev_code = codes.get(word[0], '')

    for char in word[1:]:
        code = codes.get(char, '')
        if code and code != prev_code:
            result += code
        prev_code = code if code else prev_code

    # Pad or truncate to 4 characters
    result = (result + '000')[:4]
    return result


def _string_similarity(s1, s2):
    """Calculate string similarity ratio (0-1)."""
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


def _ngram_similarity(s1, s2, n=2):
    """Calculate n-gram (character) similarity."""
    s1, s2 = s1.lower(), s2.lower()

    def get_ngrams(s, n):
        return set(s[i:i+n] for i in range(max(0, len(s) - n + 1)))

    ngrams1 = get_ngrams(s1, n)
    ngrams2 = get_ngrams(s2, n)

    if not ngrams1 or not ngrams2:
        return 0.0

    intersection = len(ngrams1 & ngrams2)
    union = len(ngrams1 | ngrams2)

    return intersection / union if union else 0.0


def search_rivers(query, data_dir, limit=10):
    """
    Search for rivers matching a query string.

    Uses multiple matching strategies:
    1. Exact/substring match
    2. Fuzzy string similarity
    3. Phonetic (similar-sounding) match

    Args:
        query: River name to search for
        data_dir: Path to data directory with Natural Earth files
        limit: Maximum number of results to return

    Returns:
        List of (river_name, score, match_type) tuples, sorted by relevance.
        score is 0-100, match_type is 'exact', 'substring', 'fuzzy', or 'phonetic'.
    """
    all_rivers = _load_river_names(data_dir)
    if not all_rivers:
        return []

    query_lower = query.lower().strip()
    query_metaphone = _metaphone(query)
    query_soundex = _soundex(query)

    results = []

    for river in all_rivers:
        river_lower = river.lower()
        river_metaphone = _metaphone(river)
        river_soundex = _soundex(river)

        # Exact match
        if river_lower == query_lower:
            results.append((river, 100, 'exact'))
            continue

        # Substring match - require meaningful coverage (at least 50%)
        if query_lower in river_lower or river_lower in query_lower:
            coverage = min(len(query_lower), len(river_lower)) / max(len(query_lower), len(river_lower))
            # Only count as substring match if coverage is significant
            if coverage >= 0.5:
                results.append((river, int(85 + coverage * 10), 'substring'))
                continue

        scores = []

        # Fuzzy string similarity
        string_sim = _string_similarity(query, river)
        if string_sim >= 0.5:
            scores.append(('fuzzy', int(string_sim * 80)))

        # N-gram similarity
        ngram_sim = _ngram_similarity(query, river)
        if ngram_sim >= 0.3:
            scores.append(('fuzzy', int(ngram_sim * 70)))

        # Phonetic match (metaphone) - boost if also string-similar
        if query_metaphone and river_metaphone:
            base_score = 0
            if query_metaphone == river_metaphone:
                base_score = 70
            elif query_metaphone.startswith(river_metaphone[:3]) or river_metaphone.startswith(query_metaphone[:3]):
                base_score = 55

            if base_score > 0:
                # Boost score if lengths are similar and string similarity is good
                len_ratio = min(len(query), len(river)) / max(len(query), len(river))
                if len_ratio >= 0.7 and string_sim >= 0.5:
                    base_score += 15  # Boost for similar length + spelling
                elif len_ratio >= 0.8:
                    base_score += 5   # Small boost for similar length

                # Boost for K/C interchange (important for Indian river names)
                first_q, first_r = query_lower[0], river_lower[0]
                if {first_q, first_r} == {'k', 'c'}:
                    base_score += 12  # K/C interchange is common in romanization

                scores.append(('phonetic', base_score))

        # Phonetic match (soundex)
        if query_soundex == river_soundex:
            scores.append(('phonetic', 50))

        if scores:
            best_type, best_score = max(scores, key=lambda x: x[1])
            results.append((river, best_score, best_type))

    # Sort by score descending, then alphabetically
    results.sort(key=lambda x: (-x[1], x[0]))

    return results[:limit]


def suggest_spellings(query, data_dir):
    """
    Suggest possible spelling modifications for a river name.

    Useful when searching for rivers with alternate spellings
    (e.g., Godavari/Godawari, Ganges/Ganga).

    Args:
        query: River name to find alternatives for
        data_dir: Path to data directory

    Returns:
        Dict with:
        - 'found': bool, whether exact match exists
        - 'exact': str or None, exact match if found
        - 'suggestions': list of (name, score, reason) tuples
    """
    all_rivers = _load_river_names(data_dir)
    query_lower = query.lower().strip()

    # Check for exact match first
    exact_match = None
    for river in all_rivers:
        if river.lower() == query_lower:
            exact_match = river
            break

    if exact_match:
        return {
            'found': True,
            'exact': exact_match,
            'suggestions': []
        }

    # Generate suggestions with reasons
    suggestions = []
    query_metaphone = _metaphone(query)

    for river in all_rivers:
        river_lower = river.lower()
        reasons = []
        score = 0

        # Check for common spelling variations

        # K/C interchange (common in Indian names: Kaveri/Cauvery)
        if _matches_with_substitution(query_lower, river_lower, 'k', 'c'):
            reasons.append('k/c interchange')
            score = max(score, 85)

        # W/V interchange (common in Indian languages)
        if _matches_with_substitution(query_lower, river_lower, 'w', 'v'):
            reasons.append('w/v interchange')
            score = max(score, 80)

        # U/OO interchange
        if _matches_with_substitution(query_lower, river_lower, 'u', 'oo'):
            reasons.append('u/oo spelling')
            score = max(score, 75)

        # I/EE interchange
        if _matches_with_substitution(query_lower, river_lower, 'i', 'ee'):
            reasons.append('i/ee spelling')
            score = max(score, 75)

        # A/AA interchange
        if _matches_with_substitution(query_lower, river_lower, 'a', 'aa'):
            reasons.append('a/aa spelling')
            score = max(score, 70)

        # TH/T interchange
        if _matches_with_substitution(query_lower, river_lower, 'th', 't'):
            reasons.append('th/t variation')
            score = max(score, 70)

        # PH/F interchange
        if _matches_with_substitution(query_lower, river_lower, 'ph', 'f'):
            reasons.append('ph/f variation')
            score = max(score, 70)

        # Check phonetic similarity
        river_metaphone = _metaphone(river)
        if query_metaphone and river_metaphone:
            # Check for K/C interchange + phonetic match (common Indian romanization)
            if query_lower[0] in 'kc' and river_lower[0] in 'kc':
                # Check if metaphones match or are prefix of each other
                if (query_metaphone == river_metaphone or
                    query_metaphone.startswith(river_metaphone) or
                    river_metaphone.startswith(query_metaphone)):
                    reasons.append('k/c sound variant')
                    score = max(score, 85)

            # General phonetic match
            if query_metaphone == river_metaphone and not reasons:
                reasons.append('sounds similar')
                score = max(score, 65)

        # Check for prefix/suffix variations (River X vs X River)
        if _is_name_variant(query_lower, river_lower):
            reasons.append('name variant')
            score = max(score, 60)

        # General string similarity for close matches
        sim = _string_similarity(query, river)
        if sim >= 0.7 and not reasons:
            reasons.append(f'similar spelling ({int(sim*100)}%)')
            score = max(score, int(sim * 80))

        if reasons:
            suggestions.append((river, score, ', '.join(reasons)))

    # Sort by score
    suggestions.sort(key=lambda x: (-x[1], x[0]))

    return {
        'found': False,
        'exact': None,
        'suggestions': suggestions[:10]
    }


def _matches_with_substitution(s1, s2, char1, char2):
    """Check if s1 matches s2 when substituting char1 for char2."""
    # Try both directions
    s1_mod = s1.replace(char1, char2)
    s2_mod = s2.replace(char1, char2)

    if s1_mod == s2 or s1 == s2_mod:
        return True

    # Also try the reverse substitution
    s1_mod = s1.replace(char2, char1)
    s2_mod = s2.replace(char2, char1)

    return s1_mod == s2 or s1 == s2_mod


def _is_name_variant(s1, s2):
    """Check if names are variants (e.g., 'Ganges' vs 'Ganga River')."""
    prefixes_suffixes = ['river', 'rio', 'fleuve', 'fluss', 'nadi', 'ganga']

    # Remove common prefixes/suffixes
    def clean(s):
        s = s.strip()
        for word in prefixes_suffixes:
            s = re.sub(rf'\b{word}\b', '', s, flags=re.IGNORECASE)
        return s.strip()

    return clean(s1) == clean(s2) or _string_similarity(clean(s1), clean(s2)) > 0.8


def list_rivers(data_dir, pattern=None):
    """
    List all available river names, optionally filtered by pattern.

    Args:
        data_dir: Path to data directory
        pattern: Optional regex pattern to filter names

    Returns:
        List of river names
    """
    rivers = _load_river_names(data_dir)

    if pattern:
        regex = re.compile(pattern, re.IGNORECASE)
        rivers = [r for r in rivers if regex.search(r)]

    return rivers


def format_search_results(results, query):
    """Format search results for display."""
    if not results:
        return f"No rivers found matching '{query}'"

    lines = [f"Rivers matching '{query}':", ""]

    for name, score, match_type in results:
        indicator = {
            'exact': '=',
            'substring': '~',
            'fuzzy': '?',
            'phonetic': '*'
        }.get(match_type, ' ')

        lines.append(f"  {indicator} {name:30} ({score}% {match_type})")

    lines.append("")
    lines.append("Legend: = exact, ~ substring, ? fuzzy, * phonetic")

    return '\n'.join(lines)


def format_suggestions(result, query):
    """Format spelling suggestions for display."""
    lines = []

    if result['found']:
        lines.append(f"'{query}' found as: {result['exact']}")
    else:
        lines.append(f"'{query}' not found in Natural Earth data.")

        if result['suggestions']:
            lines.append("")
            lines.append("Did you mean:")
            for name, score, reason in result['suggestions']:
                lines.append(f"  - {name:30} ({reason})")
        else:
            lines.append("No similar rivers found.")

    return '\n'.join(lines)
