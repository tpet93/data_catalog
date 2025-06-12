import re
import laspy
from pyproj import CRS, exceptions
from pyproj.database import query_crs_info

# ---------------------------------------------------------------------------
#  generic "guess a CRS from the ASCII VLR" helper
# ---------------------------------------------------------------------------
_MGA_BASES = {
    "GDA94": 28300,     # EPSG 28348..28358  (zone 48-58)
    "GDA2020": 7800,   # EPSG 7846..7859
    "AGD66": 20200,     # EPSG 20248..20258
    "AGD84": 20300,     # EPSG 20348..20358
}
_ZONE_RX = re.compile(r"\b(MGA|AMG)\s+zone\s+(\d{2})\b", re.I)

def crs_from_ascii_strings(strings):
    """
    Try to turn any of the strings in GeoAsciiParamsVlr into a pyproj.CRS.
    Returns None if nothing works.
    """
    for raw in strings:
        text = raw.strip().replace("|", " ")

        # -- 1. direct: pyproj quick parse ------------------------------------
        try:
            return CRS.from_user_input(text)
        except exceptions.CRSError:
            pass
       
        # -- 3. hard-coded MGA / AMG rule-set ---------------------------------
        m = _ZONE_RX.search(text)
        if m:
            zone = int(m.group(2))
            if 46 <= zone <= 59:
                for datum, base in _MGA_BASES.items():
                    if datum in text.upper():          # datum keyword match
                        return CRS.from_epsg(base + zone)

    return None
