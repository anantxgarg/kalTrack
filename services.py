import json, os
from groq import Groq
from dotenv import load_dotenv
from storage import get_device_data, save_device_data, get_device_config, save_device_config, today_key

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


def log_food_service(text: str, device_id: str):
    prompt = f"""You are a nutrition expert specializing in Indian food and cuisine.
The user ate: "{text}"

Parse this into individual food items with quantities and estimate calories for each.
Use Indian portion sizes, cooking methods, and regional context.

Respond ONLY with valid JSON in this exact format:
{{
  "items": [
    {{"item": "roti", "qty": 2, "calories_per_unit": 104}},
    {{"item": "dal tadka", "qty": 1, "calories_per_unit": 198}}
  ],
  "identified": true
}}

If you cannot identify any food at all, respond with:
{{"items": [], "identified": false}}

Rules:
- "item" must be a clean lowercase name
- "qty" is a number, default 1 if not specified
- "calories_per_unit" is calories for exactly ONE unit or serving
- Do not include any explanation, only JSON
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
    except Exception as e:
        raise Exception(f"LLM error: {str(e)}")

    if not result.get("identified") or not result.get("items"):
        raise ValueError("Could not identify any food items. Please try again.")

    data = get_device_data(device_id)
    today = today_key()

    if today not in data:
        data[today] = {}

    for entry in result["items"]:
        item = entry["item"]
        cal = entry["calories_per_unit"]
        qty = entry["qty"]

        if item in data[today]:
            data[today][item]["count"] += qty
        else:
            data[today][item] = {"calories": cal, "count": qty}

    save_device_data(device_id, data)

    total_added = sum(e["calories_per_unit"] * e["qty"] for e in result["items"])

    return {
        "items": result["items"],
        "total_added": round(total_added),
        "today": data[today]
    }


def get_today_service(device_id: str):
    data = get_device_data(device_id)
    today = today_key()
    config = get_device_config(device_id)

    today_data = data.get(today, {})
    total = sum(v["calories"] * v["count"] for v in today_data.values())

    return {
        "date": today,
        "log": today_data,
        "total": round(total),
        "target": config["target"]
    }


def update_target_service(target: int, device_id: str):
    config = get_device_config(device_id)
    config["target"] = target
    save_device_config(device_id, config)
    return {"target": target}


def reset_today_service(device_id: str):
    data = get_device_data(device_id)
    data[today_key()] = {}
    save_device_data(device_id, data)
    return {"message": "Today's log cleared"}