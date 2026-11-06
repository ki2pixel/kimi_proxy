"""Setup script pour Kimi Proxy Middleware MCP."""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="kimi-proxy-mcp",
    version="2.0.0",
    author="Kimi Proxy Team",
    description="Middleware MCP session-less avec streaming SSE",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Tools",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=[
        "fastapi>=0.100.0",
        "uvicorn>=0.23.0",
        "watchfiles>=0.20.0",
        "pydantic>=2.0.0",
        "httpx>=0.24.0",
        "tiktoken>=0.5.0",
        "aiofiles>=23.0.0",
        'tomli>=2.0.0; python_version<"3.11"',
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "ruff>=0.1.0",
            "mypy>=1.5.0",
            "bandit>=1.7.5",
        ],
    },
    entry_points={
        "console_scripts": [
            "kimi-proxy=kimi_proxy.__main__:main",
        ],
    },
)
