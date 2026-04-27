"""LLM Router — parses user input into structured food items with routing info.

The LLM's job is ONLY to understand natural language and classify items.
It does NOT estimate calories (that's done by the database lookups).
"""

import json
import os
from dataclasses import dataclass
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


@dataclass
class RoutedItem:
    normalized: str     # "McSpicy Chicken Burger"
    brand: str | None   # "McDonald's" or None
    qty: int            # 1
    route: str          # "restaurant" | "packaged" | "raw_ingredient" | "barcode" | "llm_estimate"


ROUTER_PROMPT = """You are a nutrition expert and food intake parser specializing in Indian food and cuisine.
The user ate: "{text}"

Split into individual food items. For each item output:
- "normalized": clean common name, properly capitalized
  (e.g. "McSpicy Chicken Burger", "French Fries", "Diet Coke", "Banana", "Maggi Masala Noodles", "Roti", "Bajra")
- "brand": restaurant or brand name if mentioned, else null
  (e.g. "McDonald's", "KFC", "Lays", null)
- "qty": numeric quantity, default 1
- "route": exactly one of:
    "restaurant"     → named fast food chain or restaurant brand (McDonald's, KFC, Domino's, Burger King, Subway, Pizza Hut, Starbucks, etc.)
    "packaged"       → packaged/branded product (chips, biscuits, instant noodles, soft drinks, energy drinks, etc.)
    "raw_ingredient" → unprocessed whole food (fruit, vegetable, egg, milk, rice, dal, atta, ghee, paneer, etc.)
    "barcode"        → input is a pure numeric product barcode / EAN / UPC code (e.g. 8901023006495, 012345678901). Set normalized to the barcode digits only.
    "llm_estimate"   → home-cooked dishes, Indian regional food, or unclear items (dal tadka, rajma chawal, biryani, dosa, etc.)

Use Indian portion sizes, cooking methods, and regional context.
Recognize Hindi, Tamil, Telugu, Kannada, Bengali, and other regional food names.
Respond ONLY with valid JSON in this exact format:
{{
  "items": [
    {{"normalized": "McSpicy Chicken Burger", "brand": "McDonald's", "qty": 1, "route": "restaurant"}},
    {{"normalized": "French Fries", "brand": "McDonald's", "qty": 1, "route": "restaurant"}},
    {{"normalized": "Pepsi", "brand": null, "qty": 1, "route": "packaged"}}
  ]
}}

If you cannot identify any food at all, respond with:
{{"items": []}}
"""


def route_items(text: str) -> list[RoutedItem]:
    """Parse user input into a list of routed food items using the LLM."""
    prompt = ROUTER_PROMPT.format(text=text)

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        response_format={"type": "json_object"}
    )

    result = json.loads(response.choices[0].message.content)
    items = result.get("items", [])

    routed = []
    for item in items:
        # Validate route
        route = item.get("route", "llm_estimate")
        if route not in ("restaurant", "packaged", "raw_ingredient", "barcode", "llm_estimate"):
            route = "llm_estimate"

        normalized = str(item.get("normalized", "unknown")).strip()
        
        # Force barcode route for long numeric strings to prevent hallucination
        if normalized.isdigit() and len(normalized) >= 8:
            route = "barcode"

        routed.append(RoutedItem(
            normalized=normalized,
            brand=item.get("brand"),
            qty=max(1, int(item.get("qty", 1))),
            route=route
        ))

    return routed
