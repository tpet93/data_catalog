source .venv/bin/activate
mkdir -p ~/crawler/logs
cd ~/crawler/logs

# python3 -u /mnt/treeseg_pool/dev/data_catalog-1/crawl2psv.py /mnt/datapool2/Archive/EO_IMAGERY/raw/aoi/
cd ~/crawler/logs
python3 -u /mnt/treeseg_pool/dev/data_catalog-1/crawl2psv.py /mnt/datapool2/Archive/EO_IMAGERY/raw/

cd ~/crawler/logs
python3 -u /mnt/treeseg_pool/dev/data_catalog-1/crawl2psv.py /mnt/datapool1/datapool1/datasets/las/ --ext tiff tif jp2

cd ~/crawler/logs
python3 -u /mnt/treeseg_pool/dev/data_catalog-1/crawl2psv.py '/mnt/BAMspace3/ALS/1. ORGANISED ALS/'





export user=postgres
export password='suffocate cargo turtle'
export host='192.168.11.242:5434'
export dbname='catalog'


# urlencode password
export password=$(python3 -c "import urllib.parse; print(urllib.parse.quote('''$password'''))")

# Add original_crs_int column if it doesn't exist
# psql postgresql://$user:$password@$host/$dbname -f /mnt/treeseg_pool/dev/data_catalog-1/add_original_crs.sql
# === Test example commands ===

python3 -u /mnt/treeseg_pool/dev/data_catalog-1/load_psv.py \
    -p ~/crawler/logs/crawl2psv.raw.psv \
    -d postgresql://$user:$password@$host/$dbname --clear --init


python3 -u /mnt/treeseg_pool/dev/data_catalog-1/load_psv.py \
    -p "/home/tony/crawler/logs/crawl2psv.1. ORGANISED ALS.psv"\
    -d postgresql://$user:$password@$host/$dbname 



python3 -u /mnt/treeseg_pool/dev/data_catalog-1/load_psv.py \
    -p ~/crawler/logs/crawl2psv.las.psv \
    -d postgresql://$user:$password@$host/$dbname 

# Run geoutils tests (polygon extr
# Run geoutils tests (polygon extraction)
# python3 -u /mnt/treeseg_pool/dev/data_catalog-1/geoutils.py

# # Run produtils tests (file_time on test paths)
# python3 -u /mnt/treeseg_pool/dev/data_catalog-1/produtils.py
# # === End test examples ===

# Load a PSV into DB (replace DB URL and PSV path as needed)
# python3 -u /mnt/treeseg_pool/dev/data_catalog-1/load_psv.py \
#     -p /mnt/treeseg_pool/dev/data_catalog-1/crawl2psv.aoi.psv \
#     -d postgresql://$user:$password@$host/$dbname --clear --init


# open file and in first line replace lidar_info_json with pylasinfo_json
sed -i '1s/lidar_info_json/pylasinfo_json/' ~/crawler/logs/crawl2psv.las.psv
sed -i '1s/lidar_info_json/pylasinfo_json/' "/home/tony/crawler/logs/crawl2psv.1. ORGANISED ALS.psv"
sed -i '1s/lidar_info_json/pylasinfo_json/' ~/crawler/logs/crawl2psv.raw.psv
