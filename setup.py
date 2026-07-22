from setuptools import setup, find_packages

setup(
    name="user-station",
    version="0.3",
    description="GTK user and group manager for GhostBSD and FreeBSD",
    license="BSD-2-Clause",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "user-station=user_station.main:main",
        ]
    },
    data_files=[
        ("share/applications", ["user-station.desktop"]),
        ("share/icons/hicolor/scalable/apps",
         ["user_station/resources/icons/user-station.svg"]),
    ],
)
