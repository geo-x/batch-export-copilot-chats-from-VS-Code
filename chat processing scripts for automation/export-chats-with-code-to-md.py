#!/usr/bin/env python3
"""
Combined workflow: Export chats with code snippets, then convert all to markdown.
Orchestrates:
1. bin/export-chats-with-code.py - exports JSON with extracted code blocks
2. bin/chat-trim-tool.py - converts JSON exports to markdown

Usage:
    python3 export-chats-with-code-to-md.py -p "/path/to/project/folder" -v
    
This will:
- Export all chats as JSON (with code blocks) to batch chat exports/
- Automatically convert each JSON to markdown in the same directory
"""

import subprocess
import sys
import argparse
from pathlib import Path
import os

def run_command(cmd, description=""):
    """Run a shell command and return success status"""
    try:
        print(f"\n{'='*60}")
        print(f"▶ {description}")
        print(f"{'='*60}")
        result = subprocess.run(cmd, shell=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running: {description}", file=sys.stderr)
        print(f"   Command: {cmd}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Export chats with code snippets, then batch convert to markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export and convert all chats
  python3 export-chats-with-code-to-md.py -p "/path/to/project/folder"
  
  # With verbose output
  python3 export-chats-with-code-to-md.py -p "/path/to/project/folder" -v
  
  # Help
  python3 export-chats-with-code-to-md.py --help
        """
    )
    
    parser.add_argument(
        '-p', '--project',
        required=True,
        help='Full path to the VS Code project folder'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show detailed output'
    )
    
    args = parser.parse_args()
    
    project_path = args.project
    script_dir = Path(__file__).parent.resolve()
    bin_dir = script_dir / "bin"
    
    # Validate project path
    project_folder = Path(project_path).resolve()
    if not project_folder.exists():
        print(f"❌ Error: Project path does not exist: {project_path}", file=sys.stderr)
        sys.exit(1)
    
    # Determine export directory
    export_dir = str(project_folder / "batch chat exports")
    
    # Step 1: Export chats with code snippets
    print("\n" + "="*60)
    print("STEP 1: Exporting chats with code snippets")
    print("="*60)
    
    export_script = str(bin_dir / "export-chats-with-code.py")
    if not Path(export_script).exists():
        print(f"❌ Error: export-chats-with-code.py not found at: {export_script}", file=sys.stderr)
        sys.exit(1)
    
    export_cmd = f"python3 \"{export_script}\" -p \"{project_path}\""
    if args.verbose:
        export_cmd += " -v"
    
    if not run_command(export_cmd, "Running export-chats-with-code.py"):
        sys.exit(1)
    
    # Step 2: Find all JSON files in export directory
    print("\n" + "="*60)
    print("STEP 2: Finding exported JSON files")
    print("="*60)
    
    export_path = Path(export_dir)
    if not export_path.exists():
        print(f"❌ Error: Export directory not found: {export_dir}", file=sys.stderr)
        sys.exit(1)
    
    json_files = sorted(export_path.glob("*.json"))
    if not json_files:
        print(f"⚠️  No JSON files found in {export_dir}")
        sys.exit(0)
    
    print(f"✓ Found {len(json_files)} JSON files to convert")
    
    # Step 3: Convert each JSON to markdown
    print("\n" + "="*60)
    print("STEP 3: Converting JSON files to markdown")
    print("="*60)
    
    # Use chat-trim-tool from bin directory
    trim_tool = str(bin_dir / "chat-trim-tool.py")
    
    if not Path(trim_tool).exists():
        print(f"❌ Error: chat-trim-tool.py not found at: {trim_tool}", file=sys.stderr)
        sys.exit(1)
    
    print(f"✓ Using trim tool from: bin/chat-trim-tool.py\n")
    
    successful = 0
    failed = 0
    
    for i, json_file in enumerate(json_files, 1):
        filename = json_file.name
        print(f"  [{i}/{len(json_files)}] Converting {filename}...", end=" ", flush=True)
        
        convert_cmd = f"cd \"{export_dir}\" && python3 \"{trim_tool}\" \"{filename}\""
        try:
            result = subprocess.run(convert_cmd, shell=True, capture_output=True, text=True, check=True)
            print("✓")
            successful += 1
        except subprocess.CalledProcessError as e:
            print("✗")
            if args.verbose:
                print(f"    Error: {e.stderr}")
            failed += 1
    
    # Summary
    print("\n" + "="*60)
    print("WORKFLOW COMPLETE")
    print("="*60)
    print(f"✓ Successfully exported {len(json_files)} chats as JSON with code snippets")
    print(f"✓ Successfully converted {successful}/{len(json_files)} to markdown")
    if failed > 0:
        print(f"⚠️  {failed} conversions failed")
    
    print(f"\n📁 Output directory: {export_dir}")
    print(f"   - JSON files (with code snippets): *.json")
    print(f"   - Markdown conversions: *.md")

if __name__ == "__main__":
    main()
