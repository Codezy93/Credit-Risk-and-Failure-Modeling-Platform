"""Check the Pages artifact's local links, markup basics and publication boundary."""

from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.references, self.headings = set(), [], 0
        self.has_language, self.has_viewport = False, False

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if "id" in attrs:
            assert attrs["id"] not in self.ids, f"Duplicate ID: {attrs['id']}"
            self.ids.add(attrs["id"])
        if tag == "html":
            self.has_language = bool(attrs.get("lang"))
        if tag == "meta" and attrs.get("name") == "viewport":
            self.has_viewport = True
        if tag == "h1":
            self.headings += 1
        if tag == "img":
            assert "alt" in attrs, "Images need an alt attribute."
        for key in ["href", "src", "data-figure"]:
            if key in attrs:
                self.references.append(attrs[key])


def main():
    directory = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "_site"
    expected = {"index.html", "styles.css", "app.js", ".nojekyll", "assets/results.json",
        "assets/provenance.json", "assets/eda.png", "assets/interpret.png", "assets/recovery.png",
        "assets/raw-missingness.png", "assets/status-coverage.png", "assets/tail-review.png",
        "assets/category-outcomes.png", "assets/numeric-outcomes.png", "assets/correlations.png",
        "assets/fico-dti.png", "assets/cohort-coverage.png", "assets/calibration.png", "assets/ann.png",
        "assets/loss.png", "assets/partial-dependence.png", "assets/segments.png", "assets/load.png"}
    actual = {str(path.relative_to(directory)) for path in directory.rglob("*") if path.is_file()}
    assert actual == expected, f"Unexpected or missing publishable files: {actual ^ expected}"
    assert not any(path.is_symlink() for path in directory.rglob("*")), "Pages artifact must not contain symlinks."
    document = (directory / "index.html").read_text()
    assert "{{" not in document and "localhost" not in document
    assert 'rel="icon"' not in document and 'notebook-brand' not in document
    stylesheet = (directory / "styles.css").read_text()
    assert "--mono: Menlo," in stylesheet and "--body: 'Helvetica Neue'," in stylesheet
    for color in re.findall(r"#[0-9a-fA-F]{8}\b|#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b", stylesheet):
        value = color[1:]
        if len(value) == 3:
            value = "".join(character * 2 for character in value)
        assert value[:2] == value[2:4] == value[4:6], f"Non-monochrome CSS color: {color}"
    assert "grayscale(" not in stylesheet, "Preserve recorded figures in their original colors."
    parser = Page();parser.feed(document)
    assert parser.headings == 1 and parser.has_language and parser.has_viewport
    chapters = {"question", "download", "audit", "clean", "univariate", "relationships", "population",
        "experiments", "validation", "challengers", "loss", "interpretation", "streaming", "load",
        "recovery", "monitoring", "reproduce", "conclusions"}
    assert chapters <= parser.ids, "Every end-to-end notebook chapter must be present."
    for reference in parser.references:
        link = urlsplit(reference)
        if link.scheme or link.netloc:
            assert link.scheme == "https", reference
            continue
        assert not link.path.startswith("/"), f"Use relative project Pages URLs: {reference}"
        if link.path:
            target = directory / unquote(link.path)
            assert target.is_file() and target.resolve().is_relative_to(directory.resolve()), reference
        if link.fragment and not link.path:
            assert link.fragment in parser.ids, reference
    def invalid(value):
        raise ValueError(f"Nonfinite JSON value: {value}")
    results = json.loads((directory / "assets/results.json").read_text(), parse_constant=invalid)
    assert results["recovery"]["missing_main_scores"] == 0
    assert results["recovery"]["elk_verified"] is True
    for cohort in results["cohorts"].values():
        assert 0 <= cohort["auc"] <= 1 and cohort["rows"] > 0
        assert len(cohort["curve"]) > 2
    size = sum(path.stat().st_size for path in directory.rglob("*") if path.is_file())
    print(f"Site checks passed: {len(actual)} public files, {len(parser.references)} links/assets, {size / 1024:.0f} KiB.")


if __name__ == "__main__":
    main()
