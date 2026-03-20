import os
import json

CONFIG_DIR  = os.path.join(os.path.dirname(__file__), "../config")
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "../reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

def load(filename):
    with open(os.path.join(CONFIG_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


def get_questions_flat():
    blocs = load("questions.json")["blocs"]
    result = []
    for bloc in blocs:
        for q in bloc["questions"]:
            result.append({**q, "_bloc_id": bloc["id"]})
    return result
