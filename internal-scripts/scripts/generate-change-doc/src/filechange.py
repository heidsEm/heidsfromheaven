import json
import os
from typing import List, Dict, Optional
from pathlib import Path
import re


# Define recognized file types and their metadata
RECOGNIZED_FILE_TYPES = {
    "config.json": {
        "objectType": "AZURE_CONFIG",
        "objectName": "config.json",
    },
    "policies/api.xml": {
        "objectType": "AZURE_POLICY",
        "objectName": "api.xml",
    },
}


def classify_file(file_path: str) -> Dict:
    """
    Classify a given file path into a recognized type or UNKNOWN.

    Args:
        file_path: The path of the file to classify.

    Returns:
        A dictionary with classification details.
    """
    normalized_path = file_path.replace("\\", "/")  # Normalize for cross-platform compatibility

    # Exact match check
    if normalized_path in RECOGNIZED_FILE_TYPES:
        metadata = RECOGNIZED_FILE_TYPES[normalized_path]
        return {
            "objectType": metadata["objectType"],
            "objectName": metadata["objectName"],
            "files": [{"name": file_path}],
            "remarks": [],
        }

    # Add pattern-based recognition here if needed, e.g.:
    # if re.match(r"^some/pattern/.*\.xml$", normalized_path):
    #     return { ... }

    # Default unknown
    return {
        "objectType": "UNKNOWN",
        "objectName": file_path,
        "files": [{"name": file_path}],
        "remarks": ["Unrecognized file type"],
    }


def process_file_list(changed_files: List[str], verbose: bool = False) -> Dict[str, List[Dict]]:
    """
    Process a list of changed file paths, classifying each.

    Args:
        changed_files: List of file paths as strings.
        verbose: If True, print debug information.

    Returns:
        A dictionary with 'valid_file_list' and 'skip_file_list'.
    """
    result = {"valid_file_list": [], "skip_file_list": []}

    for file_path in changed_files:
        entry = classify_file(file_path)
        if verbose:
            print(f"Classifying '{file_path}': {entry['objectType']}")
        if entry["objectType"] == "UNKNOWN":
            result["skip_file_list"].append(entry)
        else:
            result["valid_file_list"].append(entry)

    return result


def main():
    """
    Main execution function:
    - Reads the 'changed_file_list' env var (JSON list of files)
    - Processes classification
    - Saves output JSON to disk
    """
    changed_file_list = os.getenv("changed_file_list")

    if not changed_file_list:
        print("❌ Environment variable 'changed_file_list' is not set.")
        return

    try:
        changed_files = json.loads(changed_file_list)
        if not isinstance(changed_files, list):
            raise ValueError("Expected a list of file paths.")
    except (json.JSONDecodeError, ValueError) as err:
        print(f"❌ Failed to parse 'changed_file_list': {err}")
        return

    result = process_file_list(changed_files, verbose=True)

    output_path = Path(__file__).parent.parent / "test" / "processed_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print(f"✅ Processed output saved to: {output_path}")
    except IOError as e:
        print(f"❌ Failed to write output file: {e}")


if __name__ == "__main__":
    main()
