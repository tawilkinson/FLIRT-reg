from setuptools import setup

setup(
    name="flirt_reg",
    packages=[
        "flirt_reg",
        "flirt_reg.reg",
        "flirt_reg.utils",
        "gpuoptional",
    ],
    version="0.9.1",
    description="A python wrapper for FLIRT MRI registration",
    author="Dr Tom Wilkinson",
    author_email="tom@tawilkinson.com",
    url="https://github.com/tawilkinson/FLIRT-reg",
    download_url="",
    keywords=["MRI", "FLS", "FLIRT", "registration", "imaging"],
    classifiers=[],
    install_requires=["numpy", "scipy", "nipype"],
    entry_points={
        "console_scripts": [
            "flirt-reg = flirt_reg.__main__:main",
            "flirt-apply = flirt_reg.reg.flirt_reg:apply_transform_cmd",
        ]
    },
    extras_require={
        "gpu": ["cupy-cuda114"],
    },
)
