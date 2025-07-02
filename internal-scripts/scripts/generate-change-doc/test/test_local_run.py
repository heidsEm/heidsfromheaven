import os
import subprocess
import json

def test_run():
    # Simulate changed files
    changed_files = ["config.json", "policies/api.xml"]
    test_dir = os.path.dirname(__file__)
    changed_file_path = os.path.join(test_dir, "changed_files.json")
    
    with open(changed_file_path, "w") as f:
        json.dump(changed_files, f)

    env = os.environ.copy()
    env["changed_file_list"] = json.dumps(changed_files)
    env["github_branch_name"] = "main"
    env["github_repository_name"] = "heidi-org/sample-api"

    # Run filechange.py
    subprocess.run([
        "python", os.path.join("..", "src", "filechange.py")
    ], env=env, check=True)

    # Read processed result
    with open(os.path.join(test_dir, "processed_output.json"), "r") as f:
        env["PROCESSED_FILES"] = f.read()

    # Set other required environment variables
    env["REPOSITORY_NAME"] = "heidi-org/sample-api"
    env["PR_NUMBER"] = "123"
    env["PR_AUTHOR"] = "heidi.embat"

    # Run change_doc.py
    subprocess.run([
        "python", os.path.join("..", "src", "change_doc.py")
    ], env=env, check=True)

if __name__ == "__main__":
    test_run()
