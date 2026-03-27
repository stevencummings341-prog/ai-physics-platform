"""Generate experiment reports from Jinja2 Markdown templates."""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Any

log = logging.getLogger(__name__)

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    Environment = None  # type: ignore[assignment,misc]
    FileSystemLoader = None  # type: ignore[assignment,misc]
    log.warning("jinja2 not installed — report generation disabled.")


TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "report_templates")


class ReportGenerator:
    """Render a Jinja2 .md.j2 template with experiment data into a Markdown report."""

    def __init__(self, template_dir: str = TEMPLATE_DIR):
        self.template_dir = template_dir
        if Environment is not None:
            self._env = Environment(
                loader=FileSystemLoader(template_dir),
                keep_trailing_newline=True,
            )
        else:
            self._env = None

    def render(
        self,
        template_name: str,
        out_path: str,
        context: dict[str, Any],
    ) -> str:
        """Render template to a Markdown file. Returns output path."""
        if self._env is None:
            log.error("jinja2 is required for report generation. pip install jinja2")
            raise RuntimeError("jinja2 not available")

        template = self._env.get_template(template_name)
        md_content = template.render(**context)

        with open(out_path, "w") as f:
            f.write(md_content)
        log.info("Report written to %s", out_path)
        return out_path

    @staticmethod
    def md_to_pdf(md_path: str, pdf_path: str | None = None) -> str | None:
        """Convert Markdown to PDF via pandoc (if available)."""
        if pdf_path is None:
            pdf_path = md_path.replace(".md", ".pdf")
        try:
            subprocess.run(
                ["pandoc", md_path, "-o", pdf_path, "--pdf-engine=xelatex"],
                check=True,
                capture_output=True,
            )
            log.info("PDF generated: %s", pdf_path)
            return pdf_path
        except FileNotFoundError:
            log.warning("pandoc not found — skipping PDF generation.")
            return None
        except subprocess.CalledProcessError as e:
            log.warning("pandoc failed: %s", e.stderr.decode())
            return None
