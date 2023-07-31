"""test titiler.image custom Reader."""

import json
import os
from typing import List

import rasterio
from rasterio.control import GroundControlPoint

from titiler.image.reader import Reader

PREFIX = os.path.join(os.path.dirname(__file__), "fixtures")

boston_jpeg = os.path.join(PREFIX, "boston.jpg")
boston_png = os.path.join(PREFIX, "boston.png")
boston_tif = os.path.join(PREFIX, "boston.tif")
boston_geojson = os.path.join(PREFIX, "boston.geojson")
cog_geojson = os.path.join(PREFIX, "cog_no_gcps.geojson")
cog_no_gcps = os.path.join(PREFIX, "cog_no_gcps.tif")
cog_gcps = os.path.join(PREFIX, "cog_gcps.tif")


def get_gcps(path: str) -> List[GroundControlPoint]:
    """read GCPS geojson."""
    with open(path, "r") as f:
        geojson = json.loads(f.read())
        return [
            # GroundControlPoint(row, col, x, y, z)
            # https://github.com/allmaps/iiif-api/blob/georef/source/extension/georef/index.md#35-the-resourcecoords-property
            GroundControlPoint(
                f["properties"]["resourceCoords"][1],  # row = y
                f["properties"]["resourceCoords"][0],  # col = x
                *f["geometry"]["coordinates"],  # lon, lat, z
            )
            for f in geojson["features"]
        ]


def test_reader_gcps():
    """Make sure that Reader can use COG with internal GCPS (as rio_tiler.io.Reader)."""
    with rasterio.open(cog_gcps) as dst:
        with Reader(cog_gcps) as src:
            assert dst.meta != src.dataset.meta
            assert src.crs == "epsg:4326"

            info = src.info()
            assert info.nodata_type == "Alpha"
            assert len(info.band_metadata) == 2
            assert info.band_descriptions == [("b1", ""), ("b2", "")]
            assert info.colorinterp == ["gray", "alpha"]
            assert info.count == 2
            assert info.width == 1417
            assert info.height == 1071

            # The topleft corner should be masked
            assert src.preview(indexes=1).array.mask[0, 0, 0]


def test_reader_external_gcps():
    """Make sure that Reader can use COG with external GCPS."""
    with rasterio.open(cog_gcps) as dst:
        with Reader(cog_no_gcps, gcps=get_gcps(cog_geojson)) as src:
            assert dst.meta != src.dataset.meta
            assert src.crs == "epsg:4326"
            info = src.info()
            assert info.nodata_type == "Alpha"
            assert len(info.band_metadata) == 2
            assert info.band_descriptions == [("b1", ""), ("b2", "")]
            assert info.colorinterp == ["gray", "alpha"]
            assert info.count == 2
            assert info.width == 1417
            assert info.height == 1071

            # The topleft corner should be masked
            assert src.preview(indexes=1).array.mask[0, 0, 0]