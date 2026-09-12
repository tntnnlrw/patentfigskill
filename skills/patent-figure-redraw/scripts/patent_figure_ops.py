#!/usr/bin/env python3
"""Initialize, inspect, render, and validate standalone patent-figure projects."""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path, PureWindowsPath
from typing import Any, Iterable
from xml.etree import ElementTree as ET


SCHEMA_VERSION = "patentfig.project.v1"
DEFAULT_OUTPUT_DIR = "patent-figures"
INPUT_EXTENSIONS = {
    ".md": "topic",
    ".txt": "topic",
    ".pdf": "paper_pdf",
    ".json": "disclosure",
    ".svg": "existing_figure",
    ".png": "existing_figure",
    ".jpg": "existing_figure",
    ".jpeg": "existing_figure",
}
INPUT_KINDS = {
    "topic",
    "paper_pdf",
    "disclosure",
    "claims",
    "existing_figure",
}
VISUAL_SOURCE_ROLES = {
    "mechanism_source",
    "visual_ancestor",
    "baseline_source",
    "background",
    "separation_only",
}
REQUIRED_FIGURE_PLAN_FIELDS = (
    "reading_direction",
    "regions",
    "nodes",
    "interfaces",
    "edge_classes",
    "text_levels",
)
REQUIRED_ROUTING_REVIEW_FIELDS = (
    "horizontal_edge_labels",
    "parallel_edges_merged",
    "feedback_routed_outside",
    "nonsemantic_crossings_zero",
    "frame_intersections_reviewed",
    "reference_numerals_consistent",
    "text_supported_by_input",
)
PATH_KEYS = {
    "project_root",
    "path",
    "local_review_asset",
    "editable_svg",
    "editable_drawio",
    "raster_png",
    "before_png",
    "source_crop",
}
REFERENCE_MARKER_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:S\d{3}|(?:[1-9]\d{2}|[1-9]\d[A-Z])(?:-[A-Za-z0-9]+)?)(?![A-Za-z0-9_])"
)
ALLOWED_COLOR_NAMES = {
    "black",
    "white",
    "gray",
    "grey",
    "none",
    "transparent",
    "currentcolor",
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"JSON root must be an object: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def is_absolute_or_home_path(raw: str) -> bool:
    value = str(raw).strip()
    return Path(value).is_absolute() or PureWindowsPath(value).is_absolute() or value.startswith("~")


def resolve_within(root: Path, raw: str, label: str) -> Path:
    if not raw or is_absolute_or_home_path(raw):
        raise ValueError(f"{label} must be a non-empty relative path: {raw!r}")
    root = root.resolve()
    resolved = (root / raw).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} escapes the project directory: {raw}") from exc
    return resolved


def relative_posix(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def project_root_for_manifest(manifest_path: Path, manifest: dict[str, Any]) -> Path:
    raw = str(manifest.get("project_root") or "..").strip()
    if is_absolute_or_home_path(raw):
        raise ValueError(f"project_root must be relative: {raw}")
    return (manifest_path.parent / raw).resolve()


def guess_kind(path: Path) -> str:
    name = path.name.lower()
    if "claim" in name:
        return "claims"
    if "disclosure" in name or "technical-description" in name:
        return "disclosure"
    return INPUT_EXTENSIONS.get(path.suffix.lower(), "topic")


def discover_inputs(project: Path, output_root: Path) -> list[Path]:
    results: list[Path] = []
    for candidate in sorted(project.rglob("*")):
        if not candidate.is_file() or candidate.suffix.lower() not in INPUT_EXTENSIONS:
            continue
        relative_parts = candidate.relative_to(project).parts
        if any(part.startswith(".") for part in relative_parts):
            continue
        try:
            candidate.resolve().relative_to(output_root.resolve())
            continue
        except ValueError:
            pass
        results.append(candidate)
    return results


def initialize_project(
    project: Path,
    raw_inputs: list[Path],
    output_dir: str,
    force: bool,
) -> Path:
    project = project.resolve()
    if not project.is_dir():
        raise SystemExit(f"Project directory does not exist: {project}")
    try:
        output_root = resolve_within(project, output_dir, "output directory")
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    manifest_path = output_root / "figure-manifest.json"
    if manifest_path.exists() and not force:
        raise SystemExit(f"Manifest already exists; refusing to overwrite: {manifest_path}")

    inputs: list[Path] = []
    for raw in raw_inputs:
        candidate = raw if raw.is_absolute() else project / raw
        candidate = candidate.resolve()
        if not candidate.is_file():
            raise SystemExit(f"Input file does not exist: {candidate}")
        try:
            candidate.relative_to(project)
        except ValueError as exc:
            raise SystemExit(f"Input must be inside the project directory: {candidate}") from exc
        inputs.append(candidate)
    if not inputs:
        inputs = discover_inputs(project, output_root)
    if not inputs:
        raise SystemExit("No topic, text, PDF, JSON, SVG, or raster input was found")

    for directory in (
        output_root / "editable",
        output_root / "raster",
        output_root / "extracted",
        output_root / "review" / "source-crops",
    ):
        directory.mkdir(parents=True, exist_ok=True)

    manifest_inputs = []
    for index, path in enumerate(dict.fromkeys(inputs), start=1):
        kind = guess_kind(path)
        manifest_inputs.append(
            {
                "id": f"input{index}",
                "kind": kind,
                "path": relative_posix(path, project),
                "role": "controlling_disclosure" if index == 1 else "supporting_context",
                "locator": "",
            }
        )
    project_root = Path(os.path.relpath(project, manifest_path.parent)).as_posix()
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "project_root": project_root,
        "title": project.name,
        "inputs": manifest_inputs,
        "visual_sources": [],
        "grammar": [],
        "figures": [],
    }
    write_json(manifest_path, manifest)
    print(f"OK initialized {manifest_path} with {len(manifest_inputs)} input(s)")
    return manifest_path


def extract_pdf_text(pdf_path: Path, output: Path) -> None:
    pdf_path = pdf_path.resolve()
    if not pdf_path.is_file():
        raise SystemExit(f"Missing PDF: {pdf_path}")
    pages: list[str] | None = None
    try:
        import fitz  # type: ignore

        document = fitz.open(pdf_path)
        pages = [page.get_text("text") for page in document]
        document.close()
    except ImportError:
        converter = shutil.which("pdftotext")
        if converter:
            result = subprocess.run(
                [converter, "-layout", str(pdf_path), "-"],
                check=True,
                stdout=subprocess.PIPE,
            )
            pages = result.stdout.decode("utf-8", errors="replace").split("\f")
    if pages is None:
        raise SystemExit("PDF text extraction needs PyMuPDF or the pdftotext executable")
    output.parent.mkdir(parents=True, exist_ok=True)
    body = "\n\n".join(
        f"=== PDF page {index} ===\n{page.rstrip()}" for index, page in enumerate(pages, start=1)
    )
    output.write_text(body.rstrip() + "\n", encoding="utf-8")
    print(f"OK extracted {len(pages)} page(s) to {output}")


def render_pdf_page(pdf_path: Path, page_no: int, output: Path, dpi: int) -> None:
    if page_no < 1:
        raise SystemExit("PDF page numbers start at 1")
    pdf_path = pdf_path.resolve()
    if not pdf_path.is_file():
        raise SystemExit(f"Missing PDF: {pdf_path}")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        import fitz  # type: ignore

        document = fitz.open(pdf_path)
        if page_no > len(document):
            raise SystemExit(f"PDF has only {len(document)} page(s)")
        page = document[page_no - 1]
        scale = dpi / 72
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        pixmap.save(output)
        document.close()
    except ImportError:
        converter = shutil.which("pdftoppm")
        if not converter:
            raise SystemExit("PDF page rendering needs PyMuPDF or the pdftoppm executable")
        with tempfile.TemporaryDirectory(prefix="patentfig-") as temp_dir:
            prefix = Path(temp_dir) / "page"
            subprocess.run(
                [
                    converter,
                    "-f",
                    str(page_no),
                    "-l",
                    str(page_no),
                    "-singlefile",
                    "-png",
                    "-r",
                    str(dpi),
                    str(pdf_path),
                    str(prefix),
                ],
                check=True,
            )
            shutil.move(str(prefix) + ".png", output)
    print(f"OK rendered PDF page {page_no} to {output}")


def render_svg(svg_path: Path, output: Path) -> None:
    svg_path = svg_path.resolve()
    if not svg_path.is_file():
        raise SystemExit(f"Missing SVG: {svg_path}")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        import cairosvg  # type: ignore

        cairosvg.svg2png(url=str(svg_path), write_to=str(output), background_color="white")
    except ImportError:
        librsvg = shutil.which("rsvg-convert")
        inkscape = shutil.which("inkscape")
        if librsvg:
            subprocess.run(
                [librsvg, "--background-color", "white", str(svg_path), "-o", str(output)],
                check=True,
            )
        elif inkscape:
            subprocess.run(
                [
                    inkscape,
                    str(svg_path),
                    "--export-background=white",
                    f"--export-filename={output}",
                ],
                check=True,
            )
        else:
            ffmpeg = shutil.which("ffmpeg")
            if ffmpeg:
                subprocess.run(
                    [
                        ffmpeg,
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-y",
                        "-i",
                        str(svg_path),
                        "-frames:v",
                        "1",
                        str(output),
                    ],
                    check=True,
                )
            else:
                try:
                    import fitz  # type: ignore

                    document = fitz.open(stream=svg_path.read_bytes(), filetype="svg")
                    pixmap = document[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    pixmap.save(output)
                    document.close()
                except ImportError:
                    raise SystemExit(
                        "SVG rendering needs CairoSVG, rsvg-convert, Inkscape, FFmpeg, or PyMuPDF"
                    ) from None
    print(f"OK rendered {svg_path} to {output}")


def is_grayscale_color(token: str) -> bool:
    value = token.strip().lower()
    if value in ALLOWED_COLOR_NAMES or re.fullmatch(r"url\(#[\w:.-]+\)", value):
        return True
    if value.startswith("#"):
        raw = value[1:]
        if len(raw) in (3, 4):
            red, green, blue = (int(char * 2, 16) for char in raw[:3])
        elif len(raw) in (6, 8):
            red, green, blue = (int(raw[index : index + 2], 16) for index in (0, 2, 4))
        else:
            return False
        return red == green == blue
    rgb_match = re.fullmatch(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,[^)]+)?\)", value)
    if rgb_match:
        red, green, blue = (int(item) for item in rgb_match.groups())
        return red == green == blue and 0 <= red <= 255
    return False


def svg_reference_markers(root: ET.Element) -> set[str]:
    markers: set[str] = set()
    for element in root.iter():
        if str(element.tag).rsplit("}", 1)[-1].lower() == "text":
            markers.update(REFERENCE_MARKER_RE.findall("".join(element.itertext())))
    return markers


def validate_svg(path: Path, drop_terms: Iterable[str]) -> tuple[list[str], set[str]]:
    errors: list[str] = []
    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError) as exc:
        return [f"invalid SVG {path}: {exc}"], set()
    root = tree.getroot()
    raw = path.read_text(encoding="utf-8")
    forbidden: set[str] = set()
    rotated_text = False
    for element in root.iter():
        local_tag = str(element.tag).rsplit("}", 1)[-1].lower()
        if local_tag in {"lineargradient", "radialgradient", "filter", "script"}:
            forbidden.add(local_tag)
        if "filter" in element.attrib:
            forbidden.add("filter attribute")
        transform = str(element.attrib.get("transform") or "")
        descendants = {
            str(descendant.tag).rsplit("}", 1)[-1].lower() for descendant in element.iter()
        }
        if "rotate(" in transform.lower() and descendants.intersection({"text", "tspan"}):
            rotated_text = True
        if local_tag in {"text", "tspan"} and str(element.attrib.get("rotate") or "").strip():
            rotated_text = True
    if rotated_text:
        errors.append(f"rotated text is not allowed in filing SVG: {path}")
    if re.search(r"writing-mode\s*(?::|=)\s*[\"']?\s*(?:vertical|sideways|tb-)", raw, flags=re.I):
        errors.append(f"vertical writing mode is not allowed in filing SVG: {path}")
    for item in sorted(forbidden):
        errors.append(f"forbidden SVG effect or element {item}: {path}")

    for href in re.findall(r"(?:href|xlink:href)\s*=\s*[\"']([^\"']+)", raw, flags=re.I):
        if not href.startswith(("#", "data:")):
            errors.append(f"external SVG reference is not allowed: {href}")
    colors = re.findall(r"\b(?:fill|stroke)\s*=\s*[\"']([^\"']+)", raw, flags=re.I)
    colors.extend(re.findall(r"(?:^|[;{])\s*(?:fill|stroke)\s*:\s*([^;}]+)", raw, flags=re.I | re.M))
    for color in sorted(set(colors)):
        if not is_grayscale_color(color):
            errors.append(f"non-grayscale or unsupported color {color.strip()}: {path}")

    visible_text = "\n".join(
        "".join(element.itertext())
        for element in root.iter()
        if str(element.tag).rsplit("}", 1)[-1].lower() == "text"
    ).lower()
    for term in drop_terms:
        normalized = str(term).strip().lower()
        if len(normalized) >= 3 and normalized in visible_text:
            errors.append(f"dropped source term leaked into SVG {path}: {term}")
    return errors, svg_reference_markers(root)


def validate_drawio(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError) as exc:
        return [f"invalid Draw.io XML {path}: {exc}"]
    raw = path.read_text(encoding="utf-8")
    if "<!--" in raw:
        errors.append(f"Draw.io XML must not contain comments: {path}")
    root = tree.getroot()
    if root.tag == "mxfile":
        models = root.findall(".//mxGraphModel")
    elif root.tag == "mxGraphModel":
        models = [root]
    else:
        models = []
    if not models:
        errors.append(f"Draw.io file lacks mxGraphModel: {path}")
        return errors
    ids: list[str] = []
    for model in models:
        graph_root = model.find("root")
        if graph_root is None:
            errors.append(f"Draw.io mxGraphModel lacks root: {path}")
            continue
        root_ids = {cell.get("id") for cell in graph_root.findall("mxCell")}
        if not {"0", "1"}.issubset(root_ids):
            errors.append(f"Draw.io root must contain cells 0 and 1: {path}")
        for cell in graph_root.findall(".//mxCell"):
            cell_id = str(cell.get("id") or "")
            if cell_id:
                ids.append(cell_id)
            if cell.get("edge") == "1":
                geometry = cell.find("mxGeometry")
                if geometry is None or geometry.get("relative") != "1":
                    errors.append(f"Draw.io edge {cell_id or '?'} lacks relative mxGeometry: {path}")
    duplicates = sorted({cell_id for cell_id in ids if ids.count(cell_id) > 1})
    if duplicates:
        errors.append(f"Draw.io cell ids must be unique; duplicated {duplicates}: {path}")
    return errors


def iter_manifest_paths(value: Any, key: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            yield from iter_manifest_paths(child_value, str(child_key))
    elif isinstance(value, list):
        for child in value:
            yield from iter_manifest_paths(child, key)
    elif key in PATH_KEYS and value not in (None, ""):
        yield key, str(value)


def validate_manifest(manifest_path: Path, draft: bool) -> list[str]:
    manifest_path = manifest_path.resolve()
    manifest = load_json(manifest_path)
    errors: list[str] = []
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    try:
        project_root = project_root_for_manifest(manifest_path, manifest)
    except ValueError as exc:
        return [str(exc)]
    if not project_root.is_dir():
        errors.append(f"project_root does not exist: {project_root}")

    for key, raw in iter_manifest_paths(manifest):
        if is_absolute_or_home_path(raw):
            errors.append(f"manifest {key} must not be absolute or home-relative: {raw}")

    inputs = manifest.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        errors.append("manifest must contain at least one input")
        inputs = []
    input_ids: set[str] = set()
    for entry in inputs:
        if not isinstance(entry, dict):
            errors.append("invalid input entry")
            continue
        input_id = str(entry.get("id") or "")
        if not input_id or input_id in input_ids:
            errors.append(f"input id is missing or duplicated: {input_id!r}")
        input_ids.add(input_id)
        if entry.get("kind") not in INPUT_KINDS:
            errors.append(f"input {input_id} has unsupported kind: {entry.get('kind')}")
        try:
            input_path = resolve_within(project_root, str(entry.get("path") or ""), f"input {input_id} path")
            if not input_path.is_file():
                errors.append(f"input {input_id} is missing: {input_path}")
        except ValueError as exc:
            errors.append(str(exc))

    visual_sources_list = manifest.get("visual_sources", [])
    if not isinstance(visual_sources_list, list):
        errors.append("visual_sources must be a list")
        visual_sources_list = []
    visual_sources: dict[str, dict[str, Any]] = {}
    for source in visual_sources_list:
        if not isinstance(source, dict):
            errors.append("invalid visual source entry")
            continue
        source_id = str(source.get("id") or "")
        if not source_id or source_id in visual_sources:
            errors.append(f"visual source id is missing or duplicated: {source_id!r}")
        visual_sources[source_id] = source
        if not source.get("selected_for_visual_grammar"):
            continue
        if source.get("role") not in VISUAL_SOURCE_ROLES:
            errors.append(f"visual source {source_id} has invalid role: {source.get('role')}")
        verification = source.get("verification", {})
        if not str(verification.get("status") or "").strip():
            errors.append(f"visual source {source_id} lacks verification status")
        if not str(verification.get("evidence") or "").strip():
            errors.append(f"visual source {source_id} lacks verification evidence")
        if not str(source.get("figure_locator") or "").strip():
            errors.append(f"visual source {source_id} lacks figure_locator")
        raw_asset = str(source.get("local_review_asset") or "")
        try:
            asset_path = resolve_within(project_root, raw_asset, f"visual source {source_id} review asset")
            if not asset_path.is_file():
                errors.append(f"visual source {source_id} review asset is missing: {asset_path}")
            if "review" not in {part.lower() for part in asset_path.relative_to(project_root).parts}:
                errors.append(f"visual source {source_id} asset must stay under a review directory")
        except ValueError as exc:
            errors.append(str(exc))

    grammar_list = manifest.get("grammar", [])
    if not isinstance(grammar_list, list):
        errors.append("grammar must be a list")
        grammar_list = []
    grammar = {
        str(entry.get("source_id")): entry
        for entry in grammar_list
        if isinstance(entry, dict) and entry.get("source_id")
    }
    figures = manifest.get("figures")
    if not isinstance(figures, list):
        errors.append("figures must be a list")
        figures = []
    if draft:
        return errors
    if not figures:
        errors.append("final manifest must contain at least one figure")

    marker_meanings: dict[str, str] = {}
    for figure in figures:
        if not isinstance(figure, dict):
            errors.append("invalid figure entry")
            continue
        number = figure.get("figure_no", "?")
        if not str(figure.get("purpose") or "").strip():
            errors.append(f"figure {number} lacks purpose")
        support_entries = figure.get("text_support")
        if not isinstance(support_entries, list) or not support_entries:
            errors.append(f"figure {number} lacks text_support")
            support_entries = []
        for support in support_entries:
            if not isinstance(support, dict):
                errors.append(f"figure {number} has an invalid text_support entry")
                continue
            raw_support = str(support.get("path") or "")
            locator = str(support.get("locator") or "").strip()
            if not locator:
                errors.append(f"figure {number} text_support lacks a locator")
            try:
                support_path = resolve_within(project_root, raw_support, f"figure {number} support path")
                if not support_path.is_file():
                    errors.append(f"figure {number} support file is missing: {support_path}")
                elif support_path.suffix.lower() in {".md", ".txt", ".json"} and locator:
                    content = support_path.read_text(encoding="utf-8", errors="replace")
                    if locator not in content:
                        errors.append(f"figure {number} locator not found in {raw_support}: {locator}")
            except ValueError as exc:
                errors.append(str(exc))

        plan = figure.get("figure_plan")
        if not isinstance(plan, dict):
            errors.append(f"figure {number} lacks figure_plan")
        else:
            for field in REQUIRED_FIGURE_PLAN_FIELDS:
                if not plan.get(field):
                    errors.append(f"figure {number} figure_plan lacks or empties {field}")
        routing = figure.get("routing_review")
        if not isinstance(routing, dict):
            errors.append(f"figure {number} lacks routing_review")
        else:
            for field in REQUIRED_ROUTING_REVIEW_FIELDS:
                if routing.get(field) is not True:
                    errors.append(f"figure {number} routing_review requires {field}=true")

        source_ids = figure.get("visual_source_ids", [])
        if not isinstance(source_ids, list):
            errors.append(f"figure {number} visual_source_ids must be a list")
            source_ids = []
        drop_terms: list[str] = []
        for source_id in source_ids:
            source = visual_sources.get(str(source_id))
            if not source:
                errors.append(f"figure {number} references unknown visual source {source_id}")
                continue
            if not source.get("selected_for_visual_grammar"):
                errors.append(f"figure {number} uses unselected visual source {source_id}")
            mapping = grammar.get(str(source_id))
            if not mapping:
                errors.append(f"figure {number} lacks keep/adapt/drop mapping for {source_id}")
                continue
            for field in ("keep", "adapt", "drop"):
                if not mapping.get(field):
                    errors.append(f"figure {number} grammar for {source_id} lacks {field}")
            drop_terms.extend(str(term) for term in mapping.get("drop", []))

        markers = figure.get("markers")
        if not isinstance(markers, dict) or not markers:
            errors.append(f"figure {number} lacks marker explanations")
            markers = {}
        for marker, meaning in markers.items():
            marker = str(marker)
            meaning = str(meaning).strip()
            if not REFERENCE_MARKER_RE.fullmatch(marker):
                errors.append(f"figure {number} has invalid reference marker: {marker}")
            if not meaning:
                errors.append(f"figure {number} marker {marker} lacks an explanation")
            previous = marker_meanings.get(marker)
            if previous is not None and previous != meaning:
                errors.append(f"reference marker {marker} has inconsistent meanings")
            marker_meanings[marker] = meaning

        raw_svg = str(figure.get("editable_svg") or "")
        try:
            svg_path = resolve_within(project_root, raw_svg, f"figure {number} editable_svg")
            if not svg_path.is_file():
                errors.append(f"figure {number} SVG is missing: {svg_path}")
                used_markers: set[str] = set()
            else:
                svg_errors, used_markers = validate_svg(svg_path, drop_terms)
                errors.extend(svg_errors)
            declared_markers = {str(marker) for marker in markers}
            for marker in sorted(used_markers - declared_markers):
                errors.append(f"figure {number} SVG marker {marker} lacks an explanation")
            for marker in sorted(declared_markers - used_markers):
                errors.append(f"figure {number} declares unused marker {marker}")
        except ValueError as exc:
            errors.append(str(exc))

        raw_png = str(figure.get("raster_png") or "")
        try:
            png_path = resolve_within(project_root, raw_png, f"figure {number} raster_png")
            if not png_path.is_file():
                errors.append(f"figure {number} PNG is missing: {png_path}")
            else:
                try:
                    png_size(png_path)
                except ValueError as exc:
                    errors.append(str(exc))
        except ValueError as exc:
            errors.append(str(exc))

        raw_drawio = str(figure.get("editable_drawio") or "")
        if raw_drawio:
            try:
                drawio_path = resolve_within(
                    project_root, raw_drawio, f"figure {number} editable_drawio"
                )
                if not drawio_path.is_file():
                    errors.append(f"figure {number} Draw.io file is missing: {drawio_path}")
                else:
                    errors.extend(validate_drawio(drawio_path))
            except ValueError as exc:
                errors.append(str(exc))
    return errors


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a valid PNG file: {path}")
    return struct.unpack(">II", header[16:24])


def image_data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def fit_box(width: int, height: int, max_width: int, max_height: int) -> tuple[float, float]:
    scale = min(max_width / width, max_height / height)
    return width * scale, height * scale


def clip_text(value: str, limit: int = 120) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    return value if len(value) <= limit else value[: limit - 1] + "…"


def wrap_text(value: str, width: int = 70, max_lines: int = 2) -> list[str]:
    lines = textwrap.wrap(re.sub(r"\s+", " ", value).strip(), width=width) or [""]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = clip_text(lines[-1], width - 1) + "…"
    return lines


def build_board(manifest_path: Path, output: Path, png_output: Path | None) -> None:
    manifest_path = manifest_path.resolve()
    manifest = load_json(manifest_path)
    try:
        project_root = project_root_for_manifest(manifest_path, manifest)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    figures = manifest.get("figures", [])
    if not figures:
        raise SystemExit("No figures in the manifest")
    sources = {
        str(source.get("id")): source
        for source in manifest.get("visual_sources", [])
        if isinstance(source, dict)
    }
    width = 3600
    header_height = 145
    row_height = 820
    height = header_height + row_height * len(figures) + 40
    columns = [(60, "Previous / input"), (1225, "Visual source (review only)"), (2390, "Patent redraw")]
    column_width = 1100
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<style>text{font-family:"Noto Sans CJK SC","Microsoft YaHei",Arial,sans-serif;fill:#111}.h{font-size:40px;font-weight:700}.t{font-size:30px;font-weight:700}.s{font-size:22px}.cell{fill:#fff;stroke:#444;stroke-width:2}.row{fill:#fafafa;stroke:#777;stroke-width:2}</style>',
        f'<text x="1800" y="55" text-anchor="middle" class="h">{html.escape(str(manifest.get("title") or "Patent figure review"))}</text>',
    ]
    for x, label in columns:
        parts.append(f'<text x="{x + column_width / 2}" y="112" text-anchor="middle" class="t">{label}</text>')
    for index, figure in enumerate(figures):
        row_y = header_height + index * row_height
        number = figure.get("figure_no", index + 1)
        purpose = clip_text(str(figure.get("purpose") or ""), 150)
        parts.append(f'<rect x="25" y="{row_y}" width="3550" height="790" rx="16" class="row"/>')
        parts.append(f'<text x="65" y="{row_y + 48}" class="t">Figure {number}: {html.escape(purpose)}</text>')
        source_crop = str(figure.get("source_crop") or "")
        source_note = ""
        if not source_crop:
            for source_id in figure.get("visual_source_ids", []):
                source = sources.get(str(source_id))
                if source and source.get("local_review_asset"):
                    source_crop = str(source["local_review_asset"])
                    source_note = " — ".join(
                        filter(None, [str(source.get("title") or ""), str(source.get("figure_locator") or "")])
                    )
                    break
        assets = [
            str(figure.get("before_png") or ""),
            source_crop,
            str(figure.get("raster_png") or ""),
        ]
        notes = ["", source_note, str(figure.get("redraw_note") or "")]
        for column_index, ((x, _), raw_asset) in enumerate(zip(columns, assets)):
            cell_y = row_y + 70
            parts.append(f'<rect x="{x}" y="{cell_y}" width="{column_width}" height="690" rx="12" class="cell"/>')
            if not raw_asset:
                parts.append(f'<text x="{x + column_width / 2}" y="{cell_y + 335}" text-anchor="middle" class="s">Not provided</text>')
                continue
            try:
                asset_path = resolve_within(project_root, raw_asset, "board asset")
            except ValueError as exc:
                raise SystemExit(str(exc)) from exc
            if not asset_path.is_file():
                raise SystemExit(f"Missing board asset: {asset_path}")
            image_width, image_height = png_size(asset_path)
            draw_width, draw_height = fit_box(image_width, image_height, column_width - 45, 570)
            draw_x = x + (column_width - draw_width) / 2
            draw_y = row_y + 112 + (570 - draw_height) / 2
            parts.append(
                f'<image x="{draw_x:.1f}" y="{draw_y:.1f}" width="{draw_width:.1f}" height="{draw_height:.1f}" preserveAspectRatio="xMidYMid meet" href="{image_data_uri(asset_path)}"/>'
            )
            for line_index, line in enumerate(wrap_text(notes[column_index])):
                parts.append(f'<text x="{x + 20}" y="{cell_y + 638 + 26 * line_index}" class="s">{html.escape(line)}</text>')
    parts.append("</svg>")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"OK wrote {output}")
    if png_output:
        render_svg(output, png_output)


def audit_release(root: Path, deny_terms: list[str]) -> list[str]:
    root = root.resolve()
    findings: list[str] = []
    home_pattern = re.compile(r"/(?:home|Users)/[^/\s\"']+/", flags=re.I)
    windows_home_pattern = re.compile(r"[A-Za-z]:[\\/]Users[\\/][^\\/\s\"']+[\\/]", flags=re.I)
    email_pattern = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", flags=re.I)
    ignored_parts = {".git", "__pycache__", ".pytest_cache", ".venv"}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ignored_parts.intersection(path.relative_to(root).parts):
            continue
        if path.stat().st_size > 20_000_000:
            continue
        raw = path.read_bytes()
        text_value = raw.decode("utf-8", errors="replace")
        relative = path.relative_to(root).as_posix()
        if path.suffix.lower() == ".png" and raw.startswith(b"\x89PNG\r\n\x1a\n"):
            cursor = 8
            metadata_chunks: set[str] = set()
            while cursor + 12 <= len(raw):
                length = struct.unpack(">I", raw[cursor : cursor + 4])[0]
                chunk_type = raw[cursor + 4 : cursor + 8].decode("ascii", errors="replace")
                if chunk_type in {"tEXt", "zTXt", "iTXt", "eXIf"}:
                    metadata_chunks.add(chunk_type)
                cursor += 12 + length
                if chunk_type == "IEND":
                    break
            if metadata_chunks:
                findings.append(
                    f"{relative}: review or strip PNG metadata chunks {sorted(metadata_chunks)}"
                )
        if path.suffix.lower() == ".pdf":
            pdf_fields = sorted(
                {
                    match.decode("ascii")
                    for match in re.findall(
                        rb"/(Author|Creator|Producer|Subject|Keywords)\s*\(", raw
                    )
                }
            )
            if pdf_fields:
                findings.append(f"{relative}: review or strip PDF metadata fields {pdf_fields}")
        if path.suffix.lower() == ".svg" and re.search(
            r"<metadata\b|inkscape:export-filename|sodipodi:docname",
            text_value,
            flags=re.I,
        ):
            findings.append(f"{relative}: review or strip SVG editor metadata")
        for line_no, line in enumerate(text_value.splitlines(), start=1):
            if home_pattern.search(line) or windows_home_pattern.search(line):
                findings.append(f"{relative}:{line_no}: machine-specific home path")
            if email_pattern.search(line):
                findings.append(f"{relative}:{line_no}: email address")
            lowered = line.lower()
            for term in deny_terms:
                if term.lower() in lowered:
                    findings.append(f"{relative}:{line_no}: denied term")
    return findings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="initialize a relative-path figure manifest")
    init_parser.add_argument("project", type=Path)
    init_parser.add_argument("inputs", type=Path, nargs="*")
    init_parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    init_parser.add_argument("--force", action="store_true")

    text_parser = subparsers.add_parser("pdf-text", help="extract page-delimited text from a PDF")
    text_parser.add_argument("pdf", type=Path)
    text_parser.add_argument("--output", type=Path, required=True)

    page_parser = subparsers.add_parser("pdf-page", help="render one PDF page for internal review")
    page_parser.add_argument("pdf", type=Path)
    page_parser.add_argument("--page", type=int, required=True)
    page_parser.add_argument("--output", type=Path, required=True)
    page_parser.add_argument("--dpi", type=int, default=160)

    render_parser = subparsers.add_parser("render", help="render SVG to a white-background PNG")
    render_parser.add_argument("svg", type=Path)
    render_parser.add_argument("png", type=Path)

    validate_parser = subparsers.add_parser("validate", help="validate a figure manifest and artifacts")
    validate_parser.add_argument("manifest", type=Path)
    validate_parser.add_argument("--draft", action="store_true")

    board_parser = subparsers.add_parser("board", help="create a review-only comparison board")
    board_parser.add_argument("manifest", type=Path)
    board_parser.add_argument("--output", type=Path, required=True)
    board_parser.add_argument("--png", type=Path)

    audit_parser = subparsers.add_parser("audit-release", help="scan text files for release-sensitive strings")
    audit_parser.add_argument("root", type=Path)
    audit_parser.add_argument("--deny-term", action="append", default=[])
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "init":
        initialize_project(args.project, args.inputs, args.output_dir, args.force)
    elif args.command == "pdf-text":
        extract_pdf_text(args.pdf, args.output)
    elif args.command == "pdf-page":
        render_pdf_page(args.pdf, args.page, args.output, args.dpi)
    elif args.command == "render":
        render_svg(args.svg, args.png)
    elif args.command == "validate":
        errors = validate_manifest(args.manifest, args.draft)
        if errors:
            for error in errors:
                print(f"ERROR {error}", file=sys.stderr)
            raise SystemExit(1)
        mode = "draft" if args.draft else "final"
        print(f"OK validated {mode} manifest {args.manifest}")
    elif args.command == "board":
        build_board(args.manifest, args.output.resolve(), args.png.resolve() if args.png else None)
    elif args.command == "audit-release":
        findings = audit_release(args.root, args.deny_term)
        if findings:
            for finding in findings:
                print(f"ERROR {finding}", file=sys.stderr)
            raise SystemExit(1)
        print(f"OK release audit passed for {args.root}")


if __name__ == "__main__":
    main()
