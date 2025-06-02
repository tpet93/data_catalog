# Geospatial Utilities (GDAL et al).
import sys
import os
import json
from osgeo import gdal
from osgeo import osr
import platform
import subprocess
from utils import dumps, posixpath


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
        return None
        

    crs = _gdal_contains_epsg(infojson)

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
        else:
            msg = f'gdal_info: no EPSG CRS in {filepath} and no RPC data.'
            print(msg, file=sys.stderr)
            return None
        
    #CRS exists
    
    # print(f'CRS for {filepath}: {crs} Target CRS: {target_crs}', file=sys.stderr)
    if crs != target_crs:
        try:
            coords = transform_coords(coords, crs, target_crs)

        except Exception as ex:
            msg = f'Coordinate transformation failed for {filepath}: {ex}'
            print(msg, file=sys.stderr)
            return None
        
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
    return polygon


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
            # print(f'filepath={filepath}', file=sys.stderr)
            polygon = getbound_poly(filepath)
            if polygon:
                print(f'Polygon for {filepath}: {dumps(polygon)}', file=sys.stderr)
            else:
                print(f'Failed to get polygon for {filepath}', file=sys.stderr)
              
    def tests():
        # tests_geoutils_gdal_info_native()
        # tests_geoutils_gdal_info_subprocess()
        test_polygon()

    tests()