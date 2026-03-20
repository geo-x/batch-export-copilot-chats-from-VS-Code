#!/usr/bin/env python3
"""
Chat Export Trimmer & Converter
Trims VS Code Copilot chat exports by date range and converts to markdown

Usage:
    python3 chat-trim-tool.py input.json --start "2026-03-12" --end "2026-03-16" --output-dir ./

Examples:
    # Trim and export to markdown
    python3 chat-trim-tool.py chat.json --start "2026-03-12" --format md
    
    # Trim and keep JSON
    python3 chat-trim-tool.py chat.json --start "2026-03-01" --end "2026-03-15" --format json
    
    # Export both formats
    python3 chat-trim-tool.py chat.json --start "2026-03-12" --format both
    
    # Split by day (creates daily files)
    python3 chat-trim-tool.py chat.json --start "2026-03-09" --end "2026-03-15" --split-by-day
"""

import json
import argparse
from datetime import datetime
from pathlib import Path
import sys
from collections import defaultdict


def parse_date(date_str):
    """Parse date string in YYYY-MM-DD format"""
    try:
        return datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")


def format_user_message(text, style='none', color='green'):
    """Format user message based on style option"""
    # Always add distinctive green circle marker row for all messages
    marker = "🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢"
    divider_thick = "▅" * 30
    divider_thin = "▁" * 30
    
    if style == 'divider':
        # Thick unicode block dividers above and below
        return f"{marker}\n{divider_thick}\n**👤 User:**\n{text}\n{divider_thick}"
    elif style == 'divider-thin':
        # Thin unicode block dividers above and below
        return f"{marker}\n{divider_thin}\n**👤 User:**\n{text}\n{divider_thin}"
    elif style == 'emoji':
        # Emoji prefix style
        return f"{marker}\n👤 **User:**\n{text}"
    elif style == 'color':
        # Colored text (HTML) - wrap entire message in colored div
        return f'{marker}\n<div style="color:{color};">\n\n👤 **User:**\n\n{text}\n\n</div>'
    else:
        # Default style (no special formatting)
        return f"{marker}\n**User:**\n{text}"


def format_assistant_message(text, style='none', color='green'):
    """Format assistant response based on style option"""
    # Assistant messages always use default formatting (no styling)
    return f"**Assistant:**\n{text}"


def filter_requests_by_date(requests, start_date, end_date):
    """Filter requests by date range"""
    start_ts = start_date.timestamp() * 1000
    end_ts = end_date.timestamp() * 1000
    
    filtered = [
        req for req in requests 
        if start_ts <= req.get('timestamp', 0) <= end_ts
    ]
    return filtered


def split_requests_by_day(requests):
    """Group requests by day, returning dict of {date_obj: [requests]}"""
    daily_groups = defaultdict(list)
    
    for req in requests:
        timestamp = req.get('timestamp', 0)
        date_obj = datetime.fromtimestamp(timestamp/1000).date()
        daily_groups[date_obj].append(req)
    
    # Sort by date
    return dict(sorted(daily_groups.items()))


def create_markdown(requests, user_style='none', style_color='green'):
    """Convert chat requests to markdown format"""
    if not requests:
        return "# Chat Export\n\nNo messages found in the specified date range.\n"
    
    first_date = datetime.fromtimestamp(requests[0]['timestamp']/1000)
    last_date = datetime.fromtimestamp(requests[-1]['timestamp']/1000)
    
    md_content = f"# Chat Export: {first_date.strftime('%B %d, %Y')} to {last_date.strftime('%B %d, %Y')}\n\n"
    md_content += f"**Total Messages:** {len(requests)}\n"
    md_content += f"**Date Range:** {first_date.strftime('%B %d, %Y')} - {last_date.strftime('%B %d, %Y')}\n\n"
    md_content += "---\n\n"
    
    for i, req in enumerate(requests, 1):
        timestamp = req.get('timestamp', 0)
        date_str = datetime.fromtimestamp(timestamp/1000).strftime('%B %d, %Y at %H:%M:%S')
        
        # Extract user message
        message = req.get('message', {})
        if isinstance(message, dict):
            if 'text' in message:
                message_text = message['text']
            elif 'parts' in message:
                message_text = '\n'.join([p.get('text', '') for p in message['parts'] if p.get('text')])
            else:
                message_text = str(message)
        else:
            message_text = str(message)
        
        md_content += f"## Message {i}\n"
        md_content += f"**Time:** {date_str}\n\n"
        md_content += format_user_message(message_text, user_style, style_color) + "\n\n"
        
        # Extract ALL response content
        response_list = req.get('response', [])
        
        for resp_item in response_list:
            kind = resp_item.get('kind', '')
            value = resp_item.get('value', '')
            
            if kind == 'thinking':
                # Include thinking/reasoning blocks
                if value and value.strip():
                    md_content += f"**🧠 Assistant's Reasoning:**\n{value}\n\n"
            elif kind == 'mcpServersStarting':
                # Skip internal server markers
                continue
            elif isinstance(value, str) and value.strip():
                # Regular response text
                md_content += format_assistant_message(value, user_style, style_color) + "\n\n"
        
        # Include code blocks if present
        result = req.get('result', {})
        metadata = result.get('metadata', {})
        code_blocks = metadata.get('codeBlocks', [])
        
        if code_blocks:
            md_content += f"**Code Blocks Generated:**\n"
            for j, block in enumerate(code_blocks, 1):
                language = block.get('language', 'text')
                filename = block.get('filename', '')
                content = block.get('content', '')
                
                if filename:
                    md_content += f"\n{j}. `{filename}` ({language}):\n"
                else:
                    md_content += f"\n{j}. Code ({language}):\n"
                
                md_content += f"```{language}\n{content}\n```\n"
        
        md_content += "---\n\n"
    
    return md_content


def create_day_markdown(requests, date_obj, user_style='none', style_color='green'):
    """Create markdown for a single day of requests"""
    if not requests:
        return "# No messages for this day\n"
    
    date_str = date_obj.strftime('%B %d, %Y')
    md_content = f"# Chat Log: {date_str}\n\n"
    md_content += f"**Total Messages:** {len(requests)}\n\n"
    md_content += "---\n\n"
    
    for i, req in enumerate(requests, 1):
        timestamp = req.get('timestamp', 0)
        time_str = datetime.fromtimestamp(timestamp/1000).strftime('%H:%M:%S')
        
        # Extract user message (handle both text and parts format)
        message = req.get('message', {})
        if isinstance(message, dict):
            if 'text' in message:
                message_text = message['text']
            elif 'parts' in message:
                message_text = '\n'.join([p.get('text', '') for p in message['parts'] if p.get('text')])
            else:
                message_text = str(message)
        else:
            message_text = str(message)
        
        md_content += f"## {i}. {time_str}\n\n"
        md_content += format_user_message(message_text, user_style, style_color) + "\n\n"
        
        # Extract ALL response content (thinking blocks, code, everything)
        response_list = req.get('response', [])
        
        for resp_item in response_list:
            kind = resp_item.get('kind', '')
            value = resp_item.get('value', '')
            
            if kind == 'thinking':
                # Include thinking/reasoning blocks
                if value and value.strip():
                    md_content += f"**Reasoning:**\n{value}\n\n"
            elif kind == 'mcpServersStarting':
                # Skip internal server markers
                continue
            elif isinstance(value, str) and value.strip():
                # Regular response text
                md_content += format_assistant_message(value, user_style, style_color) + "\n\n"
        
        # Include code blocks if present in metadata
        result = req.get('result', {})
        metadata = result.get('metadata', {})
        code_blocks = metadata.get('codeBlocks', [])
        
        if code_blocks:
            md_content += f"**Code Generated:**\n"
            for j, block in enumerate(code_blocks, 1):
                language = block.get('language', 'text')
                filename = block.get('filename', '')
                content = block.get('content', '')
                
                if filename:
                    md_content += f"\n{j}. `{filename}` ({language}):\n"
                else:
                    md_content += f"\n{j}. Code ({language}):\n"
                
                md_content += f"```{language}\n{content}\n```\n"
        
        md_content += "---\n\n"
    
    return md_content


def save_json(data, output_path):
    """Save data as JSON"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    return output_path


def save_markdown(content, output_path):
    """Save content as markdown"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(content)
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description='Trim VS Code Copilot chat exports by date range and convert to markdown'
    )
    parser.add_argument('input_file', help='Input JSON chat export file')
    parser.add_argument('--start', help='Start date (YYYY-MM-DD). If not provided, uses earliest message in chat')
    parser.add_argument('--end', help='End date (YYYY-MM-DD). Defaults to today')
    parser.add_argument('--format', choices=['json', 'md', 'both'], default='md',
                        help='Output format (default: md)')
    parser.add_argument('--output-dir', default=None, help='Output directory (default: same as input file)')
    parser.add_argument('--output-name', help='Custom output filename (without extension)')
    parser.add_argument('--split-by-day', action='store_true',
                        help='Split into separate daily files organized by year-month')
    parser.add_argument('--user-style', choices=['none', 'emoji', 'divider', 'divider-thin', 'color'], default='none',
                        help='Style for user messages (default: none)')
    parser.add_argument('--style-color', default='green',
                        help='Color for styled output (CSS color or hex value, default: green)')
    
    args = parser.parse_args()
    
    # Validate input file
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)
    
    # Set output directory to input file's directory if not specified
    if args.output_dir is None:
        output_dir = input_path.parent
    else:
        output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load JSON first (before date parsing)
    try:
        with open(input_path, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON file: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Parse dates
    try:
        if args.start:
            start_date = parse_date(args.start)
        else:
            # If no start date provided, use earliest message in chat
            requests = data.get('requests', [])
            if requests:
                earliest_timestamp = min(req.get('timestamp', 0) for req in requests)
                start_date = datetime.fromtimestamp(earliest_timestamp/1000)
            else:
                print("Error: Chat export has no messages", file=sys.stderr)
                sys.exit(1)
        
        end_date = parse_date(args.end) if args.end else datetime.now()
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Validate date range
    if start_date > end_date:
        print(f"Error: Start date must be before end date", file=sys.stderr)
        sys.exit(1)
    
    # Filter requests
    requests = data.get('requests', [])
    filtered_requests = filter_requests_by_date(requests, start_date, end_date)
    
    if not filtered_requests:
        print(f"Warning: No messages found in the date range {start_date.date()} to {end_date.date()}", 
              file=sys.stderr)
        return
    
    # Handle split-by-day mode
    if args.split_by_day:
        daily_groups = split_requests_by_day(filtered_requests)
        output_files = []
        total_days = len(daily_groups)
        
        print(f"📅 Splitting into {total_days} daily file(s)...\n")
        
        for day_idx, (date_obj, day_requests) in enumerate(daily_groups.items(), 1):
            # Create year-month subdirectory
            year_month_dir = output_dir / f"{date_obj.strftime('%Y-%m')}"
            year_month_dir.mkdir(parents=True, exist_ok=True)
            
            # Get day number
            day_num = date_obj.strftime('%d')
            day_name = date_obj.strftime('%A')
            
            # Create files
            if args.format in ['json', 'both']:
                filtered_data = data.copy()
                filtered_data['requests'] = day_requests
                json_path = year_month_dir / f"{day_num}.json"
                save_json(filtered_data, json_path)
                output_files.append(json_path)
            
            if args.format in ['md', 'both']:
                md_content = create_day_markdown(day_requests, date_obj, args.user_style, args.style_color)
                md_path = year_month_dir / f"{day_num}.md"
                save_markdown(md_content, md_path)
                output_files.append(md_path)
            
            # Show progress
            print(f"  [{day_idx}/{total_days}] {day_name}, {date_obj.strftime('%B %d, %Y')}: {len(day_requests)} message(s)")
        
        # Summary
        print(f"\n📊 Summary:")
        print(f"  Total days: {total_days}")
        print(f"  Total messages: {len(filtered_requests)}")
        print(f"  Output directory: {output_dir}")
        print(f"  Organization: YYYY-MM/DD.{args.format if args.format != 'both' else 'md|json'}")
        print(f"  Output files: {len(output_files)}")
    
    else:
        # Regular mode (single combined output)
        # Generate output filename
        if args.output_name:
            base_name = args.output_name
        else:
            date_range = f"{start_date.strftime('%d_%m_%y')}_to_{end_date.strftime('%d_%m_%y')}"
            base_name = f"{input_path.stem}_{date_range}"
        
        # Save outputs
        output_files = []
        
        if args.format in ['json', 'both']:
            filtered_data = data.copy()
            filtered_data['requests'] = filtered_requests
            json_path = output_dir / f"{base_name}.json"
            save_json(filtered_data, json_path)
            output_files.append(json_path)
            print(f"✓ JSON saved: {json_path}")
        
        if args.format in ['md', 'both']:
            md_content = create_markdown(filtered_requests, args.user_style, args.style_color)
            md_path = output_dir / f"{base_name}.md"
            save_markdown(md_content, md_path)
            output_files.append(md_path)
            print(f"✓ Markdown saved: {md_path}")
        
        # Summary
        first_date = datetime.fromtimestamp(filtered_requests[0]['timestamp']/1000)
        last_date = datetime.fromtimestamp(filtered_requests[-1]['timestamp']/1000)
        
        print(f"\n📊 Summary:")
        print(f"  Total messages: {len(filtered_requests)}")
        print(f"  Date range: {first_date.strftime('%B %d, %Y')} to {last_date.strftime('%B %d, %Y')}")
        print(f"  Output files: {', '.join(str(f.name) for f in output_files)}")


if __name__ == '__main__':
    main()
