"""cli-anything-go-music-dl

Aggregated music search & download CLI for go-music-dl.
"""

from pathlib import Path

from setuptools import setup, find_namespace_packages

BASE_DIR = Path(__file__).parent
long_description = (BASE_DIR / "cli_anything" / "go_music_dl" / "README.md").read_text(
    encoding="utf-8"
)

setup(
    name="cli-anything-go-music-dl",
    version="1.0.0",
    description="AI-agent-friendly CLI for go-music-dl — aggregated music search & download",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/guohuiyuan/go-music-dl",
    author="go-music-dl contributors",
    license="MIT",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    include_package_data=True,
    package_data={
        "cli_anything.go_music_dl": ["skills/*.md"],
    },
    python_requires=">=3.10",
    install_requires=[
        "click>=8.0",
        "requests>=2.28",
    ],
    extras_require={
        "repl": ["prompt-toolkit>=3.0"],
        "parsing": ["beautifulsoup4>=4.11"],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-go-music-dl=cli_anything.go_music_dl.go_music_dl_cli:cli",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Topic :: Multimedia :: Sound/Audio",
    ],
)
