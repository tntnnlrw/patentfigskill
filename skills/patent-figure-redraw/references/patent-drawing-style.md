# Patent drawing style

## Contents

- Core principle
- Figure selection
- Visual grammar
- Labels and numerals
- Routing gate
- SVG requirements

## Core principle

Show the technical concept skeleton that the input actually supports. Do not reproduce the whole research pipeline merely because it appears in a paper.

Sparse figures are a useful default, not a filing rule. A claim-critical decision flow, GUI state, sequence, model structure, or data relationship may legitimately be dense.

## Figure selection

Choose from these figure types according to the mechanism:

| Figure type | Best use |
| --- | --- |
| system architecture | actors, deployment boundary, protected object |
| device or module structure | internal functional units and interfaces |
| method flow | ordered actions, branches, fallback, termination |
| timing sequence | messages or state changes across actors |
| data flow | transformations among inputs, state, model, and outputs |
| deployment topology | cloud, edge, client, region, or device hierarchy |
| state transition | lifecycle, gate, retry, recovery, retirement |
| GUI interaction | interface state or action when it is technically relevant |
| model structure | claim-critical layer, route, correspondence, or memory relation |
| effect figure | compact technical result only when the source supports it |

The default set is one system/interaction figure, one core method flow, and one detail figure. Use fewer when possible.

## Visual grammar

Useful reusable patterns include:

- top server with repeated lower clients;
- left-to-right source, transform, decision, and output;
- router, repeated unit bank, and merge;
- aligned teacher/student or input/output correspondence;
- precision, state, or ownership attached to a data path;
- decision with fallback and an exterior feedback loop;
- actor lanes with horizontal message arrows;
- one expanded repeated unit with abbreviated peers.

Reuse only the abstract grammar. Replace labels and relations with input-supported content and choose new coordinates.

## Labels and numerals

- Use short nouns for modules and the shortest complete action needed for method steps.
- Keep labels horizontal and readable in the raster preview.
- Use module numerals such as `100`, `110`, and `120` consistently.
- Use method-step markers such as `S101`, `S102`, and `S103` consistently.
- Explain every visible reference marker in the manifest.
- Do not reuse one marker for different objects in the same project.
- Put the figure identifier below the drawing.

## Routing gate

- Merge identical cross-region transfers into a named interface or bus.
- Route feedback, retry, and control paths around the main data path.
- Let a line cross a group boundary only when it enters or exits a supported node or explicit port.
- Remove every nonsemantic line crossing.
- Use solid, dashed, and dash-dot lines only with recorded meanings.
- Inspect at full size and at the size used in the review board or README.

## SVG requirements

- white background;
- black, white, or grayscale colors only;
- no gradients, shadows, filters, logos, or decorative icons;
- no rotated text or vertical writing mode;
- no external image, font, script, or stylesheet references;
- complete arrowheads and closed paths;
- CJK-capable font fallback when needed;
- sufficient whitespace around labels and figure identifier;
- editable text and vector shapes rather than one embedded raster image.

Grayscale photographs or technical input/output examples are acceptable only when line art cannot convey a source-supported, claim-relevant relation. Keep them subordinate to the technical drawing and verify publication rights separately.
