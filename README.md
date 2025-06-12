# Data Catalog

This repository contains tools for creating and managing a spatial data catalog.

## Features

- Crawling file systems for geospatial data files (TIFF, JP2, LAS, LAZ)
- Extracting metadata from geospatial files using GDAL and laspy
- Storing metadata in PostgreSQL database with PostGIS extension
- Transforming coordinates to a common coordinate reference system
- Preserving original CRS information from source files

## Recent Updates

- Added support for storing original CRS information from source files in the database
- Both TIFF/JP2 and LAS/LAZ file formats now include original CRS information in the PSV output
- Database schema updated to include `original_crs_int` column

## Usage

