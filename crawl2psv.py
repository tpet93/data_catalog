# Crawl Imagery File Metadata into PSV.
import sys
import os
from datetime import datetime
from geoutils import *
from produtils import *
from utils import *
import os.path

import argparse  # Add this import

DEBUG = True
DEBUG = False  # Set to True for debugging output






EPSG = 3857  # EPSG code for WGS84 / Pseudo-Mercator


include_exts = (
    '.jp2',
    '.tif',
    '.tiff',
    '.las',
    '.laz',
)

excluded_exts = (
    '.copc.laz',
)

exclude_dirs = (
    '.git',
    '.vs',
    '.vscode',
    'temp',
    'ept-data',

)


def imagery_metadata_processor(progname, crawlname, curdirpath, curfilenames, filename):
    """File Metadata Processor."""
    index = []
    errors = []
    try:
        # Filepath
        filepath = posixpath(os.path.join(curdirpath, filename))
        if not os.path.exists(filepath):
            msg = f'File "{filepath}" not found!'
            print(msg, file=sys.stderr)
            raise FileNotFoundError(msg)
        if not DEBUG:
            print(fileuri(filepath))
        index.append({})
        index[-1].update({
            'filename_text': filename,
            'filepath_text': fileuri(filepath),
        })
        # Filename datetime and infix for Product
        filetime, infix = file_time(filename)
        index[-1].update({
            'filetime_datetime': filetime,
        })
        # File system stats
        stat = os.stat(filepath)
        size = stat.st_size
        ctime_str = datetime.fromtimestamp(stat.st_ctime).isoformat()
        mtime_str = datetime.fromtimestamp(stat.st_mtime).isoformat()
        index[-1].update({
            'size_bigint': size,
            'modified_datetime': mtime_str,
            'created_datetime': ctime_str,
        })
        # Preview JPEG filepath
        previewfilepath = preview_filepath(curdirpath, curfilenames, infix)
        index[-1].update({
            'previewfilepath_text': fileuri(previewfilepath),
        })
        
        # Process file based on extension
        ext = os.path.splitext(filepath)[1].lower()
          # For LAS/LAZ files
        if ext in ('.las', '.laz'):
            lidar_info = get_las_info(filepath)
            polygon, original_crs = getbound_poly_las(filepath, lidar_info, target_crs=EPSG)
            if DEBUG:
                print(dumps(lidar_info), end='')
                print(',')
            lidar_info_json = compacts(lidar_info)
            if original_crs is None:
                original_crs = bbox_json = None

            bbox_json = compacts(polygon) if polygon else None

            
            metadatafilepath, metadata_json = metadatapath(curdirpath, curfilenames, filename, infix)
            
            bbox_epsg = EPSG if bbox_json else None
            index[-1].update({
                'metadatafilepath_text': fileuri(metadatafilepath),
                'bbox_epsg_int': bbox_epsg,
                'original_crs_int': original_crs,  # Add original CRS
                'bbox_json': bbox_json,
                'gdalinfo_json': None,  # Store LAS/LAZ specific info
                'pylasinfo_json': lidar_info_json,  # Store LAS/LAZ specific info
                'metadata_json': metadata_json,
            })        # For TIFF/JP2 files
        else:
            # Gdalinfo and BBox and XML filepaths
            gdalinfo = gdal_info(filepath)
            polygon, original_crs = getbound_poly(filepath, gdalinfo, target_crs=EPSG)
            if DEBUG:
                print(dumps(gdalinfo), end='')
                print(',')
            gdalinfo_json = compacts(gdalinfo)
            bbox_json = compacts(polygon) if polygon else None

            metadatafilepath, metadata_json = metadatapath(curdirpath, curfilenames, filename, infix)

            bbox_epsg = EPSG if bbox_json else None
            index[-1].update({
                'metadatafilepath_text': fileuri(metadatafilepath),
                'bbox_epsg_int': bbox_epsg,
                'original_crs_int': original_crs,  # Add original CRS
                'bbox_json': bbox_json,
                'gdalinfo_json': gdalinfo_json,
                'pylasinfo_json': None,  # Store LAS/LAZ specific info
                'metadata_json': metadata_json,
            })
    except Exception as ex:
        msg = f'gdalinfo_processor: failed on {ex}.'
        print(msg, file=sys.stderr)
        errors.append(filepath)
        return [], errors
    return index, errors

def crawler(progname, crawlname, crawlrootdir, custom_extensions=None):
    """Recurse dirtree returning gdalinfo metadata index for files matching criteria."""
    index = []
    errors = []
    # original_stderr = sys.stderr
    # sys.stderr = open(os.devnull, 'w') # swallow debugging
    crawlrootdir = posixpath(crawlrootdir)
    if not os.path.isdir(crawlrootdir):
        msg = f'Crawl Root Dir "{crawlrootdir}" not found or not a directory!'
        print(msg, file=sys.stderr)
        raise NotADirectoryError(msg)
    
    # Use custom extensions if provided, otherwise use default include_exts
    extensions_to_use = custom_extensions if custom_extensions else include_exts
    
    if DEBUG:
        print('[')
    for curdirpath, curdirnames, curfilenames in os.walk(crawlrootdir, topdown=True):
        curdirpath = posixpath(curdirpath)
        # if'temp' in path skip
        # if 'temp' in curdirpath.lower():
        #     if DEBUG:
        #         print(f'Skipping directory "{curdirpath}" due to "temp" in path.')
        #     continue
        # Modify curdirnames in-place to prevent os.walk from descending into excluded dirs
        curdirnames[:] = [_ for _ in curdirnames if _ not in exclude_dirs]
        # So can diff with find
        curdirnames = sorted(curdirnames)
        curfilenames = sorted(curfilenames)
        # Included file extensions
        filenames = [_ for _ in curfilenames if os.path.splitext(_)[1].lower() in extensions_to_use]

        # excluded_exts
        filenames = [_ for _ in filenames if os.path.splitext(_)[1].lower() not in excluded_exts]
        for filename in filenames:
            _index, _errors = imagery_metadata_processor(progname, crawlname, curdirpath, curfilenames, filename)
            if _index:
                index.extend(_index)
            if _errors:
                errors.extend(_errors)
        else:
            pass
    if DEBUG:
        print(']')
    # sys.stderr.close()
    # sys.stderr = original_stderr
    return index, errors

def crawl2psv(progname, crawlrootdir, custom_extensions=None):
    """Crawl and output index PSV with crawler JSON metadata."""
    crawlrootdir = os.path.abspath(crawlrootdir)
    crawlrootdir = os.path.dirname(crawlrootdir) if os.path.isfile(crawlrootdir) else crawlrootdir
    crawlname = os.path.basename(crawlrootdir)
    start = datetime.now()
    index, errors = crawler(progname, crawlname, crawlrootdir, custom_extensions)
    end = datetime.now()
    duration = end - start
    count = len(index)
    # ACCOUNT FOR 0
    duration_per_count = duration / count if count > 0 else duration
    info = { 
        'crawlrootdir': crawlrootdir,
        'start': start.isoformat(), 
        'end': end.isoformat(),
        'duration': str(duration),
        'count': count,
        'duration_per_count': str(duration_per_count),
    }
    jsonfn = f'{progname}.{crawlname}' + '.json'
    save_json(jsonfn, info)
    csvfn = f'{progname}.{crawlname}' + '.psv'

    save_psv(csvfn, index)
    errfn = f'{progname}.{crawlname}' + '.err'
    save_txt(errfn, errors)


def main(args=None):
    """Main parameters."""

    parser = argparse.ArgumentParser(description='Crawl directories for files and generate metadata PSV')
    parser.add_argument('crawlrootdirs', nargs='+', help='Root directories to crawl')
    parser.add_argument('--ext', nargs='+', help='File extensions to include (override defaults)')
    


    # If args is passed, use those, otherwise use sys.argv
    parsed_args = parser.parse_args(args[1:] if args else None)
    
    progname = os.path.splitext(os.path.basename(sys.argv[0]))[0]
    custom_extensions = None
    
    if parsed_args.ext:
        # Process extensions
        custom_extensions = ['.' + ext.lower().lstrip('.') for ext in parsed_args.ext]
        print(f"Using custom extensions: {custom_extensions}", file=sys.stderr)


    if not parsed_args.crawlrootdirs:
        # If in debug mode
        if DEBUG:
            from tests.testpaths import testpaths
            crawlrootdirs = testpaths
            crawlrootdirs = [os.path.dirname(_) for _ in crawlrootdirs if os.path.isfile(_)]
        else:
            print(f'No directories specified for crawling.', file=sys.stderr)
            parser.print_help()
            return 1
    else:
        crawlrootdirs = parsed_args.crawlrootdirs
 
    for crawlrootdir in crawlrootdirs:
        crawl2psv(progname, crawlrootdir, custom_extensions)
    return 0

if __name__ == '__main__':
    main(sys.argv)
    # main(['python','/mnt/datapool2/Archive/EO_IMAGERY/raw/aoi/'])

