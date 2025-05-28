# Geospatial Utilities (GDAL et al).
import sys
import os
import json
from osgeo import gdal
import platform
import subprocess
from utils import dumps, posixpath


def build_bbox(lons, lats):
    """Builds BBox from lons and lats lists."""
    min_lon = min(lons)
    max_lon = max(lons)
    min_lat = min(lats)
    max_lat = max(lats)
    bbox = {
        'type': 'Polygon',
        'coordinates': [
            [
                [min_lon, min_lat],
                [min_lon, max_lat],
                [max_lon, max_lat],
                [max_lon, min_lat],
                [min_lon, min_lat]
            ]
        ]
    }
    return bbox


def gdal_info(dirpath, filename):
    """Returns Gdalinfo as compact JSON."""
    # Equivalent to: 
    #   'gdalinfo -json -proj4 '{dirpath}\\{filename}' | jq -c .'.
    if platform.system() == 'Windows':
        return gdal_info_subprocess(dirpath, filename)
    elif platform.system() == 'Linux':
        return gdal_info_native(dirpath, filename)
    raise NotImplementedError('Running on an unknown OS!')

def gdal_info_native(dirpath, filename):
    """Returns Gdalinfo via native wrappers.
       Native (python API bindings over native) 
       skips case-sensitive '22633_TRING_1_4band' after '22633_TRING_1_4Band'."""
    filepath = posixpath(os.path.join(dirpath, filename))
    try:
        gdal.UseExceptions() # default versus # gdal.DontUseExceptions()
        dataset = gdal.Open(filepath)
        return gdal.Info(dataset, options=gdal.InfoOptions(
            format='json',
            options=[
                '-proj4',
            ])
        )
    except Exception as ex:
        msg = f'gdal_info_native: failed on {filename}: {str(ex)}.'
        print(msg, file=sys.stderr)
    return None

def gdal_info_subprocess(dirpath, filename):
    """Returns Gdalinfo via subprocess.
       Subprocess (exe or binary) picks up 
       case-sensitive '22633_TRING_1_4band' after '22633_TRING_1_4Band'."""
    filepath = posixpath(os.path.join(dirpath, filename))
    try:
        result = subprocess.run(
            [
                'gdalinfo',
                '-json',
                '-proj4',
                filepath,
            ],
            capture_output=True,
            check=True,
            text=True,
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as ex:
        msg = f'gdal_info_subprocess: failed on {filename}: {ex.stderr}.'
        print(msg, file=sys.stderr)
    return None


def gdal_transform_rpc(dirpath, filename, coords):
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
    filepath = posixpath(os.path.join(dirpath, filename))
    try:
        cmd = [
            'gdaltransform',
            '-rpc',
            '-t_srs', 'EPSG:4326',
            filepath
        ]
        # Join all coordinates into a single input string
        coords_str = '\n'.join(f'{x} {y} {z}' for x, y, z in coords) + '\n'
        result = subprocess.run(
            cmd,
            input=coords_str.encode(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return result.stdout.decode().strip().splitlines()
    except subprocess.CalledProcessError as ex:
        msg = f'gdal_transform_rpc: failed on {filename}: {ex.stderr.decode().strip()}'
        print(msg, file=sys.stderr)
    return None


if __name__ == '__main__':
    # Tests for geoutils.
    def tests_geoutils_gdal_info_native():
        dirpath = r"\\192.168.11.30\eo_imagery\raw\maxar\21410_Brindingabba\Brindingabba\050186140010_01\050186140010_01_P001_PAN"
        print(f'dirpath={dirpath}', file=sys.stderr)
        filename = '23NOV11004600-P2AS_R2C1-050186140010_01_P001.TIF'
        print(f'filename={filename}', file=sys.stderr)
        result = gdal_info_native(dirpath, filename)
        result_str = dumps(result)
        print(f'result_str={result_str}', file=sys.stderr)

    def tests_geoutils_gdal_info_subprocess():
        dirpath = r"\\192.168.11.30\eo_imagery\raw\maxar\21410_Brindingabba\Brindingabba\050186140010_01\050186140010_01_P001_PAN"
        print(f'dirpath={dirpath}', file=sys.stderr)
        filename = '23NOV11004600-P2AS_R2C1-050186140010_01_P001.TIF'
        print(f'filename={filename}', file=sys.stderr)
        result = gdal_info_subprocess(dirpath, filename)
        result_str = dumps(result)
        print(f'result_str={result_str}', file=sys.stderr)

    def tests():
        tests_geoutils_gdal_info_native()
        tests_geoutils_gdal_info_subprocess()

    tests()
