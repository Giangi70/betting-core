from setuptools import setup, find_packages

setup(
    name="betting-core",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "pandas",
        "numpy",
        "xgboost",
        "scikit-learn",
        "joblib",
        "python-dotenv",
        "requests",
        "fastapi>=0.110",
        "uvicorn[standard]>=0.29",
    ],
)
