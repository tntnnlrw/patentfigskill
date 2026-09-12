from __future__ import annotations

import base64
import importlib.util
import json
import struct
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).parents[1]
    / "skills"
    / "patent-figure-redraw"
    / "scripts"
    / "patent_figure_ops.py"
)
SPEC = importlib.util.spec_from_file_location("patent_figure_ops", SCRIPT_PATH)
assert SPEC and SPEC.loader
OPS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OPS)


ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class PatentFigureOpsTests(unittest.TestCase):
    def create_final_project(self, root: Path) -> Path:
        topic = root / "topic.md"
        topic.write_text("# Core mechanism\nInput is checked before output.\n", encoding="utf-8")
        manifest_path = OPS.initialize_project(root, [topic], "patent-figures", False)
        editable = root / "patent-figures" / "editable" / "fig1.svg"
        editable.write_text(
            """<svg xmlns="http://www.w3.org/2000/svg" width="600" height="300" viewBox="0 0 600 300">
<rect width="600" height="300" fill="#fff"/>
<rect x="50" y="80" width="180" height="80" fill="#eee" stroke="#111"/>
<rect x="370" y="80" width="180" height="80" fill="#eee" stroke="#111"/>
<text x="140" y="125" text-anchor="middle" fill="#111">Input 100</text>
<text x="460" y="125" text-anchor="middle" fill="#111">Output 110</text>
<text x="300" y="275" text-anchor="middle" fill="#111">Figure 1</text>
</svg>
""",
            encoding="utf-8",
        )
        raster = root / "patent-figures" / "raster" / "fig1.png"
        raster.write_bytes(ONE_PIXEL_PNG)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["figures"] = [
            {
                "figure_no": 1,
                "purpose": "Show the core mechanism",
                "text_support": [{"path": "topic.md", "locator": "Core mechanism"}],
                "visual_source_ids": [],
                "figure_plan": {
                    "reading_direction": "left to right",
                    "regions": ["input", "output"],
                    "nodes": ["input", "output"],
                    "interfaces": ["data path"],
                    "edge_classes": {"solid": "data"},
                    "text_levels": ["functional label", "reference numeral"],
                },
                "routing_review": {
                    "horizontal_edge_labels": True,
                    "parallel_edges_merged": True,
                    "feedback_routed_outside": True,
                    "nonsemantic_crossings_zero": True,
                    "frame_intersections_reviewed": True,
                    "reference_numerals_consistent": True,
                    "text_supported_by_input": True,
                },
                "markers": {"100": "input", "110": "output"},
                "editable_svg": "patent-figures/editable/fig1.svg",
                "raster_png": "patent-figures/raster/fig1.png",
            }
        ]
        OPS.write_json(manifest_path, manifest)
        return manifest_path

    def test_init_uses_only_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            topic = root / "topic.md"
            topic.write_text("# Topic\n", encoding="utf-8")
            manifest_path = OPS.initialize_project(root, [topic], "patent-figures", False)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["project_root"], "..")
            self.assertEqual(manifest["inputs"][0]["path"], "topic.md")
            self.assertNotIn(str(root), manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(OPS.validate_manifest(manifest_path, draft=True), [])

    def test_minimal_final_project_validates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = self.create_final_project(Path(temp_dir))
            self.assertEqual(OPS.validate_manifest(manifest_path, draft=False), [])

    def test_absolute_manifest_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = self.create_final_project(root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["inputs"][0]["path"] = str(root / "topic.md")
            OPS.write_json(manifest_path, manifest)
            errors = OPS.validate_manifest(manifest_path, draft=True)
            self.assertTrue(any("must not be absolute" in error for error in errors))

    def test_release_audit_detects_sensitive_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "bad.txt").write_text("machine path: /" + "home/sample/private.txt\n", encoding="utf-8")
            metadata = b"author\x00sample"
            (root / "metadata.png").write_bytes(
                b"\x89PNG\r\n\x1a\n"
                + struct.pack(">I", len(metadata))
                + b"tEXt"
                + metadata
                + b"\x00\x00\x00\x00"
                + struct.pack(">I", 0)
                + b"IEND"
                + b"\xae\x42\x60\x82"
            )
            findings = OPS.audit_release(root, ["private-token"])
            self.assertTrue(any("machine-specific home path" in item for item in findings))
            self.assertTrue(any("PNG metadata" in item for item in findings))

    def test_drawio_validator_checks_edge_geometry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "figure.drawio"
            path.write_text(
                '<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
                '<mxCell id="a" vertex="1" parent="1"><mxGeometry as="geometry"/></mxCell>'
                '<mxCell id="e" edge="1" parent="1" source="a" target="a"/></root></mxGraphModel>',
                encoding="utf-8",
            )
            errors = OPS.validate_drawio(path)
            self.assertTrue(any("lacks relative mxGeometry" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
