"""LaTeX Renderer — converts Markdown manuscripts to LaTeX/PDF."""

import re
from datetime import datetime, timezone
from typing import Any


class LatexRendererError(Exception):
    """Raised on LaTeX rendering failures."""


class LatexRenderer:
    """Renders structured manuscripts to LaTeX/PDF."""

    def render(self, manuscript_md: str, spec: dict) -> str:
        """Convert Markdown manuscript to LaTeX string."""
        experiment = spec.get("experiment", {})
        publication = spec.get("publication", {})

        latex_parts = [
            self._preamble(experiment, publication),
            self._body(manuscript_md),
            r"\end{document}",
        ]

        return "\n".join(latex_parts)

    def _preamble(self, experiment: dict, publication: dict) -> str:
        title = experiment.get("title", "Untitled")
        authors = [a["name"] for a in publication.get("authors", [])]
        author_str = r"\and ".join(authors)

        return (
            r"\documentclass[11pt]{article}" + "\n"
            r"\usepackage[utf8]{inputenc}" + "\n"
            r"\usepackage{geometry}" + "\n"
            r"\usepackage{booktabs}" + "\n"
            r"\usepackage{graphicx}" + "\n"
            r"\usepackage{hyperref}" + "\n"
            r"\geometry{margin=1in}" + "\n"
            r"\title{" + title + "}" + "\n"
            r"\author{" + author_str + "}" + "\n"
            r"\date{" + datetime.now(timezone.utc).strftime("%B %d, %Y") + "}" + "\n\n"
            r"\begin{document}" + "\n"
            r"\maketitle" + "\n"
        )

    def _body(self, manuscript_md: str) -> str:
        """Convert Markdown to basic LaTeX."""
        lines = manuscript_md.split("\n")
        latex_lines = []
        in_list = False

        for line in lines:
            # Headings
            if line.startswith("# "):
                latex_lines.append(r"\section*{" + line[2:] + "}")
            elif line.startswith("## "):
                latex_lines.append(r"\subsection*{" + line[3:] + "}")
            elif line.startswith("### "):
                latex_lines.append(r"\subsubsection*{" + line[4:] + "}")

            # List items
            elif line.startswith("- "):
                if not in_list:
                    latex_lines.append(r"\begin{itemize}")
                    in_list = True
                latex_lines.append(r"\item " + line[2:])

            # Empty line ends list
            elif not line.strip() and in_list:
                latex_lines.append(r"\end{itemize}")
                in_list = False

            # Plain text
            elif line.strip():
                escaped = self._escape_latex(line)
                if escaped.strip():
                    latex_lines.append(escaped + r"\\")

            else:
                latex_lines.append("")

        if in_list:
            latex_lines.append(r"\end{itemize}")

        return "\n".join(latex_lines)

    def _escape_latex(self, text: str) -> str:
        """Escape special LaTeX characters."""
        replacements = {
            "&": r"\&",
            "%": r"\%",
            "$": r"\$",
            "#": r"\#",
            "_": r"\_",
            "{": r"\{",
            "}": r"\}",
            "~": r"\textasciitilde{}",
            "^": r"\^{}",
        }
        for char, escaped in replacements.items():
            text = text.replace(char, escaped)
        return text

    def render_to_file(self, manuscript_md: str, spec: dict, output_path: str):
        """Render and write LaTeX to file."""
        latex = self.render(manuscript_md, spec)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(latex)
