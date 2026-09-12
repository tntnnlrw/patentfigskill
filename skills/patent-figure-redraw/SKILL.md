---
name: patent-figure-redraw
description: Convert one or more technical topics, disclosures, notes, or research-paper PDFs into filing-style patent figures while preserving source provenance and the disclosed technical mechanism. Use when Codex needs to analyze topic files or papers, plan a patent figure set, redraw technical concepts without copying source artwork, or deliver editable SVG and review-ready PNG figures. Also use to audit figure paths, reference numerals, grayscale styling, source overlap, and figure manifests. Do not use to determine patentability, invent unsupported mechanisms, copy paper figures, or provide legal advice.
---

# Patent Figure Redraw

Create patent-style technical drawings from topic files or paper PDFs without depending on a particular repository layout. Always deliver an editable SVG and a rendered PNG for every final figure.

## Resolve the inputs

Accept a project directory or explicit input files. Treat these as valid technical inputs:

- one or more topic, idea, or technical-note files in Markdown or plain text;
- one or more research-paper PDFs;
- an optional disclosure, draft claims, terminology list, or existing figure;
- optional external figures used only as review evidence or visual-grammar references.

Do not require fixed filenames. Keep every generated manifest path relative to the project directory.

Resolve the directory containing this `SKILL.md` and expose it as `SKILL_DIR` before running the bundled commands.

Read [references/input-output.md](references/input-output.md) before initializing a project. Run:

```bash
python3 "$SKILL_DIR/scripts/patent_figure_ops.py" init <project-directory> [input ...]
```

This creates `patent-figures/figure-manifest.json` and output directories without modifying the inputs. If a manifest already exists, preserve it unless the user explicitly requests replacement.

## Extract the disclosed mechanism

Read every user-selected topic. For each selected PDF, inspect the abstract, method, system overview, and the exact pages that support the proposed figure. Extract only what the input discloses:

- protected or central technical object;
- actors, system boundary, and deployment roles;
- input, observation, transform, decision, maintained state, and output;
- feedback, fallback, recovery, or update loop;
- technical effect stated by the source;
- stable terminology and candidate reference numerals.

Use the PDF helpers when the environment lacks native PDF inspection:

```bash
python3 "$SKILL_DIR/scripts/patent_figure_ops.py" pdf-text paper.pdf --output patent-figures/extracted/paper.txt
python3 "$SKILL_DIR/scripts/patent_figure_ops.py" pdf-page paper.pdf --page 3 --output patent-figures/review/source-crops/paper-page-3.png
```

Never turn a paper result, hypothesis, or implementation convenience into an unsupported patent mechanism. If multiple inputs conflict, record the conflict and ask the user which technical basis controls before drawing the affected relation.

## Select the figure set

Read [references/patent-drawing-style.md](references/patent-drawing-style.md) before planning or reviewing SVG.

Default to the smallest set that explains the technical skeleton:

1. a system or interaction figure for boundaries and actors;
2. a method flow for the core transformation or decision;
3. a claim-critical detail such as a state machine, sequence, model structure, data relationship, or GUI state.

One or two figures are enough when they fully cover the mechanism. Do not force every project into the same template.

For each figure, add one `figure_plan` to `figure-manifest.json` before choosing coordinates. Include reading direction, regions, nodes, interfaces, edge semantics, and text levels. Add `text_support` entries that point to exact topic headings or PDF pages.

## Use source figures safely

If any paper, repository, blog, or existing drawing influences the layout, read [references/source-use.md](references/source-use.md).

Verify the source and record its stable locator. Describe its contribution as visual grammar, then complete a `keep / adapt / drop` mapping:

- `keep`: abstract hierarchy, repetition, branch, merge, feedback, or correspondence grammar;
- `adapt`: replace source content with exact input-supported objects and relations;
- `drop`: source names, logos, colors, icons, coordinates, formulas, values, conclusions, and mechanisms absent from the target input.

Do not trace exact geometry or labels. Store source crops only under `patent-figures/review/`; never embed them in final SVG or PNG deliverables.

## Draw the editable source

Use direct SVG as the default editable format. Produce Draw.io only when the user explicitly needs drag-and-drop editing.

Apply these hard requirements:

- use a white background with black or grayscale strokes and fills;
- use line type, shape, and label rather than color to encode meaning;
- keep all edge labels horizontal;
- route feedback and control edges outside the main data path;
- eliminate nonsemantic crossings and unsupported boundary intersections;
- use stable reference numerals across figures;
- include a figure identifier below the drawing;
- use a CJK-capable fallback font when labels contain CJK text;
- embed no external image, font, script, or stylesheet reference in filing SVG;
- keep every node and edge supported by an input locator.

Represent repeated units with a container, bracket, bus, or one expanded example plus abbreviated peers. Put the central difference mechanism at the visual center, not the source paper's branding or full experimental pipeline.

## Render the fixed preview

Render every final SVG to a white-background PNG:

```bash
python3 "$SKILL_DIR/scripts/patent_figure_ops.py" render \
  patent-figures/editable/fig1.svg \
  patent-figures/raster/fig1.png
```

The renderer uses CairoSVG, `rsvg-convert`, Inkscape, FFmpeg, or PyMuPDF when available. If none is installed, keep the SVG, report the missing optional renderer, and do not claim that the PNG was delivered.

## Review and validate

Inspect both the full-size PNG and a reduced view. Only then set every figure's `routing_review` value to `true`:

- `horizontal_edge_labels`;
- `parallel_edges_merged`;
- `feedback_routed_outside`;
- `nonsemantic_crossings_zero`;
- `frame_intersections_reviewed`;
- `reference_numerals_consistent`;
- `text_supported_by_input`.

Validate the final project:

```bash
python3 "$SKILL_DIR/scripts/patent_figure_ops.py" validate patent-figures/figure-manifest.json
```

When visual sources are recorded, optionally generate a review-only board:

```bash
python3 "$SKILL_DIR/scripts/patent_figure_ops.py" board \
  patent-figures/figure-manifest.json \
  --output patent-figures/review/comparison-board.svg \
  --png patent-figures/review/comparison-board.png
```

Keep the board out of filing deliverables and public documentation unless every included source image is cleared for that use.

## Report the result

Report:

- input files and exact supporting headings or PDF pages;
- the purpose of each figure;
- source provenance and `keep / adapt / drop` results when applicable;
- editable SVG and rendered PNG paths;
- optional Draw.io and review-board paths;
- validation results and unresolved support, overlap, or readability issues.

State clearly that patent-style figures do not establish novelty, inventorship, enablement, claim scope, or patentability.
