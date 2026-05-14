from __future__ import annotations
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markdown_it import MarkdownIt


THEME_HEADING_MAP = {
    "obesity": "theme-obesity",
    "metabolic": "theme-obesity",
    "longevity": "theme-longevity",
    "strength": "theme-strength",
    "hypertrophy": "theme-strength",
    "supplement": "theme-supplements",
    "sleep": "theme-sleep",
    "recovery": "theme-sleep",
    "skin": "theme-skin-hair",
    "hair": "theme-skin-hair",
}


def _apply_theme_classes(html: str) -> str:
    """Add theme-* class to <h2> elements based on heading text."""
    def repl(match: re.Match) -> str:
        text = match.group(1).lower()
        for kw, cls in THEME_HEADING_MAP.items():
            if kw in text:
                return f'<h2 class="{cls}">{match.group(1)}</h2>'
        return match.group(0)
    return re.sub(r"<h2>(.*?)</h2>", repl, html, flags=re.DOTALL)


def _strip_frontmatter(md: str) -> tuple[str, str]:
    """Strip YAML front matter, return (frontmatter_text, body_md)."""
    if md.startswith("---"):
        end = md.find("\n---", 3)
        if end != -1:
            return md[3:end].strip(), md[end + 4:].lstrip()
    return "", md


def _md_to_html(md: str) -> str:
    parser = MarkdownIt("commonmark", {"html": False, "linkify": True})
    return parser.render(md)


def _load_template(brand_dir: Path, template_name: str):
    env = Environment(
        loader=FileSystemLoader(brand_dir),
        autoescape=select_autoescape(default=False),
    )
    return env.get_template(template_name)


def render_digest(
    digest_md: str,
    brand_dir: Path,
    out_path: Path,
    run_date_str: str,
) -> None:
    _frontmatter, body_md = _strip_frontmatter(digest_md)
    content_html = _md_to_html(body_md)
    content_html = _apply_theme_classes(content_html)

    tokens_css = (brand_dir / "tokens.css").read_text(encoding="utf-8")
    template = _load_template(brand_dir, "template_digest.html")
    html = template.render(
        date=run_date_str,
        content_html=content_html,
        tokens_css=tokens_css,
    )
    out_path.write_text(html, encoding="utf-8")


def render_angles(
    angles_md: str,
    brand_dir: Path,
    out_path: Path,
    run_date_str: str,
) -> None:
    _frontmatter, body_md = _strip_frontmatter(angles_md)
    content_html = _md_to_html(body_md)
    tokens_css = (brand_dir / "tokens.css").read_text(encoding="utf-8")
    template = _load_template(brand_dir, "template_angles.html")
    html = template.render(
        date=run_date_str,
        content_html=content_html,
        tokens_css=tokens_css,
    )
    out_path.write_text(html, encoding="utf-8")


def render_email_body(
    digest_md: str,
    brand_dir: Path,
    out_path: Path,
    run_date_str: str,
    digest_url: str,
    subject: str,
) -> None:
    """Render an email-safe HTML body with inlined CSS (via premailer)."""
    from premailer import transform

    # Extract just TL;DR for the email summary
    _frontmatter, body_md = _strip_frontmatter(digest_md)
    summary_match = re.search(r"##\s*TL;DR.*?(?=\n##\s)", body_md, re.DOTALL)
    summary_md = summary_match.group(0) if summary_match else body_md[:1000]
    summary_html = _md_to_html(summary_md)

    tokens_css = (brand_dir / "tokens.css").read_text(encoding="utf-8")
    template = _load_template(brand_dir, "template_email.html")
    raw_html = template.render(
        subject=subject,
        summary_html=summary_html,
        digest_url=digest_url,
        date=run_date_str,
        tokens_css=tokens_css,
    )

    inlined = transform(raw_html, base_url=None)
    out_path.write_text(inlined, encoding="utf-8")
