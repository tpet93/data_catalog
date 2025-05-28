-- psv2table.sql
\! clear
\set ECHO all
---
\c catalog
---
DROP TABLE IF EXISTS imagery_metadata CASCADE;
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
DROP INDEX IF EXISTS idx_pk_imagery_metadata;
-- TODO: Upsert Insert|Update as duplicate files exist...
--CREATE UNIQUE INDEX idx_pk_imagery_metadata ON imagery_metadata (filename);
CREATE INDEX idx_pk_imagery_metadata ON imagery_metadata (filename);
---
\copy imagery_metadata FROM 'crawl2psv.samples.psv' WITH (FORMAT csv, DELIMITER '|', HEADER true, QUOTE '"');
--\copy imagery_metadata FROM 'crawl2psv.maxar.psv' WITH (FORMAT csv, DELIMITER '|', HEADER true, QUOTE '"');
--\copy imagery_metadata FROM 'crawl2psv.raw.psv' WITH (FORMAT csv, DELIMITER '|', HEADER true, QUOTE '"');
---
ALTER TABLE imagery_metadata ADD COLUMN bbox_geom GEOMETRY;
ALTER TABLE imagery_metadata
ALTER COLUMN bbox_geom TYPE GEOMETRY(Polygon, 4326)
USING ST_SetSRID(bbox_geom, 4326);
UPDATE imagery_metadata
SET bbox_geom = ST_SetSRID(ST_GeomFromGeoJSON(bbox), 4326)
WHERE bbox IS NOT NULL;
DROP INDEX IF EXISTS idx_imagery_metadata_bbox_geom;
CREATE INDEX idx_imagery_metadata_bbox_geom
ON imagery_metadata
USING GIST (bbox_geom);
---




