import re


def fix_file(path):
    with open(path) as f:
        content = f.read()

    # 1. Add imports if missing
    if 'from typing import' in content:
        if 'Optional' not in content:
            content = content.replace('from typing import ', 'from typing import Optional, ')
        if 'Union' not in content:
            content = content.replace('from typing import ', 'from typing import Union, ')

    # 2. Replace | None with Optional[...]
    # This is tricky for nested brackets. We'll do a simple one first.
    # Pattern: ([^ ]+) \| None -> Optional[\1]
    # We need to be careful with spaces.

    # Let's use a more robust approach: find all " | None"
    # and try to find the start of the type expression.

    new_content = re.sub(r'([a-zA-Z0-9_\[\], ]+) \| None', r'Optional[\1]', content)
    new_content = re.sub(r'([a-zA-Z0-9_\[\], ]+) \| ([a-zA-Z0-9_\[\], ]+)', r'Union[\1, \2]', new_content)

    # Clean up double imports
    new_content = new_content.replace('Optional, Optional,', 'Optional,')
    new_content = new_content.replace('Union, Union,', 'Union,')

    with open(path, 'w') as f:
        f.write(new_content)

files = [
    'mcp_sdk/inference/active_inference.py',
    'mcp_sdk/geospatial/model.py',
    'mcp_sdk/geospatial/chunker.py',
    'mcp_sdk/loop/engine.py',
    'mcp_sdk/context/manager.py'
]

for f in files:
    print(f"Fixing {f}...")
    fix_file(f)
