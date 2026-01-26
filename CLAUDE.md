# Purpose

Create beautiful historical maps from declarative YAML manifests.
See [motivation](motivation.md).

# Philosophy

- The priority is on beautiful, printable maps - for history books.
- Keep the code modular and loosely coupled where possible.

# Structure

The input is a YAML file describing the desired map. It contains:
  - map extents, title, etc
  - cities to be labelled in the map
  - military movements - called campaigns
  - specific events

The backgrounds used are NaturalEarth provided images of the world.

## Anchor circle
- An imaginary circle around a city dot - where labels and campaign arrow endpoints are placed.

## Placement Manager
- Module to resolve candidate positions for labels, arrows, etc to get a visually pleasing decluttered map.

