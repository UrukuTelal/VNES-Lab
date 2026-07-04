"""Tests for the LaTeX Renderer."""

import os
import tempfile
import pytest
from rlaaer.publication.latex_renderer import LatexRenderer


class TestLatexRenderer:
    @pytest.fixture
    def renderer(self):
        return LatexRenderer()

    def test_basic_latex_output(self, renderer):
        md = "# Title\n\nAbstract content.\n## Section\n\n- item 1\n- item 2"
        spec = {
            "experiment": {"id": "001", "title": "Test Experiment"},
            "publication": {"authors": [{"name": "Author One"}], "format": "latex", "license": "CC"},
        }
        latex = renderer.render(md, spec)

        assert r"\documentclass[11pt]{article}" in latex
        assert r"\begin{document}" in latex
        assert r"\end{document}" in latex
        assert r"\title{Test Experiment}" in latex
        assert r"\author{Author One}" in latex
        assert r"\section*{Title}" in latex

    def test_section_heading(self, renderer):
        md = "## Methods"
        spec = {"experiment": {"id": "001", "title": "T"}, "publication": {"authors": [{"name": "A"}], "format": "latex", "license": "CC"}}
        latex = renderer.render(md, spec)
        assert r"\subsection*{Methods}" in latex

    def test_list_conversion(self, renderer):
        md = "- item A\n- item B"
        spec = {"experiment": {"id": "001", "title": "T"}, "publication": {"authors": [{"name": "A"}], "format": "latex", "license": "CC"}}
        latex = renderer.render(md, spec)
        assert r"\begin{itemize}" in latex
        assert r"\item item A" in latex
        assert r"\end{itemize}" in latex

    def test_special_characters_escaped(self, renderer):
        md = "Cost: $100 & 50%"
        spec = {"experiment": {"id": "001", "title": "T"}, "publication": {"authors": [{"name": "A"}], "format": "latex", "license": "CC"}}
        latex = renderer.render(md, spec)
        assert r"\$" in latex
        assert r"\&" in latex
        assert r"\%" in latex

    def test_render_to_file(self, renderer):
        md = "# Test"
        spec = {"experiment": {"id": "001", "title": "T"}, "publication": {"authors": [{"name": "A"}], "format": "latex", "license": "CC"}}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.tex")
            renderer.render_to_file(md, spec, path)
            assert os.path.exists(path)
            with open(path) as f:
                content = f.read()
            assert r"\begin{document}" in content
