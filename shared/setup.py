from setuptools import setup, find_packages

setup(
    name="saiga_shared",
    version="0.1.0",
    description="Shared SQLAlchemy models for saiga web and bot",
    packages=find_packages(),
    install_requires=[
        "SQLAlchemy>=2.0,<3.0",
    ],
    python_requires=">=3.10",
)
