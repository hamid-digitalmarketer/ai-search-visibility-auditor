"""Minimal packaging for the AI Search Visibility Auditor."""

from setuptools import find_packages, setup

setup(
    name="ai-search-visibility-auditor",
    version="0.1.0",
    packages=find_packages(exclude=["tests", "tests.*"]),
    python_requires=">=3.9",
    install_requires=["streamlit>=1.30"],
    description="Open-source GEO toolkit: audit AI crawler access, llms.txt and AI-citation readiness of any website.",
    license="MIT",
)
