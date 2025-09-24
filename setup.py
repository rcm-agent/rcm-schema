from setuptools import setup, find_packages

setup(
    name="rcm-schema",
    version="0.1.0",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "sqlalchemy>=2.0.0",
        "pydantic>=2.0.0",
    ],
    description="RCM Schema - Shared database models for RCM services",
    author="RCM Team",
)