from plans.schema import Plan


def load_plan(path: str) -> Plan:
    with open(path, "r", encoding="utf-8") as f:
        data = f.read()
    return Plan.model_validate_json(data)
