import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parsers.common import normalize_url


def test_rna_reportage_url_normalization() -> None:
    assert normalize_url("https://reportage.ly/", "ly.reportage://https", "rna_reportage") == "https://reportage.ly/"
    assert normalize_url("https://reportage.ly/news/", "/example-story/", "rna_reportage") == "https://reportage.ly/example-story/"


if __name__ == "__main__":
    test_rna_reportage_url_normalization()
    print("URL normalization tests passed")
