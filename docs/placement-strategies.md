# Label Placement Strategies

Research notes on automatic label placement algorithms for cartographic maps.

## The Problem

Automatic label placement (also called text placement or name placement) is one of the most difficult, complex, and time-consuming problems in mapmaking and GIS. Naively placed labels overlap excessively, resulting in a map that is difficult or impossible to read.

The problem is **NP-hard** for non-trivial cases - there's no known polynomial-time algorithm to find the optimal solution.

### Core Requirements

1. **Legibility** - Labels must not overlap each other
2. **Association** - It should be clear which map feature a label refers to
3. **Aesthetics** - Labels should follow cartographic conventions

## Imhof's Rules (1962)

Swiss cartographer Eduard Imhof established foundational rules for label placement:

### Position Priority for Point Features

For left-to-right languages, the preferred positions around a point feature are:

```
    NW   N   NE
     ╲   │   ╱
   W ─── ● ─── E
     ╱   │   ╲
    SW   S   SE
```

**Priority order:** NE > E > NW > W > SE > SW > N > S

Rationale:
- Top-right (NE) preferred because capital letters have more ascenders than descenders
- Right side preferred over left (reading direction)
- Top preferred over bottom

### Feature Categories

Map objects fall into three categories:
- **Punctiform** (points): settlements, mountain peaks
- **Linear** (lines): roads, rivers, boundaries
- **Areal** (polygons): countries, lakes, islands

Each category has different placement rules.

## Algorithmic Approaches

### 1. Greedy Algorithm

**How it works:** Place labels one-by-one, each in the best available position at that moment.

```
for each label in priority_order:
    for each candidate_position:
        if no_overlap(candidate_position):
            place_label(candidate_position)
            break
```

| Pros | Cons |
|------|------|
| O(n) time complexity - very fast | Can "paint into corners" |
| Deterministic | Early choices constrain later ones |
| Easy to implement and debug | May not find global optimum |

**Best for:** Moderate label counts, when speed matters, when determinism is needed.

### 2. Simulated Annealing

**How it works:** Start with any placement, then iteratively make random changes. Accept improvements always; accept worse solutions with decreasing probability (controlled by "temperature").

```
temperature = T_max
while temperature > T_min:
    new_placement = perturb(current_placement)
    delta = cost(new_placement) - cost(current_placement)
    if delta < 0 or random() < exp(-delta / temperature):
        current_placement = new_placement
    temperature *= cooling_rate
```

| Pros | Cons |
|------|------|
| Can escape local optima | Slow (many iterations needed) |
| Near-optimal results | Requires tuning (temperature, cooling rate) |
| Handles complex constraints | Non-deterministic |

**Best for:** Dense label sets, when quality matters more than speed.

**Libraries:**
- [Dymo](https://github.com/migurski/Dymo) - Python, specifically for map labels
- [simanneal](https://pypi.org/project/simanneal/) - Generic Python simulated annealing

### 3. Force-Directed (Spring Model)

**How it works:** Model labels as charged particles that repel each other. Attach each label to its anchor point with a spring. Simulate until equilibrium.

```
while not converged:
    for each label:
        repulsion = sum of forces pushing away from other labels
        attraction = spring force toward anchor point
        label.position += (repulsion + attraction) * timestep
```

| Pros | Cons |
|------|------|
| Intuitive physical model | May oscillate or not converge |
| Handles dynamic updates well | Results can look "floaty" |
| Good for interactive maps | Harder to control precisely |

**Best for:** Interactive/dynamic maps, graph layouts.

**Libraries:**
- [D3-force](https://github.com/d3/d3-force) - JavaScript

### 4. Integer Programming / Optimization

**How it works:** Formulate as a mathematical optimization problem. Each label has N candidate positions (binary variables). Constraints prevent overlaps. Objective maximizes labels placed or minimizes displacement.

| Pros | Cons |
|------|------|
| Mathematically optimal | Complex to implement |
| Handles hard constraints | Slow for large problems |
| Provable guarantees | Requires optimization solver |

**Best for:** When optimality is required, small-medium label sets.

### 5. GRASP (Greedy Randomized Adaptive Search)

**How it works:** Combine greedy construction with local search. Build initial solution greedily (with some randomness), then improve via local search. Repeat and keep best.

| Pros | Cons |
|------|------|
| Better than pure greedy | More complex than greedy |
| Faster than simulated annealing | Still heuristic |
| Good balance of speed/quality | Requires parameter tuning |

## Recommendation for history_cartopy

Given our constraints:
- Static maps (not interactive)
- Moderate label count (tens to low hundreds)
- Already have priority system
- Already have anchor/offset infrastructure
- Want deterministic, debuggable results

**Recommended approach: Priority-Ordered Greedy with Candidate Positions**

### Algorithm

```python
def resolve_overlaps(elements, placement_manager):
    # Sort by priority (highest first)
    sorted_elements = sorted(elements, key=lambda e: -e.priority)

    for element in sorted_elements:
        if element.type == 'point_label':
            # Try 8 positions around anchor
            positions = ['NE', 'E', 'NW', 'W', 'SE', 'SW', 'N', 'S']
            placed = False

            for pos in positions:
                candidate = compute_position(element, pos)
                if not placement_manager.would_overlap(candidate):
                    placement_manager.add(candidate)
                    placed = True
                    break

            if not placed:
                # Either suppress or use least-overlapping position
                log_warning(f"Could not place {element.id} without overlap")

        elif element.type == 'path_label':
            # Already implemented: try segments longest-first
            pass
```

### Why This Approach

1. **Deterministic** - Same input always produces same output
2. **Fast** - Single pass through labels, O(n) complexity
3. **Debuggable** - Can trace exactly why each label went where
4. **Builds on existing code** - PlacementManager and anchor system already exist
5. **Appropriate for scale** - Greedy works well for moderate label density

### Future Enhancements

If greedy proves insufficient:
1. Add simulated annealing as optional post-processing step
2. Implement GRASP for better initial solutions
3. Consider force-directed for specific dense regions

## References

- [Automatic label placement - Wikipedia](https://en.wikipedia.org/wiki/Automatic_label_placement)
- [Dymo - Map label placer with simulated annealing](https://github.com/migurski/Dymo)
- [Label Placement Algorithms for Automated Mapping](https://www.maplibrary.org/1398/label-placement-algorithms-for-automated-mapping/)
- [Imhof's position priority model](https://www.researchgate.net/figure/mhofs-31-model-for-positional-prioritization-of-point-feature-labeling_fig4_263859497)
- [GEOG 486: Label Placement](https://courses.ems.psu.edu/geog486/node/557)
- [D3-force library](https://github.com/d3/d3-force)
- [simanneal - Python simulated annealing](https://pypi.org/project/simanneal/)
- Imhof, E. (1962). Die Anordnung der Namen in der Karte. Int. Yearbook Cartography 2, 93-129.
- Imhof, E. (1975). Positioning names on maps. Am. Cartographer 2(2), 128-144.
