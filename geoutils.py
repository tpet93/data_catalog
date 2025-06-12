# Geospatial Utilities (GDAL et al).
import sys
import os
import json
from osgeo import gdal
from osgeo import osr
import platform
import subprocess
from utils import dumps, posixpath
import datetime

import pyproj

from typing import Any, Dict, Union
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Sequence, Union

from laspy.point.format import PointFormat as _LasPointFormat  # type: ignore
from crs_fix import crs_from_ascii_strings  # type: ignore

# Import laspy for LAS/LAZ file handling
try:
    import laspy
    import numpy as np
    HAS_LASPY = True
except ImportError:
    HAS_LASPY = False
    print("Warning: laspy not installed. LAS/LAZ file processing will not be available.", file=sys.stderr)


# def build_bbox(xs, ys):
#     """Builds BBox from xs and ys (or lons and lats) lists."""
#     min_x = min(xs)
#     max_x = max(xs)
#     min_y = min(ys)
#     max_y = max(ys)
#     bbox = {
#         'type': 'Polygon',
#         'coordinates': [
#             [
#                 [min_x, min_y],
#                 [min_x, max_y],
#                 [max_x, max_y],
#                 [max_x, min_y],
#                 [min_x, min_y]
#             ]
#         ]
#     }
#     return bbox


def gdal_info(filepath):
    """Returns Gdalinfo as compact JSON."""
    # Equivalent to: 
    #   'gdalinfo -json -proj4 '{dirpath}\\{filename}' | jq -c .'.
    if platform.system() == 'Windows':
        return _gdal_info_subprocess(filepath)
    elif platform.system() == 'Linux':
        return _gdal_info_native(filepath)
    raise NotImplementedError('Running on an unknown OS!')

def _gdal_info_native(filepath):
    """Returns Gdalinfo via native wrappers.
       Native (python API bindings over native) 
       skips case-sensitive '22633_TRING_1_4band' after '22633_TRING_1_4Band'."""
    try:
        gdal.UseExceptions() # default versus # gdal.DontUseExceptions()
        dataset = gdal.Open(filepath)
        return gdal.Info(dataset, options=gdal.InfoOptions(
            format='json',
            options=[
            ])
        )
    except Exception as ex:
        msg = f'gdal_info_native: failed on {filepath}: {str(ex)}.'
        print(msg, file=sys.stderr)
    return None

def _gdal_info_subprocess(filepath):
    """Returns Gdalinfo via subprocess.
       Subprocess (exe or binary) picks up 
       case-sensitive '22633_TRING_1_4band' after '22633_TRING_1_4Band'."""
    try:
        result = subprocess.run(
            [
                'gdalinfo',
                '-json',
                filepath,
            ],
            capture_output=True,
            check=True,
            text=True,
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as ex:
        msg = f'gdal_info_subprocess: failed on {filepath}: {ex.stderr}.'
        print(msg, file=sys.stderr)
    return None



def gdal_transform_rpc(filepath, epsg, coords):
    """Returns Gdaltransform with -rpc to transform a list of (x, y, z) coordinates.
        Args:
            dirpath (str): Directory path to the image.
            filename (str): Image filename.
            coords (list of tuples): List of (x, y, z) coordinates.
        Returns:
            list of str: Transformed coordinates as strings."""
    # Equivalent to:  
    # 'gdalinfo IMG_...JP2 
    # | awk '/Upper Left/{ul=$0} /Upper Right/{ur=$0} /Lower Right/{lr=$0} /Lower Left/{ll=$0} 
    # END {print ul RS ur RS lr RS ll RS ul}' 
    # | sed -E 's/.*\(\s*([0-9.+-]+),\s*([0-9.+-]+).*/\1 \2/' 
    # | gdaltransform -rpc -t_srs EPSG:4326 IMG_...JP2'.
    try:
        cmd = [
            'gdaltransform',
            '-rpc',
            '-t_srs', f'EPSG:{epsg}',
            filepath
        ]
        # Join all coordinates into a single input string

        # {'upperLeft': [0.0, 0.0], 'lowerLeft': [0.0, 351.0], 'lowerRight': [275.0, 351.0], 'upperRight': [275.0, 0.0], 'center': [137.5, 175.5]}
        coords_str = '\n'.join(
            f"{coords[key][0]} {coords[key][1]}" for key in ('upperLeft', 'upperRight', 'lowerRight', 'lowerLeft', 'center')
        )


        result = subprocess.run(
            cmd,
            input=coords_str.encode(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        resultstring = result.stdout.decode().strip()

        coords_new = coords.copy()

        # update coords
        for i, key in enumerate(('upperLeft', 'upperRight', 'lowerRight', 'lowerLeft', 'center')):
            x, y, z  = map(float, resultstring.splitlines()[i].split())
            coords_new[key] = [x, y]


        return coords_new
    except subprocess.CalledProcessError as ex:
        msg = f'gdal_transform_rpc: failed on {filepath}: {ex.stderr.decode().strip()}'
        print(msg, file=sys.stderr)
    return None

def _gdal_contains_epsg( gdalinfo):
    """Return gdalinfo contains epsg crs other than WGS84 Extents."""
    # Gdalinfo 'stac'.'proj:epsg'
    if gdalinfo and 'stac' in gdalinfo and 'proj:epsg' in gdalinfo['stac']:
        return gdalinfo['stac']['proj:epsg']
    return None

def _gdal_contains_rpc(gdalinfo):
    """Return gdalinfo contains rpc data."""
    # Gdalinfo 'metadata'.'rpc'
    if gdalinfo and 'metadata' in gdalinfo and 'RPC' in gdalinfo['metadata']:
        return gdalinfo['metadata']['RPC']
    return None



def transform_coords(coords, src_crs, tgt_crs):


#   print(f'Transforming corner coordinates from EPSG:{src_crs} to {tgt_crs}', file=sys.stderr)

    new_coords = coords.copy()

    # Set up source and target spatial references
    src_srs = osr.SpatialReference()
    src_srs.ImportFromEPSG((src_crs))
    src_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

    tgt_srs = osr.SpatialReference()
    tgt_epsg = int(tgt_crs)
    tgt_srs.ImportFromEPSG(tgt_epsg)
    tgt_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

    transform = osr.CoordinateTransformation(src_srs, tgt_srs)
    # Transform each corner coordinate
    for key in ('upperLeft', 'upperRight', 'lowerRight', 'lowerLeft'):
        x, y = coords[key]
        x2, y2, _ = transform.TransformPoint(x, y)
        new_coords[key] = [x2, y2]

    return new_coords




def getbound_poly(filepath,infojson=None,target_crs=3857):

    if infojson is None:
       infojson = gdal_info(filepath)

    if not infojson:
        msg = f'gdal_info_failed on {filepath}.'
        print(msg, file=sys.stderr)
        return None, None
        

    crs = _gdal_contains_epsg(infojson)
    original_crs = crs  # Store the original CRS

    if 'cornerCoordinates' not in infojson:
        msg = f'gdal_info: no cornerCoordinates in {filepath}.'
        print(msg, file=sys.stderr)
        return None
    
    coords = infojson['cornerCoordinates']

    if not crs:
        # if rpcdata is present
        rpcdata = _gdal_contains_rpc(infojson)
        if rpcdata:
            print(f'gdal_info: using RPC data for {filepath}.', file=sys.stderr)
            # coords, use pixel counts
            coords = gdal_transform_rpc(filepath, target_crs, coords)
            crs = target_crs # altready transformed
            original_crs = 0  # RPC data doesn't have a specific EPSG code
        else:
            msg = f'gdal_info: no EPSG CRS in {filepath} and no RPC data.'
            print(msg, file=sys.stderr)
            return None, None
        
        
    #CRS exists
    
# print(f'CRS for {filepath}: {crs} Target CRS: {target_crs}', file=sys.stderr)    if crs != target_crs:
    try:
        coords = transform_coords(coords, crs, target_crs)

    except Exception as ex:
        msg = f'Coordinate transformation failed for {filepath}: {ex}'
        print(msg, file=sys.stderr)
        return None, None
    
    polygon = {
        'type': 'Polygon',  # GeoJSON type  
        'coordinates': [
            [
                [coords['upperLeft'][0], coords['upperLeft'][1]],
                [coords['upperRight'][0], coords['upperRight'][1]],
                [coords['lowerRight'][0], coords['lowerRight'][1]],
                [coords['lowerLeft'][0], coords['lowerLeft'][1]],
                [coords['upperLeft'][0], coords['upperLeft'][1]]  # Closing the polygon
            ]
        ],
    }
    return polygon, original_crs




def _serialise(value: Any) -> Any:  # noqa: C901 – complexity acceptable
    """Recursively convert *value* into JSON‑friendly primitives."""

    # ── Bytes → UTF‑8 string / list[int] ─────────────────────────────────────
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return list(value)

    # ── NumPy scalars / arrays ───────────────────────────────────────────────
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()

    # ── Path objects → str ───────────────────────────────────────────────────
    if isinstance(value, Path):
        return str(value)

    # ── laspy PointFormat special‑case ───────────────────────────────────────
    if _LasPointFormat is not None and isinstance(value, _LasPointFormat):  # type: ignore[arg-type]
        return {
            "id": value.id,
            "size": value.size ,
            "num_extra_bytes ": value.num_extra_bytes,
            "num_standard_bytes ": value.num_standard_bytes ,
            "dimensions": [d.name for d in value.dimensions],
        }

    # ── Mapping (dict‑like) → recurse over keys/values ───────────────────────
    if isinstance(value, Mapping):  # includes dict, defaultdict, OrderedDict …
        return {str(k): _serialise(v) for k, v in value.items()}

    # ── Sequence / set but **not** (str, bytes) → recurse element‑wise ───────
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_serialise(v) for v in value]
    
    # datetime.date
    if isinstance(value, datetime.date):
        return value.isoformat()

    # ── Fallback: if JSON accepts it, keep; else stringify ───────────────────
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)




def get_las_info(filepath):
    """Returns LAS/LAZ file information as a dictionary."""
    if not HAS_LASPY:
        msg = f'las_info: laspy not installed, cannot process {filepath}.'
        print(msg, file=sys.stderr)
        return None

    try:
        with laspy.open(filepath) as las_file:
            header = las_file.header

            # convert header into json-like dictionary
            info: Dict[str, Any] = {}
            for name in dir(header):
                if name.startswith("_"):
                    continue  # Skip private attrs
                try:
                    val = getattr(header, name)
                except AttributeError:
                    continue

                # Skip callables (methods, properties w/ arguments, etc.)
                if callable(val):
                    continue

                # Special‑case Variable Length Records
                if name == "vlrs":
                    val = [
                        {
                            "user_id": v.user_id,
                            "record_id": v.record_id,
                            "description": v.description,
                            # if has record data
                        # "AttributeError: 'GeoKeyDirectoryVlr' object has no attribute 'record_data'"
                            # Raw bytes converted to list of ints for JSON safety
                            "record_data": list(v.record_data) if hasattr(v, 'record_data') else None,

                            # "record_data": list(v.record_data),
                        }
                        for v in val
                    ]

                info[name] = _serialise(val)
              # Extract CRS information if available and store it instead of the raw header object
            crs_info = header.parse_crs()

            # if crs_info is not None:
            #         # 'COMPD_CS***
            #     if 'COMPD_CS' in crs_info.srs:
            #         ascii_vlr = header.vlrs.get("GeoAsciiParamsVlr")
            #         if ascii_vlr:
            #             crs_info2 = crs_from_ascii_strings(ascii_vlr[0].strings)



            if crs_info is None:
                info['bad_crs'] = True
                ascii_vlr = header.vlrs.get("GeoAsciiParamsVlr")
                if ascii_vlr:
                     crs_info = crs_from_ascii_strings(ascii_vlr[0].strings)

            if crs_info is None:
                info['crs'] = None
                info['srs'] = None
            else:
                info['crs'] = crs_info.to_json_dict()
                info['srs'] = crs_info.to_2d().to_epsg() if crs_info.srs else None
            
            # Store header properties we might need later, but don't store the raw header object
            info['header_info'] = {
                'version': header.version,
                'point_format': _serialise(header.point_format),
                'scales': _serialise(header.scales),
                'offsets': _serialise(header.offsets)
            }
            
            # Extract corner coordinates
            corner_coordinates = {
                'upperLeft': [float(header.mins[0]), float(header.maxs[1])],
                'upperRight': [float(header.maxs[0]), float(header.maxs[1])],
                'lowerRight': [float(header.maxs[0]), float(header.mins[1])],
                'lowerLeft': [float(header.mins[0]), float(header.mins[1])],
                'center': [
                    float(header.mins[0] + (header.maxs[0] - header.mins[0]) / 2),
                    float(header.mins[1] + (header.maxs[1] - header.mins[1]) / 2)
                ]
            }
            
            info['cornerCoordinates'] = corner_coordinates
            
            return info
    except Exception as ex:
        msg = f'las_info: failed on {filepath}: {str(ex)}.'
        print(msg, file=sys.stderr)
    
    return None


def get_las_crs(header):

    crsdata = header.parse_crs()
    crs = crsdata.srs
    return crs if crs else None


   

def getbound_poly_las(filepath, las_info=None, target_crs=3857):
    """Get the bounding polygon for a LAS/LAZ file."""
    if not HAS_LASPY:
        msg = f'getbound_poly_las: laspy not installed, cannot process {filepath}.'
        print(msg, file=sys.stderr)
        return None, None
    
    if las_info is None:
        las_info = get_las_info(filepath)
    
    if not las_info or 'cornerCoordinates' not in las_info:
        msg = f'las_info: no cornerCoordinates in {filepath}.'
        print(msg, file=sys.stderr)
        return None, None
    
    coords = las_info['cornerCoordinates']
      # Try to determine the source CRS from the LAS file
    src_crs = None
    if 'srs' in las_info:
        src_crs = las_info['srs']

    # get as int after epsg
    # src_crs = int(src_crs.split(':')[-1]) if src_crs else None
    # src_crs = int(src_crs.split(':')[-1]) if src_crs else None
    
    # Store the original CRS for returning later
    original_crs = src_crs
    
    # If we couldn't determine the CRS from the file, use a default
    # or inform the user that we're making an assumption
    if not src_crs:
        print(f"Warning: Could not determine CRS for {filepath}", file=sys.stderr)
        src_crs = None  # WGS 84 as a reasonable default for LiDAR data    # Transform coordinates if necessary
    if src_crs != target_crs:
        try:
            print(f"Transforming LAS coordinates from EPSG:{src_crs} to EPSG:{target_crs}", file=sys.stderr)
            coords = transform_coords(coords, src_crs, target_crs)
        except Exception as ex:
            msg = f"Coordinate transformation failed for LAS file {filepath}: {ex}"
            print(msg, file=sys.stderr)
            # Continue with untransformed coordinates rather than failing completely

    # Check for Infinity values in coordinates
    for corner in ['upperLeft', 'upperRight', 'lowerRight', 'lowerLeft']:
        if corner not in coords:
            print(f"Warning: Missing {corner} coordinate in {filepath}", file=sys.stderr)
            return None, original_crs
        
        # Check if values are numbers and not infinity or NaN
        for val in coords[corner]:
            if not isinstance(val, (int, float)) or not np.isfinite(val):
                print(f"Warning: Invalid coordinate value {val} in {corner} for {filepath}", file=sys.stderr)
                return None, original_crs
    
    # Create polygon only if all coordinates are valid
    polygon = {
        'type': 'Polygon',  # GeoJSON type  
        'coordinates': [
            [
                [coords['upperLeft'][0], coords['upperLeft'][1]],
                [coords['upperRight'][0], coords['upperRight'][1]],
                [coords['lowerRight'][0], coords['lowerRight'][1]],
                [coords['lowerLeft'][0], coords['lowerLeft'][1]],
                [coords['upperLeft'][0], coords['upperLeft'][1]]  # Closing the polygon
            ]
        ],
    }
    
    # Final safety check - convert to string and check for "Infinity"
    polygon_str = json.dumps(polygon)
    if "Infinity" in polygon_str or "NaN" in polygon_str:
        print(f"Warning: Found Infinity or NaN in final polygon for {filepath}, returning None", file=sys.stderr)
        return None, original_crs
        
    return polygon, original_crs


if __name__ == '__main__':

    from tests.testpaths import testpaths

    # Tests for geoutils.
    # mnt/datapool2/Archive/EO_IMAGERY/raw/aoi/Curranyalpa_AOI2/Curranyalpa_AOI2/01_Raw/JL1KF01C_PMSL6_20250118084319_200341659_101_0021_001_L1_978900/JL1KF01C_PMSL6_20250118084319_200341659_101_0021_001_L1_MSS_978900/JL1KF01C_PMSL6_20250118084319_200341659_101_0021_001_L1_MSS_978900.tif
    def tests_geoutils_gdal_info_native():
        for filepath in testpaths:
            print(f'filepath={filepath}', file=sys.stderr)
            result = _gdal_info_native(filepath)
            result_str = dumps(result)
            print(f'result_str={result_str}', file=sys.stderr)

    def tests_geoutils_gdal_info_subprocess():
        for filepath in testpaths:
            print(f'filepath={filepath}', file=sys.stderr)
            result = _gdal_info_subprocess(filepath)
            result_str = dumps(result)
            print(f'result_str={result_str}', file=sys.stderr)

    def test_polygon():
        for filepath in testpaths:
            ext = os.path.splitext(filepath)[1].lower()
            if ext not in ('.tif', '.jp2', '.tiff'):
                print(f'Skipping non-image file: {filepath}', file=sys.stderr)
                continue
            # print(f'filepath={filepath}', file=sys.stderr)
            polygon = getbound_poly(filepath)
            if polygon:
                print(f'Polygon for {filepath}: {dumps(polygon)}', file=sys.stderr)
            else:
                print(f'Failed to get polygon for {filepath}', file=sys.stderr)
              
    def test_las_crs(filepath):
        """Test function to extract CRS information from a LAS/LAZ file."""
        if not filepath.lower().endswith(('.las', '.laz')):
            return None
        
        try:
            with laspy.open(filepath) as las_file:
                header = las_file.header
                crs_info = get_las_crs(header)
                return crs_info
        except Exception as ex:
            print(f"Error extracting CRS from {filepath}: {ex}", file=sys.stderr)
            return None   
    def test_las():
        for filepath in testpaths:
            if filepath.lower().endswith(('.las', '.laz')):
                print(f'Testing LAS/LAZ file: {filepath}', file=sys.stderr)
                info = get_las_info(filepath)
                if info:
                    dumps_info = json.dumps(info, indent=2)
                    print(f'LAS info for {filepath}:\n{dumps_info}', file=sys.stderr)
                    # Extract and display CRS information from the serialized info
                    crs_code = None
                    if 'crs' in info:
                        crs_code = info['crs']
                    
                    if crs_code:
                        print(f'Detected CRS for {filepath}: EPSG:{crs_code}', file=sys.stderr)
                    else:
                        print(f'Could not detect CRS for {filepath}, using default', file=sys.stderr)
                    
                    # Generate and display polygon
                    polygon = getbound_poly_las(filepath, info)
                    if polygon:
                        print(f'LAS polygon for {filepath}: {dumps(polygon)}', file=sys.stderr)
                    else:
                        print(f'Failed to get LAS polygon for {filepath}', file=sys.stderr)
                else:
                    print(f'Failed to get LAS info for {filepath}', file=sys.stderr)

    def tests():
        # tests_geoutils_gdal_info_native()
        # tests_geoutils_gdal_info_subprocess()
        test_polygon()
        if HAS_LASPY:
            test_las()


    tests()