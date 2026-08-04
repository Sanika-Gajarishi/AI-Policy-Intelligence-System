def add_metadata(chunks, state, year, month, power_type, source_file=None):
    docs = []

    for chunk in chunks:
        docs.append({
            "text": chunk,
            "state": state,
            "year": year,
            "month": month,
            "power_type": power_type,
            "source_file": source_file
        })

    return docs