import os
import json
import re
from datetime import datetime
from typing import List, Dict, Tuple
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm

# Environment Variables
PROCESSED_FILES = os.environ.get("PROCESSED_FILES", "{}")
REPOSITORY_NAME = os.environ.get("REPOSITORY_NAME", "")
PR_NUMBER = os.environ.get("PR_NUMBER", "")
PR_AUTHOR = os.environ.get("PR_AUTHOR", "")

# Policy reference list
POLICY_REFERENCE_MAP = {
    "allowedIps": "IP Whitelist Policy",
    "queryparmregexp": "RegEx Policy",
    "rate-limit-by-key": "SpikeArrest",
    "quota-by-key": "Quota",
    "set-variable": "Variable Assignment",
    "set-header": "Header Control",
    "authentication-basic": "Basic Auth",
    "return-response": "Manual Response",
    "set-backend-service": "Backend Override",
    "forward-request": "Forward Request",
    "choose": "Conditional Logic",
}

# Logging utility
def log(message: str, level: str = "INFO") -> None:
    print(f"[{level}] {datetime.now().isoformat()} - {message}")

# Determine base URL for API
def determine_api_url(repo_name: str) -> str:
    if "EAI-APIM-Ent" in repo_name:
        return "https://InternalAPI.pg.com"
    elif "EAI-APIM-Ext" in repo_name:
        return "https://API.pgcloud.com"
    elif "EAI-APIM-Con" in repo_name:
        return "https://CSAPI.com"
    return "https://Unknown"

# Extract policy tags from XML
def extract_policy_blocks(xml_path: str) -> Tuple[List[Dict[str, str]], List[str]]:
    try:
        with open(xml_path, "r", encoding="utf-8") as f:
            xml = f.read()

        sections = re.findall(r"<(inbound|outbound|backend|on-error)>(.*?)</\1>", xml, re.DOTALL | re.IGNORECASE)
        policy_blocks = []
        tag_set = set()

        for section_name, content in sections:
            matches = re.findall(r"<([a-zA-Z0-9\-_]+)([\s\S]*?)(/>|>[\s\S]*?</\1>)", content, re.DOTALL)
            for tag, inner, closer in matches:
                full_block = f"<{tag}{inner}{closer}"
                policy_blocks.append({
                    "name": tag,
                    "content": full_block.strip()
                })
                tag_set.add(tag)

        return policy_blocks, sorted(tag_set)

    except Exception as e:
        log(f"Failed to parse XML policies: {e}", "ERROR")
        return [], []

# Extract named values and API metadata
def extract_named_values(config_path: str) -> Tuple[List[Dict[str, str]], List[str], Dict[str, str]]:
    kvm_entries = []
    whitelist = []
    metadata = {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            named_values = config.get("named_values", {})

            for key, val in named_values.items():
                value = val.get("value", "")
                kvm_entries.append({"file_name": key, "kvm_entry": value})
                if key in ["allowed-ips", "allowed-cidrs"] and isinstance(value, str):
                    whitelist.extend(x.strip() for x in value.split(",") if x.strip())

            api = config.get("api", {})
            metadata = {
                "api_name": api.get("name", ""),
                "api_basepath": api.get("path", ""),
                "api_backend": api.get("service_url", ""),
                "ritm_number": api.get("ritm_number", "")
            }

    except Exception as e:
        log(f"Failed to read config: {e}", "ERROR")

    return kvm_entries, whitelist or ["None"], metadata

# Extract product IDs from config
def extract_product_ids(config_path: str) -> List[str]:
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            value = config.get("product", {}).get("product_id", [])
            if isinstance(value, str):
                return [value]
            return value if isinstance(value, list) else []
    except Exception as e:
        log(f"Failed to read product_id: {e}", "ERROR")
        return []

# Build policy summary list
def build_policy_summary(tags: List[str]) -> List[Dict[str, str]]:
    return [
        {"tag": tag, "label": POLICY_REFERENCE_MAP.get(tag, tag.replace("-", " ").title())}
        for tag in tags
    ]

# Safely update context dictionary
def safe_update_context(context: dict, updates: dict) -> None:
    for key, value in updates.items():
        if key in context and value:
            context[key] = value

# Process values from changed files
def process_values(processed_files: dict) -> dict:
    context = {
        "api_name": "",
        "api_basepath": "",
        "api_backend": "",
        "ritm_number": "",
        "version_number": 1,
        "developer_name": PR_AUTHOR,
        "pr_date": datetime.today().strftime("%B %d, %Y"),
        "pr_url": f"https://github.com/{REPOSITORY_NAME}/pull/{PR_NUMBER}",
        "platform": "Azure API Management",
        "api_region": "ASIA, US, EU",
        "api_url": determine_api_url(REPOSITORY_NAME),
        "kvm_list": [],
        "api_whitelist": [],
        "product_list": [],
        "api_target_list": [],
        "policy_summary": [],
        "api_policy_list": [],
        "data_diagram": None,
    }

    for entry in processed_files:
        for file in entry.get("files", []):
            path = file.get("name", "")

            if path.endswith("config.json"):
                kvms, ips, meta = extract_named_values(path)
                context["kvm_list"].extend(kvms)
                context["api_whitelist"].extend(ips)
                safe_update_context(context, meta)
                context["product_list"].extend(extract_product_ids(path))

            elif path.endswith("policies/api.xml"):
                policies, tags = extract_policy_blocks(path)
                context["api_target_list"].extend(policies)
                context["policy_summary"] = build_policy_summary(tags)

                friendly_names = sorted(set(
                    POLICY_REFERENCE_MAP.get(tag, tag.replace("-", " ").title()) for tag in tags
                ))
                context["api_policy_list"] = [{"name": name} for name in friendly_names]

    # Deduplicate list entries
    context["api_whitelist"] = sorted(set(context["api_whitelist"]))
    context["product_list"] = sorted(set(context["product_list"]))

    return context

# Validate paths before document generation
def validate_paths(template_path: str, output_path: str) -> None:
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"❌ Template not found: {template_path}")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

# Generate document from template
def create_document_from_template(template_path: str, output_path: str, context: dict) -> None:
    doc = DocxTemplate(template_path)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    diagram_path = os.path.join(base_dir, "../templates/azureapim_architecture.drawio.png")
    if os.path.exists(diagram_path):
        context["data_diagram"] = InlineImage(doc, diagram_path, width=Mm(140))
    doc.render(context)
    doc.save(output_path)
    log(f"✅ Document generated at: {output_path}")

# Main function
def main() -> None:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(base_dir, "../templates", "DevOpsChangeRequest_Documentation_Template.docx")
    output_path = os.path.join(base_dir, "../output", "DevOpsChangeRequest_Documentation.docx")

    validate_paths(template_path, output_path)

    try:
        processed_files = json.loads(PROCESSED_FILES).get("valid_file_list", [])
    except json.JSONDecodeError:
        processed_files = []
        log("⚠️ Invalid JSON in PROCESSED_FILES environment variable.", "WARN")

    context = process_values(processed_files)
    create_document_from_template(template_path, output_path, context)

if __name__ == "__main__":
    try:
        log("🚀 Starting documentation generation...")
        main()
    except Exception as e:
        log(f"❌ Unhandled exception: {e}", "ERROR")
