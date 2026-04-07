import re
from collections import Counter
from text2digits import text2digits

t2d = text2digits.Text2Digits()


def preprocess(text: str) -> list:
    text = text.lower()
    text = t2d.convert(text)

    text = re.sub(r'(\d+)\s*x', r'\1', text)
    text = re.sub(r'x\s*(\d+)', r'\1', text)

    text = text.replace(",", " and ")
    text = re.sub(r'[^\w\s]', ' ', text)

    return text.split()


def extract_items(tokens: list) -> list:
    segments = []
    current = []

    for token in tokens:
        if token == "and":
            if current:
                segments.append(current)
                current = []
            continue

        if token.isdigit() and current and any(t.isdigit() for t in current):
            segments.append(current)
            current = [token]
        else:
            current.append(token)

    if current:
        segments.append(current)

    results = {}

    for segment in segments:
        numbers = [int(t) for t in segment if t.isdigit()]
        words = [t for t in segment if not t.isdigit()]

        if not words:
            continue

        qty = numbers[0] if numbers else 1

        counts = Counter(words)

        if len(words) == 1:
            item = words[0]
            results[item] = results.get(item, 0) + qty
        else:
            item = " ".join(words)
            results[item] = results.get(item, 0) + qty

    return [
        {"item": item, "quantity": qty}
        for item, qty in results.items()
    ]


def parse_order(text: str) -> list:
    """Main entry point"""
    return extract_items(preprocess(text))