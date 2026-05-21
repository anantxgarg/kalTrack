"""Nutrition lookups — resolves food items to calorie counts.

Lookup sources (in order of preference per route):
  1. IFCT 2017 CSV     → local in-memory search for raw ingredients
  2. Open Food Facts   → remote API for packaged food + barcode lookups
  3. LLM Fallback      → Groq/Llama estimation (when all else misses)
"""

import csv
import json
import os
import re
from llm import RoutedItem
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# --- IFCT 2017 local dataset ---
IFCT_CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "ifct2017.csv")
_ifct_data: list[dict] | None = None

# --- Groq client for LLM fallback ---
_groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


def _load_ifct():
    """Load IFCT 2017 CSV into memory (once). Returns list of dicts."""
    global _ifct_data
    if _ifct_data is not None:
        return _ifct_data

    _ifct_data = []
    try:
        with open(IFCT_CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    energy_kj = float(row.get("enerc", 0))
                except (ValueError, TypeError):
                    energy_kj = 0
                _ifct_data.append({
                    "code": row.get("code", ""),
                    "name": row.get("name", ""),
                    "lang": row.get("lang", ""),
                    "scie": row.get("scie", ""),
                    "grup": row.get("grup", ""),
                    "energy_kj": energy_kj,
                    "energy_kcal": round(energy_kj / 4.184),
                })
    except FileNotFoundError:
        print(f"Warning: IFCT CSV not found at {IFCT_CSV_PATH}")
        _ifct_data = []

    return _ifct_data


def _tokenize(text: str) -> set[str]:
    """Split text into lowercase word tokens, stripping punctuation."""
    return set(re.findall(r'[a-z]+', text.lower()))


def _search_ifct(query: str) -> int | None:
    """Search IFCT dataset for a food item. Returns kcal per 100g or None."""
    data = _load_ifct()
    query_lower = query.lower().strip()
    query_words = _tokenize(query)

    if not query_words:
        return None

    # Try exact match on name first
    for item in data:
        if item["name"].lower() == query_lower:
            return item["energy_kcal"]

    # Word-level matching on name:
    # Score = fraction of query words found in the item name
    # e.g. "Milk, Cow" (words: {milk, cow}) vs "Milk, whole, Cow" → 2/2 = 1.0
    best_match = None
    best_score = 0
    for item in data:
        name_words = _tokenize(item["name"])
        if not name_words:
            continue
        # How many query words appear in this item's name?
        overlap = len(query_words & name_words)
        if overlap == 0:
            continue
        # Score: high when all query words match, penalize overly broad names
        query_coverage = overlap / len(query_words)        # what % of query is matched
        name_specificity = overlap / len(name_words)       # how specific is the match
        score = (query_coverage * 0.7) + (name_specificity * 0.3)
        if score > best_score:
            best_score = score
            best_match = item

    if best_match and best_score > 0.5:
        return best_match["energy_kcal"]

    # Also try substring match (handles single-word queries like "banana")
    for item in data:
        name_lower = item["name"].lower()
        if query_lower in name_lower or name_lower in query_lower:
            return item["energy_kcal"]

    # Try matching against local language names (Hindi, Tamil, etc.)
    for item in data:
        lang_lower = item["lang"].lower()
        if query_lower in lang_lower:
            return item["energy_kcal"]

    return None


def lookup_raw(item: RoutedItem) -> tuple[int, str]:
    """Look up raw ingredient: IFCT 2017 CSV → LLM Fallback."""
    from admin_config import is_ifct_disabled
    if is_ifct_disabled():
        print(f"Admin Config: IFCT lookup disabled. Directing '{item.normalized}' to LLM estimate.")
        return llm_estimate(item)

    # 1. IFCT 2017 in-memory search
    result = _search_ifct(item.normalized)
    if result is not None:
        return result, "IFCT 2017"

    # Try stripping common qualifiers
    simplified = item.normalized.lower()
    for word in ["raw", "fresh", "whole", "ripe", "green", "dry", "dried"]:
        simplified = re.sub(rf'\b{word}\b', '', simplified).strip()
    if simplified != item.normalized.lower():
        result = _search_ifct(simplified)
        if result is not None:
            return result, "IFCT 2017"

    # 2. LLM Fallback
    return llm_estimate(item)


def lookup_packaged(item: RoutedItem) -> tuple[int, str]:
    """Look up packaged food: Open Food Facts text search API → LLM Fallback."""
    import httpx

    # 1. Open Food Facts text search API
    search_term = item.normalized
    if item.brand and item.brand.lower() not in search_term.lower():
        search_term = f"{item.brand} {search_term}"
    try:
        response = httpx.get(
            "https://world.openfoodfacts.org/cgi/search.pl",
            params={"search_terms": search_term, "json": 1, "page_size": 3,
                    "fields": "product_name,nutriments"},
            headers={"User-Agent": "KalTrack/1.0"},
            timeout=10.0,
        )
        if response.status_code == 503:
            print(f"Open Food Facts 503 for '{item.normalized}', skipping")
        else:
            response.raise_for_status()
            for product in response.json().get("products", []):
                n = product.get("nutriments", {})
                # Always prefer the explicit kcal field to avoid kJ confusion
                kcal = n.get("energy-kcal_100g")
                if kcal and float(kcal) > 0:
                    return round(float(kcal)), "Open Food Facts"
                # energy_100g is sometimes kJ — only use if energy-kcal_100g is absent
                energy = n.get("energy_100g")
                if energy and float(energy) > 0 and not n.get("energy-kcal_100g"):
                    return round(float(energy) / 4.184), "Open Food Facts (kJ→kcal)"
    except Exception as e:
        print(f"Open Food Facts lookup failed for '{item.normalized}': {e}")

    # 2. LLM Fallback
    return llm_estimate(item)


def lookup_barcode(item: RoutedItem) -> tuple[int, str]:
    """Look up by barcode: Open Food Facts v2 API."""
    import httpx

    barcode = item.normalized.strip()

    try:
        response = httpx.get(
            f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json",
            headers={"User-Agent": "KalTrack/1.0"},
            timeout=8.0,
        )
        if response.status_code == 503:
            print(f"Open Food Facts barcode 503 for '{barcode}'")
        elif response.status_code == 404:
            raise ValueError(f"Barcode {barcode} not found in database.")
        else:
            response.raise_for_status()
            data = response.json()
            if data.get("status") == 1:
                product = data.get("product", {})
                product_name = product.get("product_name")
                if product_name:
                    item.normalized = product_name
                    
                n = product.get("nutriments", {})
                kcal_100g = n.get("energy-kcal_100g")
                if kcal_100g and float(kcal_100g) > 0:
                    return round(float(kcal_100g)), "Open Food Facts (Barcode)"
                kcal_serving = n.get("energy-kcal_serving")
                if kcal_serving and float(kcal_serving) > 0:
                    return round(float(kcal_serving)), "Open Food Facts (Barcode)"
                energy_100g = n.get("energy_100g")
                if energy_100g and float(energy_100g) > 0:
                    return round(float(energy_100g) / 4.184), "Open Food Facts (Barcode, kJ)"
            else:
                raise ValueError(f"Barcode {barcode} not found in database.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise ValueError(f"Barcode {barcode} not found in database.")
        print(f"Barcode lookup failed for '{barcode}': {e}")
    except ValueError:
        raise
    except Exception as e:
        print(f"Barcode lookup failed for '{barcode}': {e}")

    raise ValueError(f"Could not find nutritional info for barcode {barcode}.")


def llm_estimate(item: RoutedItem) -> tuple[int, str]:
    """Estimate calories using LLM. Called when IFCT + Open Food Facts all miss."""
    prompt = f"""You are a nutrition expert specializing in Indian food and cuisine.
Estimate the calories for: "{item.qty} × {item.normalized}"

Use Indian portion sizes, cooking methods, and regional context.

Respond ONLY with valid JSON:
{{"calories_per_unit": <number>}}

Where calories_per_unit is the calories for exactly ONE unit/serving of {item.normalized}.
Do not include any explanation, only JSON.
"""
    try:
        response = _groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        cal = result.get("calories_per_unit", 0)
        return (round(cal) if cal else 0), "LLM Estimate"
    except Exception as e:
        print(f"LLM estimate failed for '{item.normalized}': {e}")
        return 0, "LLM Estimate (Failed)"


def resolve_calories(item: RoutedItem) -> tuple[int, str]:
    """Dispatch to the appropriate lookup based on the item's route."""
    match item.route:
        case "raw_ingredient":
            return lookup_raw(item)
        case "packaged":
            return lookup_packaged(item)
        case "barcode":
            return lookup_barcode(item)
        case "restaurant" | "llm_estimate" | _:
            # Restaurant items and cooked dishes go straight to LLM estimation
            # (no more CalorieNinjas or local restaurant DB)
            return llm_estimate(item)
