"""
Setup script pour Kimi Proxy Dashboard.
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="kimi-proxy-dashboard",
    version="2.0.0",
    author="Kimi Proxy Team",
    description="Proxy transparent avec monitoring temps réel de tokens LLM",
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
        "uvicorn[standard]>=0.23.0",
        "httpx>=0.24.0",
        "websockets>=11.0",
        "tiktoken>=0.5.0",
        "aiofiles>=23.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "ruff>=0.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "kimi-proxy=kimi_proxy.__main__:main",
        ],
    },
)
