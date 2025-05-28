# Product Utilities.
import sys
from datetime import datetime
import json
import os
import re
import xmltodict
from geoutils import build_bbox
from utils import compacts, dumps, read_xml


AOI = 4
AIRBUS = 3
MAXAR = 1
UNKNOWN = None


def file_time(filename):
    """Extract iso datetime from filename if possible."""
    t2 = _file_time_airbus(filename)
    if all(t2):
        return t2
    t2 = _file_time_aoi(filename)
    if all(t2):
        return t2
    t2 = _file_time_maxar(filename)
    if all(t2):
        return t2
    return None, None

def _file_time_airbus(filename):
    """Extract iso datetime from 4th infix if possible."""
    # e.g. IMG_PHR1A_MS_202111220049294_SEN_7108037101-2_R1C1.JP2
    regex = re.compile(r'^(.*?)_(.*?)_(.*?)_(\d{14})\d{1}_', re.IGNORECASE)
    match = regex.match(filename)
    if match:
        try:
            filetime_str = match.group(AOI)
            return datetime.strptime(filetime_str, '%Y%m%d%H%M%S').isoformat(), AOI
        except ValueError:
            pass
    return None, None

def _file_time_aoi(filename):
    """Extract iso datetime from 3rd infix if possible."""
    # e.g. JL1KF01C_PMSL3_20250112084005_200339713_101_0039_001_L1_MSS_978899.tif
    regex = re.compile(r'^(.*?)_(.*?)_(\d{14})_', re.IGNORECASE)
    match = regex.match(filename)
    if match:
        filetime_str = match.group(AIRBUS)
        try:
            return datetime.strptime(filetime_str, '%Y%m%d%H%M%S').isoformat(), AIRBUS
        except ValueError:
            pass
    return None, None

def _file_time_maxar(filename):
    """Extract iso datetime from 1st infix (prefix) if possible."""
    # e.g. 23NOV11004600-M2AS_R1C1-050186140010_01_P001.TIF
    #      23NOV11004600-M2AS_R2C1-050186140010_01_P001.TIF
    regex = re.compile(r'^(\d{2}[A-Z]{3}\d{8})-', re.IGNORECASE)
    match = regex.match(filename)
    if match:
        filetime_str = match.group(MAXAR)
        try:
            return datetime.strptime(filetime_str, '%y%b%d%H%M%S').isoformat(), MAXAR
        except ValueError:
            pass
    return None, None


def bbox(dirpath, filenames, filename, infix, gdalinfo):
    """Retrieve Bounding Box JSON if possible."""
    regex = re.compile(r'^(.*?)\.xml$', re.IGNORECASE)
    filenames = [_ for _ in filenames if regex.match(_)]
    if filenames:
        for filename in filenames:
            t3 = _bbox_matches_airbus(dirpath, filename, infix, gdalinfo)
            if all(t3):
                return t3
            t3= _bbox_matches_aoi(dirpath, filename, infix, gdalinfo)
            if all(t3):
                return t3
            t3 = _bbox_matches_maxar(dirpath, filename, infix, gdalinfo)
            if all(t3):
                return t3
    else:
        t3 = _bbox_unmatched_other_ortho(dirpath, filename, infix, gdalinfo)
        if any(t3):
            return t3
    return None, None, None

def _bbox_matches_airbus(dirpath, filename, infix, gdalinfo):
    """Retrieve Bounding Box JSON if possible."""
    bbox_json = None
    xmlfilepath = None
    xml_json = None
    # e.g. DIM_PHR1A_MS_202111220049294_SEN_7108037101-2.XML
    regex = re.compile(r'^DIM_(.*?)\.xml$', re.IGNORECASE)
    match = regex.match(filename)
    if match:
        try:
            xmlfilepath = os.path.join(dirpath, filename)
            xml_str = read_xml(xmlfilepath)
            xmlinfo = xmltodict.parse(xml_str)
            xml_json = compacts(xmlinfo)
            dataset_extent = xmlinfo['Dimap_Document']['Dataset_Content']['Dataset_Extent']
            lons = [float(_['LON']) for _ in dataset_extent['Vertex']]
            lats = [float(_['LAT']) for _ in dataset_extent['Vertex']]
            bbox = build_bbox(lons, lats)
            bbox_json = compacts(bbox)
        except:
            pass
    return bbox_json, xmlfilepath, xml_json

def _bbox_matches_aoi(dirpath, filename, infix, gdalinfo):
    """Retrieve Bounding Box JSON if possible."""
    bbox_json = None
    xmlfilepath = None
    xml_json = None
    # e.g. JL1KF01C_PMSL3_20250112084005_200339713_101_0039_001_L1_MSS_978899_meta.xml
    regex = re.compile(r'^(.*?)_meta\.xml$', re.IGNORECASE)
    match = regex.match(filename)
    if match:
        try:
            xmlfilepath = os.path.join(dirpath, filename)
            xml_str = read_xml(xmlfilepath)
            xmlinfo = xmltodict.parse(xml_str)
            xml_json = compacts(xmlinfo)
            productinfo = xmlinfo['MetaData']['ProductInfo']
            lons_keys = ('UpperLeftLongitude', 'UpperRightLongitude', 'LowerRightLongitude', 'LowerLeftLongitude')
            lats_keys = ('UpperLeftLatitude', 'UpperRightLatitude', 'LowerRightLatitude', 'LowerLeftLatitude')
            lons = [float(productinfo[_]) for _ in lons_keys]
            lats = [float(productinfo[_]) for _ in lats_keys]
            bbox = build_bbox(lons, lats)
            bbox_json = compacts(bbox)
        except:
            pass
    return bbox_json, xmlfilepath, xml_json

def _bbox_matches_maxar(dirpath, filename, infix, gdalinfo):
    """Retrieve Bounding Box JSON if possible."""
    bbox_json = None
    xmlfilepath = None
    xml_json = None
    # e.g. 23NOV11004600-M2AS-050186140010_01_P001.XML
    regex = re.compile(r'^(.*?)\.xml$', re.IGNORECASE)
    match = regex.match(filename)
    if match:
        try:
            xmlfilepath = os.path.join(dirpath, filename)
            xml_str = read_xml(xmlfilepath)
            xmlinfo = xmltodict.parse(xml_str)
            xml_json = compacts(xmlinfo)
        except:
            pass
    try:
        # Gdalinfo contains 'wgs84Extent'.'type'&.'coordinates'.[0],[1],[2],[3],[0].
        if gdalinfo and 'wgs84Extent' in gdalinfo:
            coordinates = gdalinfo['wgs84Extent']['coordinates']
            lons = [float(_[0]) for _ in coordinates[0]]
            lats = [float(_[1]) for _ in coordinates[0]]
            bbox = build_bbox(lons, lats)
            bbox_json = compacts(bbox)
    except:
        pass
    return bbox_json, xmlfilepath, xml_json

def _bbox_unmatched_other_ortho(dirpath, filename, infix, gdalinfo):
    """Retrieve Bounding Box JSON if possible."""
    bbox_json = None
    xmlfilepath = None
    xml_json = None
    try:
        # Gdalinfo contains 'wgs84Extent'.'type'&.'coordinates'.[0],[1],[2],[3],[0].
        if gdalinfo and 'wgs84Extent' in gdalinfo:
            coordinates = gdalinfo['wgs84Extent']['coordinates']
            lons = [float(_[0]) for _ in coordinates[0]]
            lats = [float(_[1]) for _ in coordinates[0]]
            bbox = build_bbox(lons, lats)
            bbox_json = compacts(bbox)
    except:
        pass
    return bbox_json, xmlfilepath, xml_json


def preview_filepath(dirpath, filenames, infix):
    """Find Preview JPEG filename if possible."""
    regex = re.compile(r'^(.*?)\.jpg$', re.IGNORECASE)
    filenames = [_ for _ in filenames if regex.match(_)]
    for filename in filenames:
        if _preview_filename_matches_airbus(filename, infix) \
           or _preview_filename_matches_aoi(filename, infix) \
           or _preview_filename_matches_maxar(filename, infix):
            previewfilepath = os.path.join(dirpath, filename).replace(os.sep, "/")
            return previewfilepath
    return None

def _preview_filename_matches_airbus(filename, infix):
    """Find Preview JPEG filename if possible."""
    # e.g. PREVIEW_PHR1A_MS_202111220049294_SEN_7108037101-2.JPG
    regex = re.compile(r'^PREVIEW_(.*?)\.jpg$', re.IGNORECASE)
    return regex.match(filename)

def _preview_filename_matches_aoi(filename, infix):
    """Find Preview JPEG filename if possible."""
    # e.g. JL1KF01C_PMSL3_20250112084005_200339713_101_0039_001_L1_MSS_978899.jpg
    filebase = os.path.splitext(filename)[0]
    regex = re.compile(rf'^{filebase}\.jpg$', re.IGNORECASE)
    return regex.match(filename)

def _preview_filename_matches_maxar(filename, infix):
    """Find Preview JPEG filename if possible."""
    # e.g. 23NOV11004600-M2AS-050186140010_01_P001-BROWSE.JPG
    regex = re.compile(r'^(.*?)-BROWSE\.jpg$', re.IGNORECASE)
    return regex.match(filename)


if __name__ == '__main__':
    # Tests for produtils.
    def tests_filetime():
        # Airbus
        filename = 'IMG_PHR1A_MS_202111220049294_SEN_7108037101-2_R1C1.JP2'
        print(f'filename={filename}', file=sys.stderr)
        result = file_time(filename)
        print(f'result={result}', file=sys.stderr)
        # Aoi
        filename = 'JL1KF01C_PMSL3_20250112084005_200339713_101_0039_001_L1_MSS_978899.tif'
        print(f'filename={filename}', file=sys.stderr)
        result = file_time(filename)
        print(f'result={result}', file=sys.stderr)
        # Maxar
        filename = '23NOV11004600-P2AS_R2C1-050186140010_01_P001.TIF'
        print(f'filename={filename}', file=sys.stderr)
        result = file_time(filename)
        print(f'result={result}', file=sys.stderr)
        filename = 'bad.TIF'
        print(f'filename={filename}', file=sys.stderr)
        result = file_time(filename)
        print(f'result={result}', file=sys.stderr)
        filename = ''
        print(f'filename={filename}', file=sys.stderr)
        result = file_time(filename)
        print(f'result={result}', file=sys.stderr)

    def tests():
        tests_filetime()

    tests()

