"""Geographic distance + hop classification helpers."""
import math

EARTH_RADIUS_KM = 6371.0

def haversine_km(lat1, lng1, lat2, lng2):
    """Great-circle distance in km between two lat/lng points."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))

def classify_hop(mins, max_hop_mins=60):
    """Classify an inter-POI travel time. <= threshold is 'ok', else 'far'."""
    return "ok" if mins <= max_hop_mins else "far"
