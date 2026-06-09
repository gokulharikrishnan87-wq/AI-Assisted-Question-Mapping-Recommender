#!/usr/bin/env python3
"""Convert SLCP Excel to JSON format with parent questions."""

import openpyxl
import json

# Load the Excel file
print("Loading Excel file...")
wb = openpyxl.load_workbook('/Users/manju_na/Downloads/slcp_data_dictionary (1).xlsx', data_only=True)
ws = wb.active

# Build data dictionary
data = {}
parent_questions = {}  # Store parent questions separately

for row in ws.iter_rows(min_row=2, values_only=True):
    if not any(row):
        continue

    # Extract fields
    key = row[0]
    number = row[1]
    section = row[2]
    subsection = row[3]
    category = row[4]
    question = row[5]
    question_type = row[6] if len(row) > 6 else None
    parent_key = row[11] if len(row) > 11 else None

    if not key or not question:
        continue

    # Store in data dictionary
    data[key] = {
        "key": key,
        "number": number,
        "section": section,
        "subsection": subsection,
        "category": category,
        "question": question,
    }

    # Track parent questions
    if parent_key:
        data[key]["parent_key"] = parent_key

    # If this looks like a parent question (no dash in number after prefix)
    # Store it separately for easy lookup
    if number and '-' not in number.split('-', 1)[-1]:  # e.g., MS-PLA-16 has no sub-number
        parent_questions[number] = {
            "key": key,
            "question": question
        }

# Save to JSON
output_file = 'slcp_data_dictionary_new.json'
with open(output_file, 'w') as f:
    json.dump(data, f, indent=2)

print(f"✅ Saved {len(data)} questions to {output_file}")
print(f"✅ Found {len(parent_questions)} parent questions")

# Show example parent
if 'MS-PLA-16' in parent_questions:
    p = parent_questions['MS-PLA-16']
    print(f"\nExample parent: MS-PLA-16")
    print(f"  Key: {p['key']}")
    print(f"  Question: {p['question'][:100]}...")
