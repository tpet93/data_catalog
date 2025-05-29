# Crawl Imagery File Metadata into PSV.
import sys
import os
from datetime import datetime
from geoutils import *
from produtils import *
from utils import *


DEBUG = False
# DEBUG = True


EPSG = 4326


include_exts = (
    '.jp2',
    '.tif',
    '.tiff',
)

exclude_dirs = (
    '.git',
    '.vs',
    '.vscode',
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
        # Gdalinfo and BBox and XML filepaths
        gdalinfo = gdal_info(curdirpath, filename)
        if DEBUG:
            print(dumps(gdalinfo), end='')
            print(',')
        gdalinfo_json = compacts(gdalinfo)
        bbox_json, metadatafilepath, metadata_json = bbox(curdirpath, curfilenames, filename, infix, EPSG, gdalinfo)
        bbox_epsg = EPSG if bbox_json else None
        index[-1].update({
            'metadatafilepath_text': fileuri(metadatafilepath),
            'bbox_epsg_int': bbox_epsg,
            'bbox_json': bbox_json,
            'gdalinfo_json': gdalinfo_json,
            'metadata_json': metadata_json,
        })
    except Exception as ex:
        msg = f'gdalinfo_processor: failed on {ex}.'
        print(msg, file=sys.stderr)
        errors.append(filepath)
        return [], errors
    return index, errors

def crawler(progname, crawlname, crawlrootdir):
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
    if DEBUG:
        print('[')
    for curdirpath, curdirnames, curfilenames in os.walk(crawlrootdir, topdown=True):
        curdirpath = posixpath(curdirpath)
        # Modify curdirnames in-place to prevent os.walk from descending into excluded dirs
        curdirnames[:] = [_ for _ in curdirnames if _ not in exclude_dirs]
        # So can diff with find
        curdirnames = sorted(curdirnames)
        curfilenames = sorted(curfilenames)
        # Included file extensions
        filenames = [_ for _ in curfilenames if os.path.splitext(_)[1].lower() in include_exts]
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

def crawl2psv(progname, crawlrootdir):
    """Crawl and output index PSV with crawler JSON metadata."""
    crawlrootdir = os.path.abspath(crawlrootdir)
    crawlrootdir = os.path.dirname(crawlrootdir) if os.path.isfile(crawlrootdir) else crawlrootdir
    crawlname = os.path.basename(crawlrootdir)
    start = datetime.now()
    index, errors = crawler(progname, crawlname, crawlrootdir)
    end = datetime.now()
    duration = end - start
    count = len(index)
    duration_per_count = duration / count
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
    progname = os.path.splitext(os.path.basename(sys.argv[0]))[0]
    crawlrootdirs = []
    if args and len(args) > 1:
        crawlrootdirs = args[1:]
    if not crawlrootdirs:
        print(f'Usage: {progname} dir-path(s)...', file=sys.stderr)
        return 1
    for crawlrootdir in crawlrootdirs:
        crawl2psv(progname, crawlrootdir)
    return 0


if __name__ == '__main__':
    main(sys.argv)
