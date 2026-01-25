import sys
import os
import argparse
import json
from pprint import pprint

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

try:
    from analysis import analyze_content
except ImportError:
    print("Error: Could not import analysis module. Make sure you are running from backend/scripts/ or root.")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Analyze a shared item manually.")
    parser.add_argument('input', help="The content string to analyze, or a path to a file.")
    parser.add_argument('--type', default='text', help="The type of item (text, web_url, image, video, audio, file, screenshot). Default: text")
    
    args = parser.parse_args()
    
    content = args.input
    if os.path.exists(content):
        try:
            with open(content, 'r') as f:
                content = f.read()
            print(f"Loaded content from file: {args.input}")
        except Exception as e:
            print(f"Error reading file {args.input}: {e}")
            return

    print("--- Analyzing Item ---")
    print(f"Type: {args.type}")
    print(f"Content Preview: {content[:100]}...")
    
    result = analyze_content(content, item_type=args.type)
    
    print("\n--- Result ---")
    pprint(result)

if __name__ == "__main__":
    main()
