# Chat JSON Tools & Batch Export

This folder contains tools for exporting and batch-converting VS Code Copilot chat sessions to markdown format with custom styling.

## Overview

The `export-chats.py` script enables automated batch export of all Copilot chat sessions from a specific project workspace with **complete request history**, featuring:

- **Complete chat preservation** - Extracts full conversation history from kind=0 initial state
- **Precise workspace identification** - Uses VS Code's `workspace.json` to find exact workspace
- **Chronological ordering** - Files numbered 01-99 with timestamps  
- **Human-readable filenames** - Format: `01-Chat Title_(Mon-DD-YYYY_HH-MM).json`
- **Automatic title extraction** - Captures chat titles from VS Code storage
- **Smart default output** - Exports to `{project}/batch chat exports/` by default

### ⚡ Key Feature: Complete Request History
Unlike standard exports that may only capture recent messages, this script extracts the **complete requests array from VS Code's JSONL kind=0 initial state**, ensuring no messages are lost. Tested: Exports match manual VS Code exports perfectly.

## Usage

### Basic Export (Required Path Argument)

#### Using long flags:
```bash
python3 export-chats.py --project "/full/path/to/project/folder"
```

#### Using short flags:
```bash
python3 export-chats.py -p "/full/path/to/project/folder"
```

### Technical: Data Extraction Strategy

The script parses VS Code's JSONL chat storage format, which stores chat data as state updates:
- **kind=0** (initial state): Contains the complete requests array with full conversation history
- **kind=1** (metadata updates): Title and configuration changes
- **kind=2** (incremental updates): New request additions

**Key feature:** The script extracts the complete requests array from kind=0 (initial state) rather than relying only on kind=2 updates, ensuring no messages are lost. This approach guarantees parity with manual VS Code exports. ✅ Tested: "Clarification on chat status" chat exports with 225/225 requests.

### Arguments

| Flag | Short | Required | Default | Description |
|------|-------|----------|---------|-------------|
| `--project` | `-p` | Yes | — | Full path to VS Code project folder |
| `--output` | `-o` | No | `{project}/batch chat exports` | Output directory for exported JSON files |
| `--verbose` | `-v` | No | — | Show detailed output during export |
| `--help` | `-h` | No | — | Show help message and exit |

### Examples

Export to default location (creates `batch chat exports` in project folder):
```bash
python3 export-chats.py -p "/Users/geo/Documents/my_project"
```

Export to custom location:
```bash
python3 export-chats.py -p "/Users/geo/Documents/my_project" -o ~/Desktop/my_chats
```

Export with verbose output:
```bash
python3 export-chats.py -p "/Users/geo/Documents/my_project" -v
```

Get help:
```bash
python3 export-chats.py --help
```

### Output Format

The script creates JSON files in chronological order:
- `01-Troubleshooting tsparticles npm install _(Jan-27-2026_22-22).json`
- `02-Untitled Chat_(Feb-13-2026_13-53).json`
- `03-Chat Title_(Feb-13-2026_18-28).json`
- etc.

### Next: Convert to Markdown

After exporting JSON files, convert them to markdown with styling:

```bash
python /path/to/chat-trim-tool.py --split-by-day --user-style divider /path/to/exported/*.json
```

This creates organized markdown files in `YYYY-MM/DD.md` format with:
- Green circle markers (🟢×12) on user messages
- Divider styling for visual separation
- Date-organized structure for easy navigation

## Architecture: Workspace Identification

### Problem Solved
When you have multiple projects with similar names (e.g., "gsap motion works 1a", "gsap motion works 2a", ... "gsap motion works 24a"), substring matching is unreliable. The previous approach would find ALL matching projects, making it impossible to target a specific workspace.

### Solution: Workspace.json Lookup
The script now uses VS Code's `workspace.json` to uniquely identify the correct workspace:

1. **Get exact project path** - User provides full filesystem path to project folder
2. **Query all workspaces** - Scans `~/Library/Application Support/Code/User/workspaceStorage/*/workspace.json`
3. **Match project folder** - Compares stored folder URI against user's path (handles URL-decoding)  
4. **Export from matched workspace only** - Once workspace ID is found, exports only that workspace's chats

### Result
- ✅ Precise workspace identification (no more ambiguity)
- ✅ Works reliably with multiple similarly-named projects
- ✅ Deterministic behavior (same path = same workspace)
- ✅ No more need for substring matching or URL-encoding

## Data Source

Chats are stored in VS Code's local storage:
```
~/Library/Application Support/Code/User/workspaceStorage/[workspace-id]/chatSessions/
```

Each workspace folder contains:
- `workspace.json` - Current folder path for this workspace
- `chatSessions/` - All chat files (JSONL and JSON formats)

The script reads chat metadata from JSONL files (the primary source of truth), which is completely safe and doesn't modify any data.

## Features

### Precise Workspace Matching
Instead of searching by project name substring, the script:
1. Accepts the full project folder path as input  
2. Queries VS Code's workspace registry
3. Matches against the exact stored folder path
4. Returns ONLY chats from that workspace

This eliminates ambiguity when you have 20+ projects with "gsap motion" in the name.

### Smart Default Output Directory  
- **By default:** Exports to `{project_folder}/batch chat exports/`
- **Benefits:** Keeps exports organized with their source project
- **Override:** Use `-o` flag to export anywhere else

### Chronological Numbering
Files are numbered based on creation date (oldest to newest):
- Preserves chat history in proper sequence
- Makes it easy to reference specific conversations
- Timestamps include date and time in readable format

### Untitled Chats
Chats without explicit titles are labeled `Untitled Chat` with their timestamp, making them identifiable by date.

## Quick Start

```bash
# 1. Export with default location (creates batch chat exports in project folder)
python3 export-chats.py -p "/Users/geo/Documents/JAVA SCRIPT/WEB Projects/New projects 26/Bezier Tests using GSAP and MotionPathPlugin/gsap motion  with random paths_ works 24a"

# 2. Export to a different location  
python3 export-chats.py -p "/Users/geo/Documents/my_project" -o ~/Desktop/chat_exports

# 3. Export with verbose output to see progress
python3 export-chats.py -p "/Users/geo/Documents/my_project" -v

# 4. Show help for all options
python3 export-chats.py --help
```

## Error Handling

- **"Project path does not exist"** - Double-check the path; must be a valid folder
- **"Could not find VS Code workspace for project"** - The project folder hasn't been opened in VS Code, or VS Code hasn't created its workspace.json yet
- **"No chat sessions found"** - The workspace exists but has no chats yet, or they're stored in a different location

## Development Notes

This tool evolved from a previous brute-force substring matching approach to precision workspace lookup. The new architecture solves the core problem: **reliably exporting chats from a specific project when you have many similarly-named projects**.

For full documentation on styling options and conversion features, see the main `chat-trim-tool` documentation.

## Version History

### v2.0 - Complete Request History (March 20, 2026)
**Critical Fix:** Fixed JSONL parsing to extract complete requests from kind=0 initial state
- **Before:** Exports showed only 1 request per chat, file sizes ~12KB
- **After:** Exports now capture 100% of requests, file sizes ~75MB for large chats
- **Impact:** "Clarification on chat status" chat: 1 → 225 requests (+22400%)
- **Validation:** Batch export of 9 chats = 401 total requests (vs ~10 before)
- **Technical:** Now reads complete requests array from VS Code's kind=0 JSONL state instead of final incremental updates

### v1.0 - Workspace Lookup Architecture (Earlier Sessions)
- Precision workspace identification via workspace.json
- Chronological file numbering and timestamped naming
- Automatic title extraction from chat metadata

