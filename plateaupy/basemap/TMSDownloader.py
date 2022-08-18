import os
import sys
import time

from enum import Enum
from typing import Tuple
from urllib import request
import math

import numpy as np
import cv2


class TMSDownloader:
    """TMSDownloader"""

    tile_size = 256

    class TMS(Enum):
        """Tile Map Service List

        Args:
            Enum (str): Tile Map Service ID
        """

        GoogleMaps = "google"
        OpenStreetMap = "osm"
        CyberJapan = "cyberjapan"

    class LayerType(Enum):
        """TMS Layer Type List"""

        ROADMAP = "roadmap"
        SATELLITE = "satellite"
        HYBRID = "hybrid"

    Services = {
        TMS.GoogleMaps: {
            "url": "http://mt{s}.google.com/vt/lyrs={layer}&x={x}&y={y}&z={z}",
            "attribution": "© Google",
            "description": "Google Maps",
            "max_zoom": 20,
            "subdomains": ["0", "1", "2", "3"],
            "layers": {
                "roadmap": {"layer": "m", "ext": "jpg"},
                "satellite": {"layer": "s", "ext": "jpg"},
                "hybrid": {"layer": "y", "ext": "jpg"},
            },
        },
        TMS.OpenStreetMap: {
            "url": "http://{s}.tile.openstreetmap.org/{z}/{x}/{y}.{ext}",
            "attribution": "© OpenStreetMap contributors",
            "description": "Open Street Map",
            "max_zoom": 19,
            "subdomains": ["a", "b", "c"],
            "layers": {
                "roadmap": {"layer": "", "ext": "png"},
                "satellite": {"layer": "", "ext": "png"},
                "hybrid": {"layer": "", "ext": "png"},
            },
        },
        TMS.CyberJapan: {
            "url": "https://cyberjapandata.gsi.go.jp/xyz/{layer}/{z}/{x}/{y}.{ext}",
            "attribution": "Geospatial Information Authority of Japan",
            "description": "国土交通省 国土地理院 (Japan area only)",
            "max_zoom": 18,
            "subdomains": [],
            "layers": {
                "roadmap": {"layer": "std", "ext": "png"},
                "satellite": {"layer": "seamlessphoto", "ext": "jpg"},
                "hybrid": {"layer": "", "ext": "jpg"},
            },
        },
    }

    class GeoCoordinate:
        """GeoCoordinate"""

        def __init__(self, lat: float, lng: float):
            self.lat = lat
            self.lng = lng

        def __str__(self) -> str:
            return f"(lat: {self.lat}, lng: {self.lng})"

        def __repr__(self) -> str:
            return self.__str__()

        def __add__(self, other):
            return TMSDownloader.GeoCoordinate(
                self.lat + other.lat, self.lng + other.lng
            )

        def __sub__(self, other):
            return TMSDownloader.GeoCoordinate(
                self.lat - other.lat, self.lng - other.lng
            )

    @classmethod
    def getBBox(self, a, b):
        """Get bounding box from two geo coordinates

        Args:
            a (GeoCoordinate): 1st GeoCoordinate
            b (GeoCoordinate): 2nd GeoCoordinate

        Returns:
            Tuple[GeoCoordinate. GeoCoordinate]: _description_
        """
        return (
            TMSDownloader.GeoCoordinate(max(a.lat, b.lat), min(a.lng, b.lng)),
            TMSDownloader.GeoCoordinate(min(a.lat, b.lat), max(a.lng, b.lng)),
        )

    @classmethod
    def getXY(self, loc: GeoCoordinate, zoom: int) -> Tuple[int, int]:
        """Get tile coordinate(col, row) from geo coordinate and zoom level

        Args:
            loc (GeoCoordinate): _description_
            zoom (int): zoom level

        Returns:
            Tuple[int, int]: _description_
        """

        # get tile num
        numTiles = 1 << zoom

        col = math.floor((loc.lng + 180.0) / 360.0 * numTiles)
        rad_lat = math.radians(loc.lat)
        row = math.floor(
            (1.0 - math.log(math.tan(rad_lat) + 1.0 / math.cos(rad_lat)) / math.pi)
            / 2.0
            * numTiles
        )

        return int(row), int(col)

    @classmethod
    def getLatLng(self, row: int, col: int, zoom: int) -> Tuple[float, float]:
        """Get geo coordinate from tile coordinate and zoom level

        Args:
            row (int): row
            col (int): col
            zoom (int): zoom level

        Returns:
            Tuple[float, float]: _description_
        """

        # get tile num
        numTiles = 1 << zoom

        lng = col / numTiles * 360.0 - 180.0
        lat = math.atan(math.sinh(math.pi * (1 - 2 * row / numTiles)))
        lat = math.degrees(lat)

        return lat, lng

    @classmethod
    def urlBuilder(
        self, service: TMS, layer: LayerType, row: int, col: int, zoom: int
    ) -> str:
        """Build URL from service, layer, col, row, zoom

        Args:
            service (TMS): TMS service
            layer (LayerType): TMS layer type
            col (int): col
            row (int): row
            zoom (int): zoom level

        Returns:
            str: tile download URL
        """

        subdomain_num = len(service["subdomains"])
        if subdomain_num <= 0:
            subdomain = ""
        else:
            # choose random subdomain
            idx = np.random.randint(0, subdomain_num)
            subdomain = service["subdomains"][idx]

        # build url
        url = (
            service["url"]
            .replace("{s}", subdomain)
            .replace("{layer}", service["layers"][layer.value]["layer"])
            .replace("{ext}", service["layers"][layer.value]["ext"])
            .replace("{x}", str(col))
            .replace("{y}", str(row))
            .replace("{z}", str(zoom))
        )

        return url

    def downloadTile(url: str) -> bytes:
        """Download tile from URL

        Args:
            url (str): download tile URL

        Returns:
            bytes: downloaded data
        """
        headers = {
            "Accept": "image/png,image/*;q=0.8,*/*;q=0.5",
            "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.7",
            "Accept-Language": "fr,en-us,en;q=0.5",
            "Proxy-Connection": "keep-alive",
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:45.0) Gecko/20100101 Firefox/45.0",
        }

        buff = None
        # download request
        req = request.Request(url, headers=headers)
        with request.urlopen(req) as res:
            buff = res.read()

        return buff

    @classmethod
    def generateImage(
        self,
        startLoc: GeoCoordinate,
        endLoc: GeoCoordinate,
        zoom: int = 12,
        tms: TMS = TMS.GoogleMaps,
        layer: LayerType = LayerType.SATELLITE,
        cache_dir: str = "cached/tiles/",
        no_cache: bool = False,
        isCrop: bool = False,
        draw_grid: bool = False,
    ) -> np.array:
        """Generate map image from two geo coordinates and zoom level
            fetch tiles from tile map service and stitch them together.
            fetched tiles are cached in cache_dir.
            if no_cache is "True", cached tiles are not used. (default: False)

        Args:
            startLoc (GeoCoordinate): Left-Top geo coordinate
            endLoc (GeoCoordinate): Right-Bottom geo coordinate
            zoom (int, optional): zoom level. Defaults to 12.
            tms (TMS, optional): Tile Map Service ID. Defaults to TMS.GoogleMaps.
            layer (LayerType, optional): Layer Type. Defaults to LayerType.SATELLITE.
            cache_dir (str, optional): cache dir path. Defaults to "cached/tiles/".
            no_cache (bool, optional): not use cache. Defaults to False.
            isCrop (bool, optional): crop image Left-Top to Right-Bottom. Defaults to False.
            draw_grid (bool, optional): draw grid each tile. Defaults to False.

        Returns:
            np.array: Map image (opencv format)
        """

        # get TM service info
        service = self.Services[tms]

        # zoom level
        zoom = int(zoom)
        if service["max_zoom"] < zoom:
            zoom = service["max_zoom"]

        # check cache directory
        tiles_cache_dir = os.path.join(cache_dir, tms.value)
        if not os.path.exists(tiles_cache_dir):
            os.makedirs(tiles_cache_dir)

        lt, rb = self.getBBox(startLoc, endLoc)

        # Get the x,y coordinates of the start and end locations
        start_row, start_col = self.getXY(lt, zoom)
        end_row, end_col = self.getXY(rb, zoom)

        # Swap variables if start_xxx is greater than end_xxx
        if start_col > end_col:
            start_col, end_col = end_col, start_col
        if start_row > end_row:
            start_row, end_row = end_row, start_row

        # calculate the number of tiles required to cover the area
        tile_col_num = end_col - start_col + 1
        tile_row_num = end_row - start_row + 1

        # Determine the size of the image
        width, height = self.tile_size * tile_col_num, self.tile_size * tile_row_num

        # Create empty image
        imgMap = np.zeros((height, width, 3), dtype=np.uint8)

        bbox = (
            TMSDownloader.GeoCoordinate(*self.getLatLng(start_row, start_col, zoom)),
            TMSDownloader.GeoCoordinate(
                *self.getLatLng(end_row + 1, end_col + 1, zoom)
            ),
        )
        print(f"StartLoc: {lt} -> {bbox[0]}")
        print(f"EndLoc: {rb} -> {bbox[1]}")
        print(f"Col: {start_col} - {end_col}")
        print(f"Row: {start_row} - {end_row}")
        print(f"Zoom: {zoom}")
        print(f"Tiles: {tile_col_num} x {tile_row_num}")

        # calc pixel per degree
        diffLoc = bbox[0] - bbox[1]
        dx = width / abs(diffLoc.lng)
        dy = height / abs(diffLoc.lat)
        # print(f"dx: {dx} dy: {dy}")

        startDiff = lt - bbox[0]
        endDiff = bbox[1] - rb
        # print(f"{dx * startDiff.lat}, {dy * startDiff.lng}")
        # print(f"{dx * endDiff.lat}, {dy * endDiff.lng}")

        # get tile images
        for x in range(0, tile_col_num):
            for y in range(0, tile_row_num):
                col = x + start_col
                row = y + start_row

                url = self.urlBuilder(service, layer, row, col, zoom)

                filename = f"{zoom}_{col}_{row}_{layer.value}.jpg"
                filename = os.path.join(tiles_cache_dir, filename)

                # check cache
                if no_cache or not os.path.exists(filename):
                    # request download tile
                    print(
                        f"-- fetch ({(x * tile_row_num) + y + 1} / {tile_col_num * tile_row_num})",
                        url,
                        "to",
                        filename,
                    )

                    # download tile
                    buff = None
                    try:
                        buff = self.downloadTile(url)
                    except Exception as e:
                        print("--", url, "to", filename, "->", e)
                        continue

                    # save image cache
                    isCached = False
                    if buff is not None:
                        with open(filename, "wb") as f:
                            f.write(buff)
                        isCached = True

                    # wait a seconds
                    time.sleep(0.1 + np.random.random())
                else:
                    isCached = True
                    print("-- cached", filename)

                try:
                    if isCached:
                        # read image
                        imgTile = cv2.imread(filename)

                        # draw grid
                        if draw_grid:
                            imgTile = cv2.rectangle(
                                imgTile,
                                (y, x),
                                (y + self.tile_size, x + self.tile_size),
                                (0, 255, 0),
                                2,
                            )

                        # merge image
                        merge_pos_x = x * self.tile_size
                        merge_pos_y = y * self.tile_size
                        imgMap[
                            merge_pos_y : merge_pos_y + imgTile.shape[0],
                            merge_pos_x : merge_pos_x + imgTile.shape[1],
                        ] = imgTile

                        del imgTile

                except Exception as e:
                    print(f"-- {e}, error {filename}")
                    continue

        if isCrop:
            # cv2.imwrite("map_.jpg", imgMap)
            crop_lt = (int(abs(dy * startDiff.lat)), int(abs(dx * startDiff.lng)))
            crop_rb = (int(abs(dy * endDiff.lat)), int(abs(dx * endDiff.lng)))
            imgMap = imgMap[
                crop_lt[0] : height - crop_rb[0], crop_lt[1] : width - crop_rb[1]
            ]

        return imgMap


if __name__ == "__main__":

    # Kyocera Dome (Osaka)
    startLoc = TMSDownloader.GeoCoordinate(34.67042882707316, 135.47453288400564)
    endLoc = TMSDownloader.GeoCoordinate(34.668376317727486, 135.47727372077304)

    # Tokyo Station (Tokyo)
    # startLoc = TMSDownloader.GeoCoordinate(35.68479157138042, 139.76548660257424)
    # endLoc = TMSDownloader.GeoCoordinate(35.67621276216543, 139.76971984744708)

    # # Tokyo Tower (Tokyo)
    # startLoc = TMSDownloader.GeoCoordinate(35.65940142544001, 139.7448018174573)
    # endLoc = TMSDownloader.GeoCoordinate(35.65790616603373, 139.74631070466197)

    # # Pytamid of Khufu, Khafre, Menkaure (Egypt)
    # startLoc = TMSDownloader.GeoCoordinate(29.980261596963285, 31.13549049951689)
    # endLoc = TMSDownloader.GeoCoordinate(29.971980323262382, 31.12772144285645)

    # # Machu Picchu (Peru)
    # startLoc = TMSDownloader.GeoCoordinate(-13.165265274078298, -72.54318216995344)
    # endLoc = TMSDownloader.GeoCoordinate(-13.161587153669503, -72.54684881896942)

    # # Sydney Opera House (Sydney)
    # startLoc = TMSDownloader.GeoCoordinate(-33.85832511064872, 151.21607681124982)
    # endLoc = TMSDownloader.GeoCoordinate(-33.855937226068875, 151.21433543812492)

    try:
        img = TMSDownloader.generateImage(
            startLoc=startLoc,
            endLoc=endLoc,
            zoom=15,
            tms=TMSDownloader.TMS.GoogleMaps,
            layer=TMSDownloader.LayerType.SATELLITE,
            cache_dir="./cached/tiles",
            no_cache=False,
            isCrop=True,
        )
    except Exception as e:
        print(e)
        sys.exit(1)
    else:
        # Save the image
        cv2.imwrite("map.jpg", img)
        print("Output image -> 'map.jpg'")
