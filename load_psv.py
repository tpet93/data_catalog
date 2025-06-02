#!/usr/bin/env python3
"""
Script to load a PSV file into the PostgreSQL imagery_metadata table.
"""
import argparse
import io
import sys

import psycopg2
import requests


def parse_args():
    parser = argparse.ArgumentParser(
        description="Load a pipe-separated values (PSV) file into the imagery_metadata table."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--psv', '-p',
        help='Local path to the PSV file to load.'
    )
    group.add_argument(
        '--url', '-u',
        help='HTTP(S) URL to download the PSV file from.'
    )
    parser.add_argument(
        '--db-url', '-d',
        required=True,
        help='PostgreSQL connection URL, e.g. postgresql://user:pass@host:port/dbname'
    )
    parser.add_argument(
        '--clear', '-c',
        action='store_true',
        help='Truncate the imagery_metadata table before loading.'
    )
    parser.add_argument(
        '--epsg', '-e',
        type=int,
        default=3857,
        help='EPSG code for bbox geometry (default: 3857).'
    )
    parser.add_argument(
        '--init', '-i',
        action='store_true',
        help='Drop and recreate imagery_metadata table and indexes before loading.'
    )
    return parser.parse_args()


def load_psv_to_db(conn, file_obj):
    """
    Copy PSV content from file_obj into imagery_metadata table.
    """
    copy_sql = (
        "COPY imagery_metadata "
        "FROM STDIN WITH (FORMAT csv, DELIMITER '|', HEADER true)"
    )
    with conn.cursor() as cur:
        cur.copy_expert(copy_sql, file_obj)
    conn.commit()


def process_geometry(conn, epsg):
    """
    Add/Post-process geometry column bbox_geom using PostGIS based on EPSG code.
    """
    with conn.cursor() as cur:
        # Drop existing geometry column if present, then add fresh with correct SRID
        cur.execute("ALTER TABLE imagery_metadata DROP COLUMN IF EXISTS bbox_geom CASCADE;")
        cur.execute(
            "ALTER TABLE imagery_metadata ADD COLUMN bbox_geom geometry(Polygon, %s);",
            (epsg,)
        )
        # Populate and transform geometry from GeoJSON
        cur.execute(
            """
            UPDATE imagery_metadata
            SET bbox_geom = ST_Transform(
                ST_SetSRID(ST_GeomFromGeoJSON(bbox::text), bbox_epsg), %s
            )
            WHERE bbox IS NOT NULL AND bbox_epsg IS NOT NULL;
            """,
            (epsg,)
        )
        # Create spatial index
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_imagery_metadata_bbox_geom ON imagery_metadata USING GIST (bbox_geom);"
        )
    conn.commit()

        # Vacuum analyze table for QGIS metadata
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("VACUUM ANALYZE imagery_metadata;")
    conn.autocommit = False


def init_schema(conn):
    """
    Drop and recreate imagery_metadata table and primary index.
    """
    commands = [
        "DROP TABLE IF EXISTS imagery_metadata CASCADE;",
        '''
        CREATE TABLE imagery_metadata (
            filename TEXT,
            filepath TEXT,
            filetime TIMESTAMP,
            size BIGINT,
            modified TIMESTAMP,
            created TIMESTAMP,
            previewfilepath TEXT,
            metadatafilepath TEXT,
            bbox_epsg INT,
            bbox JSON,
            gdalinfo JSON,
            metadata JSON
        );
        ''',
        "DROP INDEX IF EXISTS idx_pk_imagery_metadata;",
        "CREATE INDEX idx_pk_imagery_metadata ON imagery_metadata (filename);"
    ]
    with conn.cursor() as cur:
        for cmd in commands:
            cur.execute(cmd)
    conn.commit()


def main():
    args = parse_args()

    # Establish database connection
    try:
        conn = psycopg2.connect(args.db_url)
    except Exception as exc:
        print(f"Failed to connect to database: {exc}", file=sys.stderr)
        sys.exit(1)

    # Initialize schema if requested
    if args.init:
        init_schema(conn)
        print("Initialized imagery_metadata table and primary index.")

    try:
        if args.clear:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE imagery_metadata;")
            conn.commit()
            print("Cleared imagery_metadata table.")

        # Obtain PSV content
        if args.url:
            print(f"Downloading PSV from {args.url}")
            response = requests.get(args.url)
            response.raise_for_status()
            file_obj = io.StringIO(response.text)
        else:
            print(f"Loading PSV from {args.psv}")
            file_obj = open(args.psv, 'r')
            if False:    
                import pandas as pd
                df1 = pd.read_csv(file_obj, sep='|', header=0, dtype=str)
                df2 =  pd.read_csv('/mnt/treeseg_pool/dev/data_catalog/crawl2psv.raw.psv', sep='|', header=0, dtype=str)
                df1.bbox_json[10]
                df2.bbox_json[10]
                # df1.
        # Load into DB
        load_psv_to_db(conn, file_obj)
        # Create geometry and spatial index
        process_geometry(conn, args.epsg)
        print("Successfully loaded PSV into imagery_metadata.")

    except Exception as exc:
        print(f"Error during load: {exc}", file=sys.stderr)
        sys.exit(1)

    finally:
        # Cleanup
        try:
            file_obj.close()
        except:
            pass
        conn.close()


if __name__ == '__main__':
    main()
