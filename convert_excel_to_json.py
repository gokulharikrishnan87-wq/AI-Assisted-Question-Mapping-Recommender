#!/usr/bin/env python3
"""Convert the new SLCP Excel file to JSON with parent questions."""

import sys
sys.path.insert(0, 'src')

import json
from mapper_copilot.ingestion.excel_loader import load_slcp_data_dictionary

# Load the new Excel file
print("Loading Excel file...")
questions, metadata = load_slcp_data_dictionary('/Users/manju_na/Downloads/slcp_data_dictionary (1).xlsx')

print(f"Loaded {len(questions)} questions")

# Check for parent question
parent_found = False
for key, meta in metadata.items():
    if meta.get('number') == 'MS-PLA-16':
        print(f"\n✅ Found parent question MS-PLA-16:")
        print(f"   Question: {questions[key][:200]}")
        parent_found = True
        break

if not parent_found:
    print("\n❌ Parent question MS-PLA-16 not found")

# Build combined data structure
combined_data = {}
for key in questions.keys():
    combined_data[key] = {
        **metadata[key],
        "question": questions[key]
    }

# Save to new JSON file
output_file = 'slcp_data_dictionary_new.json'
with open(output_file, 'w') as f:
    json.dump(combined_data, f, indent=2)

print(f"\n✅ Saved to {output_file}")
print(f"   Total entries: {len(combined_data)}")
