import logging

import requests

logger = logging.getLogger(__name__)

LOOKUP_TIMEOUT_SECONDS = 5
OPEN_FOOD_FACTS_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"


def lookup_barcode(barcode):
    """Looks up a scanned barcode against the free Open Food Facts database.

    Returns a dict of whatever fields were found (name/brand/description/
    image_url may each be missing) or None if the barcode isn't in the
    database. Never raises: a slow or unreachable external API must not be
    able to break product entry, so network/parse failures are swallowed
    and treated the same as "not found".
    """
    try:
        response = requests.get(
            OPEN_FOOD_FACTS_URL.format(barcode=barcode),
            timeout=LOOKUP_TIMEOUT_SECONDS,
            headers={"User-Agent": "isAndrewsGrocery/1.0 (product entry lookup)"},
        )
        response.raise_for_status()
        data = response.json()
    except Exception:
        logger.warning("Barcode lookup failed for %s", barcode, exc_info=True)
        return None

    if data.get("status") != 1:
        return None

    product = data.get("product", {})
    name = product.get("product_name") or product.get("product_name_en")
    if not name:
        return None

    return {
        "name": name,
        "brand": product.get("brands", "").split(",")[0].strip() or None,
        "description": product.get("generic_name") or None,
        "image_url": product.get("image_front_url") or product.get("image_url") or None,
    }
