# Input and output contract

## Contents

- Input modes
- Project layout
- Manifest fields
- Minimal manifest example
- Output rules

## Input modes

Use any combination of:

| Kind | Typical files | Purpose |
| --- | --- | --- |
| `topic` | `.md`, `.txt` | idea, topic, mechanism, constraints, terminology |
| `paper_pdf` | `.pdf` | technical basis with page-level locators |
| `disclosure` | `.md`, `.txt` | controlling technical description |
| `claims` | `.md`, `.txt`, `.json` | optional coverage and numeral consistency check |
| `existing_figure` | `.svg`, `.png`, `.jpg` | optional redraw or audit input |

Do not infer priority among conflicting inputs. Mark the controlling input or ask the user.

## Project layout

Keep inputs in their existing locations. Put generated artifacts under one relative output directory:

```text
project/
├── topic.md
├── papers/
│   └── paper.pdf
└── patent-figures/
    ├── figure-manifest.json
    ├── editable/
    │   ├── fig1.svg
    │   └── fig2.svg
    ├── raster/
    │   ├── fig1.png
    │   └── fig2.png
    ├── extracted/
    │   └── paper.txt
    └── review/
        ├── source-crops/
        └── comparison-board.svg
```

Use SVG as the canonical editable artifact. Treat PNG as a fixed preview and downstream embedding format. Add `.drawio` only when requested.

## Manifest fields

The helper script uses schema `patentfig.project.v1`.

Top level:

- `project_root`: relative path from the manifest directory to the project;
- `inputs`: semantic source files;
- `visual_sources`: optional external figures that influenced layout;
- `grammar`: `keep / adapt / drop` mappings for visual sources;
- `figures`: plans, provenance, paths, markers, and review results.

Input entry:

- `id`: stable local identifier;
- `kind`: one of the input kinds above;
- `path`: project-relative path;
- `role`: normally `technical_basis`, `controlling_disclosure`, or `supporting_context`;
- `locator`: optional heading, section, or page range.

Figure entry:

- `figure_no` and `purpose`;
- `text_support`: project-relative path plus exact locator;
- `visual_source_ids`: optional source identifiers;
- `figure_plan`: reading direction, regions, nodes, interfaces, edge classes, and text levels;
- `routing_review`: final visual checks;
- `markers`: numeral-to-object mapping;
- `editable_svg` and `raster_png`;
- optional `editable_drawio`, `before_png`, `source_crop`, and `redraw_note`.

All file paths in the manifest must be relative to `project_root`. URLs belong only in `url` fields.

## Minimal manifest example

```json
{
  "schema_version": "patentfig.project.v1",
  "project_root": "..",
  "title": "Example project",
  "inputs": [
    {
      "id": "input1",
      "kind": "topic",
      "path": "topic.md",
      "role": "controlling_disclosure",
      "locator": "Core mechanism"
    }
  ],
  "visual_sources": [],
  "grammar": [],
  "figures": [
    {
      "figure_no": 1,
      "purpose": "Show the core processing path",
      "text_support": [
        {"path": "topic.md", "locator": "Core mechanism"}
      ],
      "visual_source_ids": [],
      "figure_plan": {
        "reading_direction": "left to right",
        "regions": ["input", "core mechanism", "output"],
        "nodes": ["input object", "decision module", "output object"],
        "interfaces": ["data path"],
        "edge_classes": {"solid": "data", "dashed": "control"},
        "text_levels": ["region title", "functional label", "reference numeral"]
      },
      "routing_review": {
        "horizontal_edge_labels": true,
        "parallel_edges_merged": true,
        "feedback_routed_outside": true,
        "nonsemantic_crossings_zero": true,
        "frame_intersections_reviewed": true,
        "reference_numerals_consistent": true,
        "text_supported_by_input": true
      },
      "markers": {"100": "input module", "110": "decision module", "120": "output module"},
      "editable_svg": "patent-figures/editable/fig1.svg",
      "raster_png": "patent-figures/raster/fig1.png"
    }
  ]
}
```

## Output rules

- Do not overwrite source topics or PDFs.
- Do not store machine-specific absolute paths.
- Do not place review crops beside filing artifacts.
- Keep explanations in the manifest or specification, not as marketing text inside the figure.
- Preserve stable reference numerals when revising a figure set.
- A missing PNG is an incomplete delivery, even when the SVG is valid.
