from pathlib import Path


def test_streamlit_embedding_dependencies_include_torchvision():
    """Keep Streamlit's transformers module inspection from breaking retrieval."""
    requirements = Path("requirements.txt").read_text(encoding="utf-8").splitlines()
    packages = {
        line.split("#", 1)[0].strip().split("@", 1)[0].split("=", 1)[0].split(">", 1)[0].lower()
        for line in requirements
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert {"torch", "torchvision"} <= packages
