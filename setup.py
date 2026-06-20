"""GovernorNode — and GovernorStateGraph for LangGraph.

Drop-in governance wrappers for LangGraph agents:
- Iteration limits to prevent runaway loops
- Oscillation detection (repeated identical outputs)
- Flight data recorder for full audit trails (JSON export)
- Plan entropy monitoring (Shannon entropy over output diversity)
- YAML-driven policy configuration
"""

from setuptools import setup, find_packages

setup(
    name="governornode",
    version="1.0.0",
    description="LangGraph governance wrapper — iteration limits, oscillation detection, flight recorder",
    long_description=__doc__,
    packages=find_packages(),
    install_requires=[
        "langgraph>=1.0.0",
    ],
    extras_require={
        "yaml": ["pyyaml>=6.0"],
        "dev": ["pytest>=8.0", "pyyaml>=6.0"],
    },
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
)
