import json
import os
from datetime import datetime

def save_item(data, path="wishlist.json"):
    wishlist = []

    # Safely read existing wishlist
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                contents = f.read().strip()
                if contents:
                    wishlist = json.loads(contents)
        except json.JSONDecodeError:
            print("⚠️ Warning: wishlist.json is corrupted. Starting fresh.")

    # Add timestamp and append the new item
    data["timestamp"] = datetime.now().isoformat()
    wishlist.append(data)

    # Save back to JSON
    with open(path, "w") as f:
        json.dump(wishlist, f, indent=2)
