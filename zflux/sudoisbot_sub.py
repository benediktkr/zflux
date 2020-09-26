def to_influx_fmt(data):

    print(data)
    if not data['type'] == 'temp':
        return data
    if "fields" in data and "tags" in data:
        return data
    return {"measurement": "test", # toopic!
            "tags": {"test": "yes"},
            "time": data['timestamp'],
            "fields": data}
