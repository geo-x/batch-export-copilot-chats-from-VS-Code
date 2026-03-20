#!/usr/bin/env python3
"""
Export Copilot chats from VS Code's storage for a specific project workspace.
Matches the project folder against workspace.json to find the exact workspace ID,
then exports only chats from that workspace.
"""

import json
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from urllib.parse import unquote

def find_workspace_id_for_folder(project_folder_path):
    """
    Find the VS Code workspace ID that corresponds to a specific project folder.
    
    Returns: (workspace_dir_path, folder_uri) or (None, None) if not found
    """
    project_path = Path(project_folder_path).resolve()
    workspace_storage = Path.home() / "Library/Application Support/Code/User/workspaceStorage"
    
    if not workspace_storage.exists():
        print(f"Error: {workspace_storage} not found", file=sys.stderr)
        return None, None
    
    for workspace_dir in sorted(workspace_storage.iterdir()):
        if not workspace_dir.is_dir():
            continue
        
        workspace_json = workspace_dir / "workspace.json"
        if not workspace_json.exists():
            continue
        
        try:
            with open(workspace_json) as f:
                data = json.load(f)
                folder_uri = data.get("folder", "")
                
                # Decode URL encoding
                decoded_uri = unquote(folder_uri)
                
                # Remove file:// prefix for comparison
                if decoded_uri.startswith("file://"):
                    decoded_uri = decoded_uri[7:]
                
                # Compare paths
                if str(project_path) == decoded_uri:
                    return workspace_dir, folder_uri
        except Exception as e:
            continue
    
    return None, None


def find_chat_sessions_in_workspace(workspace_dir):
    """Find all chat sessions in a specific workspace directory."""
    chats = []
    chats_by_id = {}  # Track which chat IDs we've processed
    
    chat_sessions_dir = workspace_dir / "chatSessions"
    if not chat_sessions_dir.exists():
        return chats
    
    # First, process JSON files (snapshots with complete data - primary source)
    for chat_file in sorted(chat_sessions_dir.glob("*.json")):
        # Skip non-chat files like workspace.json
        if chat_file.name == "workspace.json":
            continue
        
        try:
            chat_list = parse_json_file(chat_file)
            chats.extend(chat_list)
            # Track which session IDs we've seen
            for chat in chat_list:
                session_id = chat.get("sessionId")
                if session_id:
                    chats_by_id[session_id] = chat_file.stem
        except Exception as e:
            continue
    
    # Then, process JSONL files only if we haven't already seen that session
    # in a JSON file (which is more complete and up-to-date)
    for chat_file in sorted(chat_sessions_dir.glob("*.jsonl")):
        try:
            chat_list = parse_jsonl_file(chat_file)
            for chat in chat_list:
                session_id = chat.get("sessionId")
                # Only add if we haven't seen this session in a JSON file
                if session_id not in chats_by_id:
                    chats.append(chat)
                    chats_by_id[session_id] = chat_file.stem
        except Exception as e:
            continue
    
    return chats


def parse_json_file(filepath):
    """Parse a single JSON chat file."""
    chats = []
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            data = json.load(f)
            
            # Only include JSON files if they have meaningful content
            requests = data.get("requests", [])
            title = data.get("customTitle", "").strip()
            
            # Skip if it's just an empty shell (no title and no meaningful requests)
            # A meaningful request has actual user input, not just system messages
            has_meaningful_content = False
            if requests and len(requests) > 0:
                for req in requests:
                    if isinstance(req, dict):
                        # Check if it has actual content (value field) or meaningful structure
                        if req.get("value") or (req.get("requestId") and req.get("agent")):
                            has_meaningful_content = True
                            break
            
            # Include if has title or meaningful requests
            if not (title or has_meaningful_content):
                return chats
            
            # Extract info from JSON snapshot
            chat_info = {
                "sessionId": data.get("sessionId"),
                "customTitle": title or "Untitled Chat",
                "creationDate": data.get("creationDate", 0),
                "filepath": str(filepath),
                "requests": requests
            }
            
            chats.append(chat_info)
    except json.JSONDecodeError as e:
        # Try to read with less strict encoding for corrupted files
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
                # Remove any problematic surrogate pairs
                content = content.encode('utf-8', 'replace').decode('utf-8', 'replace')
                data = json.loads(content)
                
                requests = data.get("requests", [])
                title = data.get("customTitle", "").strip()
                
                if requests and len(requests) > 0:
                    chat_info = {
                        "sessionId": data.get("sessionId"),
                        "customTitle": title or "Untitled Chat",
                        "creationDate": data.get("creationDate", 0),
                        "filepath": str(filepath),
                        "requests": requests
                    }
                    chats.append(chat_info)
        except Exception as inner_e:
            pass
    except Exception as e:
        pass
    
    return chats

def parse_jsonl_file(filepath):
    """Parse a JSONL chat file and extract requests/responses."""
    chats = []
    
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        state = {"customTitle": None, "requests": [], "projectPath": None}
        
        # First pass: read all lines
        lines = f.readlines()
    
    # Parse lines
    for line in lines:
        if not line.strip():
            continue
        
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        
        kind = obj.get("kind")
        
        # Extract initial state (kind 0) - contains COMPLETE initial requests array
        if kind == 0:
            if "v" in obj:
                v = obj["v"]
                if "customTitle" in v:
                    state["customTitle"] = v["customTitle"]
                if "sessionId" in v:
                    state["sessionId"] = v["sessionId"]
                if "creationDate" in v:
                    state["creationDate"] = v.get("creationDate")
                # IMPORTANT: Extract initial requests from kind=0
                # This contains the FULL request history at the start
                if "requests" in v and isinstance(v["requests"], list):
                    state["requests"] = v["requests"]
        
        # Extract title updates (kind 1 with k=["customTitle"])
        elif kind == 1:
            k = obj.get("k", [])
            if k == ["customTitle"]:
                state["customTitle"] = obj.get("v")
        
        # Extract requests array updates (kind 2 with k=["requests"])
        # NOTE: These are incremental updates, often just individual requests
        # If we have a complete array from kind=0, only update if this is larger
        elif kind == 2:
            k = obj.get("k", [])
            if k and k[0] == "requests":
                v = obj.get("v", [])
                # Only replace if this update has MORE requests (indicates growth)
                if isinstance(v, list) and len(v) > len(state.get("requests", [])):
                    state["requests"] = v
    
    # Include chats that have at least a title or requests
    if state.get("customTitle") or state.get("requests"):
        chats.append({
            "sessionId": state.get("sessionId"),
            "customTitle": state.get("customTitle", "Untitled Chat"),
            "projectPath": state.get("projectPath", ""),
            "creationDate": state.get("creationDate", 0),
            "filepath": str(filepath),
            "requests": state["requests"]
        })
    
    return chats

def filter_chats_by_project(all_chats, project_path):
    """Filter chats to only those matching the project path."""
    # Normalize the project path for comparison
    project_path = project_path.strip().lower()
    
    matching_chats = []
    for chat_file, chats in all_chats.items():
        for chat in chats:
            project = chat.get("projectPath", "")
            # Check if the project path contains the search term
            if project and project_path in project.lower():
                matching_chats.append(chat)
    
    return matching_chats

def export_chat_to_json(chat, output_dir, sequence_number=None, verbose=False):
    """Export a single chat to a JSON file in the format expected by chat-trim-tool."""
    # Check for suspiciously small chats (potential data loss)
    request_count = len(chat.get("requests", []))
    if verbose and request_count < 2:
        print(f"  ⚠️  Warning: '{chat.get('customTitle', 'Untitled')}' has only {request_count} request(s)")
        print(f"      This may indicate a recreated/archived session with data loss")
    
    # Create filename from chat title, sanitizing invalid characters
    title = chat["customTitle"] or "Untitled Chat"
    safe_title = "".join(c if c.isalnum() or c in "-_ " else "_" for c in title)
    safe_title = safe_title.strip()[:40]  # Truncate to 40 chars
    
    # Format timestamp for human readability
    date_obj = datetime.fromtimestamp(chat["creationDate"] / 1000)
    readable_date = date_obj.strftime("%b-%d-%Y_%H-%M")  # e.g., "Jan-27-2026_22-22"
    
    # Add sequence number and readable timestamp
    if sequence_number is not None:
        filename = f"{sequence_number:02d}-{safe_title}_({readable_date}).json"
    else:
        filename = f"{safe_title}_({readable_date}).json"
    filepath = Path(output_dir) / filename
    
    # Handle filename collisions
    counter = 1
    while filepath.exists():
        if sequence_number is not None:
            base_name = f"{sequence_number:02d}-{safe_title}_({readable_date})"
            filename = f"{base_name}_{counter}.json"
        else:
            base_name = f"{safe_title}_({readable_date})"
            filename = f"{base_name}_{counter}.json"
        filepath = Path(output_dir) / filename
        counter += 1
    
    # Convert requests to the format expected by chat-trim-tool
    export_data = {
        "requests": chat["requests"],
        "sessionId": chat["sessionId"],
        "customTitle": chat["customTitle"],
        "exportDate": datetime.now().isoformat(),
        "sourceFile": chat["filepath"]
    }
    
    # Write the export file
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    return filepath

def main():
    parser = argparse.ArgumentParser(
        description="Export VS Code Copilot chats from a specific project workspace",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export chats from a specific project (exports to {project}/batch chat exports/)
  python3 export-chats.py -p "/path/to/project/folder"
  
  # Export with custom output directory
  python3 export-chats.py -p "/path/to/project/folder" -o ~/Desktop/my_chats
  
  # Export with verbose output
  python3 export-chats.py -p "/path/to/project" -v
  
  # Show help
  python3 export-chats.py --help
        """
    )
    
    parser.add_argument(
        '-p', '--project',
        required=True,
        help='Full path to the VS Code project folder'
    )
    
    parser.add_argument(
        '-o', '--output',
        default=None,
        help='Output directory for exported JSON files (default: {project_folder}/batch chat exports)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show detailed output during export'
    )
    
    args = parser.parse_args()
    
    project_path = args.project
    
    # Determine output directory
    if args.output:
        output_dir = args.output
    else:
        # Default: create batch chat exports in the project folder
        project_folder = Path(project_path).resolve()
        output_dir = str(project_folder / "batch chat exports")
    
    # Validate project path exists
    project_folder = Path(project_path).resolve()
    if not project_folder.exists():
        print(f"❌ Error: Project path does not exist: {project_path}", file=sys.stderr)
        sys.exit(1)
    
    if args.verbose:
        print(f"🔍 Looking for workspace ID for project: {project_folder}")
    
    # Find the workspace ID for this project
    workspace_dir, folder_uri = find_workspace_id_for_folder(str(project_folder))
    
    if workspace_dir is None:
        print(f"❌ Error: Could not find VS Code workspace for project: {project_folder}", file=sys.stderr)
        sys.exit(1)
    
    if args.verbose:
        print(f"✓ Found workspace: {workspace_dir}")
    
    # Find all chat sessions in this workspace
    chat_sessions = find_chat_sessions_in_workspace(workspace_dir)
    
    if not chat_sessions:
        print(f"⚠️  No chat sessions found in workspace: {workspace_dir}")
        sys.exit(0)
    
    if args.verbose:
        print(f"✓ Found {len(chat_sessions)} chat sessions\n")
        for chat in chat_sessions:
            source_basename = Path(chat.get("filepath", "")).stem
            print(f"  → {chat.get('customTitle', 'Untitled')} ({source_basename})")
    
    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    if args.verbose:
        print(f"📁 Exporting to: {output_dir}\n")
    
    # Sort chats by creation date (oldest first)
    chat_sessions.sort(key=lambda x: x.get("creationDate", 0))
    
    # Export each chat with chronological numbering
    for i, chat in enumerate(chat_sessions, 1):
        try:
            export_chat_to_json(chat, str(output_path), i, args.verbose)
            if args.verbose:
                title = chat.get('customTitle', 'Untitled')
                request_count = len(chat.get('requests', []))
                print(f"  {i:02d}. {title} ({request_count} requests)")
        except Exception as e:
            print(f"⚠️  Failed to export chat {i}: {e}", file=sys.stderr)
    
    print(f"\n✓ Successfully exported {len(chat_sessions)} chats to {output_dir}")
    
    # Check for low-request chats that may indicate data loss
    low_request_chats = [c for c in chat_sessions if len(c.get('requests', [])) < 2]
    if low_request_chats:
        print(f"\n⚠️  Note: {len(low_request_chats)} chat(s) have very few requests.")
        print(f"    This may indicate archived/recreated sessions.")
        print(f"    If you need the full conversation, use VS Code's 'Export Chat' feature")
        print(f"    or restore from backup if available.")

if __name__ == "__main__":
    main()
