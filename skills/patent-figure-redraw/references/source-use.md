# Source use and provenance

## Contents

- Source roles
- Verification gate
- Visual-grammar mapping
- Review asset boundary
- Technical and legal limits

## Source roles

Record why each source is present:

- `technical_basis`: supports the target mechanism or terminology;
- `mechanism_source`: has substantial technical overlap requiring careful separation;
- `visual_ancestor`: contributes layout grammar only;
- `baseline_source`: describes a comparison method;
- `background`: provides scene or vocabulary only;
- `separation_only`: documents what the target does not claim.

A paper PDF may be both a technical input and a visual source. Record the roles separately.

## Verification gate

Before using an external figure as visual evidence, record:

- the exact figure number, PDF page, file path, or stable anchor;
- the canonical identifier, version, or commit when available;
- a local review crop.

Do not silently substitute a similarly named source. When a source has no stable identifier, such as a standalone image, record its available provenance and note that it cannot be independently verified.

## Visual-grammar mapping

For every selected visual source, record:

```json
{
  "source_id": "source1",
  "topology": "decision followed by fallback and an exterior feedback loop",
  "keep": ["branch and merge grammar", "exterior feedback route"],
  "adapt": ["replace the source gate with the input-supported confidence decision"],
  "drop": ["source method name", "logo", "colors", "experiment values"]
}
```

`keep` may preserve only abstract visual organization. `adapt` must be supported by an input locator. `drop` terms must not leak into final SVG text.

Do not copy exact coordinates, icons, graphical styling, labels, formulas, captions, or a distinctive arrangement when a new arrangement can explain the target mechanism.

## Review asset boundary

- Keep source crops under `patent-figures/review/source-crops/`.
- Use the smallest crop needed for internal review.
- Do not embed source crops in filing SVG or PNG.
- Do not publish a source-versus-redraw board without checking the source image's publication terms.
- Keep a stable source locator even when the crop cannot be redistributed.

## Technical and legal limits

The skill can help document provenance and reduce accidental copying. It cannot determine whether a use is licensed, fair, non-infringing, patentable, novel, enabled, or correctly attributed under every jurisdiction.

Treat publication clearance and patent analysis as separate review tasks. A visually distinct redraw does not repair unsupported disclosure or remove substantive overlap with prior work.
