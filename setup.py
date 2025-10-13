from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="mcp-ssh-server",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="MCP Server for remote SSH management of Linux servers",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/mcp-ssh",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=[
        "fastapi>=0.109.0",
        "uvicorn[standard]>=0.27.0",
        "pydantic>=2.5.0",
        "pydantic-settings>=2.1.0",
        "starlette>=0.35.0",
        "paramiko>=3.4.0",
        "asyncssh>=2.14.0",
        "typer>=0.9.0",
        "rich>=13.7.0",
        "questionary>=2.0.0",
        "cryptography>=41.0.0",
        "python-jose[cryptography]>=3.3.0",
        "python-dotenv>=1.0.0",
        "sse-starlette>=1.8.2",
    ],
    entry_points={
        "console_scripts": [
            "mcp-ssh=src.cli:app",
        ],
    },
)

