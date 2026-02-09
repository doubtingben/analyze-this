#!/usr/bin/env python3
import argparse
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import firebase_admin
from firebase_admin import firestore



SYNONYM_MAP = {
    "ai": "artificial intelligence",
    "ml": "machine learning",
    "machine-learning": "machine learning",
    "llm": "large language models",
    "llms": "large language models",
    "ux": "user experience",
    "ui": "user interface",
    "product": "product management",
    "pm": "product management",
    "meetup": "meeting",
    "mtg": "meeting",
    "doc": "documentation",
    "docs": "documentation",
}


def normalize_tag(tag: str) -> str:
    base = tag.strip().lower()
    base = re.sub(r"[_/]+", " ", base)
    base = re.sub(r"[-]+", " ", base)
    base = re.sub(r"\s+", " ", base).strip()
    base = SYNONYM_MAP.get(base, base)

    if len(base) > 3 and base.endswith("s") and not base.endswith("ss"):
        base = base[:-1]
    return base


def canonicalize_tag(group: List[str]) -> str:
    counts = Counter(group)
    most_common = counts.most_common(1)[0][0]
    canonical = most_common.strip()
    if canonical.isupper() or canonical.islower():
        canonical = canonical.title()
    return canonical


def extract_tags(item: dict) -> List[str]:
    analysis = item.get("analysis") or {}
    tags = analysis.get("tags")
    if not tags or not isinstance(tags, list):
        return []
    return [str(tag).strip() for tag in tags if str(tag).strip()]


def build_consolidation_map(tags: List[str]) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    groups = defaultdict(list)
    for tag in tags:
        key = normalize_tag(tag)
        if key:
            groups[key].append(tag)

    consolidated_map = {}
    group_details = {}
    for key, originals in groups.items():
        canonical = canonicalize_tag(originals)
        consolidated_map[key] = canonical
        group_details[canonical] = sorted(set(originals))

    return consolidated_map, group_details


def main() -> None:
    parser = argparse.ArgumentParser(description="Consolidate analysis tags and update items + prompt.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write updates.")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of items processed (0 = all).")
    parser.add_argument("--output", type=str, default="tag-consolidation.json", help="Output JSON mapping file.")

    args = parser.parse_args()

    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    db = firestore.client()

    query = db.collection("shared_items")
    items = []
    for idx, doc in enumerate(query.stream()):
        items.append((doc.id, doc.to_dict()))
        if args.limit and idx + 1 >= args.limit:
            break

    all_tags = []
    for _, data in items:
        all_tags.extend(extract_tags(data))

    consolidation_map, group_details = build_consolidation_map(all_tags)
    canonical_tags = sorted(group_details.keys(), key=str.lower)

    output = {
        "canonical_tags": canonical_tags,
        "groups": group_details
    }

    Path(args.output).write_text(json.dumps(output, indent=2))

    if not items:
        print("No items found.")
        return

    if args.dry_run:
        print(f"[dry-run] Would update {len(items)} items.")
        return

    batch = db.batch()
    batch_count = 0
    updated = 0

    for doc_id, data in items:
        tags = extract_tags(data)
        if not tags:
            continue
        new_tags = []
        for tag in tags:
            key = normalize_tag(tag)
            canonical = consolidation_map.get(key)
            if canonical:
                new_tags.append(canonical)
        new_tags = sorted(set(new_tags), key=str.lower)

        if not new_tags:
            continue

        analysis = data.get("analysis") or {}
        if analysis.get("tags") == new_tags:
            continue
        analysis["tags"] = new_tags
        batch.update(db.collection("shared_items").document(doc_id), {"analysis": analysis})
        updated += 1
        batch_count += 1

        if batch_count >= 400:
            batch.commit()
            batch = db.batch()
            batch_count = 0

    if batch_count:
        batch.commit()

    print(f"Updated {updated} items. Consolidated tag list has {len(canonical_tags)} tags.")


if __name__ == "__main__":
    main()
