"""TiTiler-Image FastAPI application."""
import warnings

from fastapi import FastAPI, Query
from fastapi.exceptions import RequestValidationError
from rasterio.errors import NotGeoreferencedWarning, RasterioIOError
from starlette import status
from starlette.middleware.cors import CORSMiddleware
from starlette_cramjam.middleware import CompressionMiddleware

from titiler.core.errors import DEFAULT_STATUS_CODES, add_exception_handlers
from titiler.core.middleware import CacheControlMiddleware
from titiler.core.factory import TilerFactory
from titiler.image import __version__ as titiler_image_version
from titiler.image.factory import (
    IIIFFactory,
    LocalTilerFactory,
    MetadataFactory,
)
from titiler.image.settings import api_settings
from titiler.image.dependencies import GCPSParams
from titiler.image.reader import Reader
from pyproj import Transformer
from rasterio.control import GroundControlPoint
from typing import Annotated

app = FastAPI(
    title=api_settings.name,
    openapi_url="/api",
    docs_url="/api.html",
    description="""titiler application to work with non-geo images.

---

**Source Code**: <a href="https://github.com/developmentseed/titiler-image" target="_blank">https://github.com/developmentseed/titiler-image</a>

---
    """,
    version=titiler_image_version,
    root_path=api_settings.root_path,
)

warnings.filterwarnings("ignore", category=NotGeoreferencedWarning)

DEFAULT_STATUS_CODES.update(
    {
        RasterioIOError: status.HTTP_404_NOT_FOUND,
        RequestValidationError: status.HTTP_400_BAD_REQUEST,
    }
)

add_exception_handlers(app, DEFAULT_STATUS_CODES)

# Set all CORS enabled origins
if api_settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=api_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

app.add_middleware(
    CompressionMiddleware,
    minimum_size=0,
    exclude_mediatype={
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/jp2",
        "image/webp",
    },
)

app.add_middleware(
    CacheControlMiddleware,
    cachecontrol=api_settings.cachecontrol,
    exclude_path={r"/healthz"},
)

meta = MetadataFactory()
app.include_router(meta.router, tags=["Metadata"])

iiif = IIIFFactory(router_prefix="/iiif")
app.include_router(iiif.router, tags=["IIIF"], prefix="/iiif")

image_tiles = LocalTilerFactory(router_prefix="/image")
app.include_router(image_tiles.router, tags=["Local Tiles"], prefix="/image")

geo_tiles = TilerFactory(
    reader=Reader,
    reader_dependency=GCPSParams,
    router_prefix="/geo"
)
app.include_router(geo_tiles.router, tags=["Geo Tiles"], prefix="/geo")

def parse_gcps(gcps: str) -> list[GroundControlPoint]:
    gcps: list[GroundControlPoint] = [
                GroundControlPoint(*list(map(float, gcps.split(","))))
                for gcps in gcps
            ]

@app.get("/latlng_to_pixel")
def latlng_to_pixel(url: str, latitude: float, longitude: float, gcps: Annotated[list[str], 
    Query(title="Ground Control Points", description="Ground Control Points in form of `row (y), col (x), lon, lat, alt`")]):
    gcpList = parse_gcps(gcps)
    with Reader(url, gcps=gcpList) as reader:
        dataset = reader.dataset
        transformer = Transformer.from_crs("EPSG:4326", dataset.crs.to_string())
        latM, lngM = transformer.transform(latitude, longitude)
        py, px = dataset.index(latM, lngM)
        return {"x": px, "y": py}
    
@app.get("/pixel_to_latlng")
def pixel_to_latlng(url: str, x: float, y: float, gcps: Annotated[list[str], 
    Query(title="Ground Control Points", description="Ground Control Points in form of `row (y), col (x), lon, lat, alt`")]):
    gcpList = parse_gcps(gcps)
    with Reader(url, gcps=gcpList) as reader:
        dataset = reader.dataset
        transformer = Transformer.from_crs(dataset.crs.to_string(), "EPSG:4326")
        lat, lng = dataset.xy(y, x)
        latitude, longitude = transformer.transform(lat, lng)
        return {"latitude": latitude, "longitude": longitude}

###############################################################################
# Health Check Endpoint
@app.get(
    "/healthz",
    description="Health Check.",
    summary="Health Check.",
    operation_id="healthCheck",
    tags=["Health Check"],
)
def ping():
    """Health check."""
    return {"ping": "pong!"}
