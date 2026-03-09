#!/usr/bin/env python3
"""
Extract Mermaid diagrams from markdown and convert them to images.
"""
import re
import subprocess
import tempfile
from pathlib import Path


def extract_mermaid_diagrams(markdown_content: str) -> list[tuple[str, str]]:
    """Extract all mermaid code blocks from markdown."""
    pattern = r'```mermaid\n(.*?)```'
    matches = re.findall(pattern, markdown_content, re.DOTALL)
    
    diagrams = []
    for i, match in enumerate(matches):
        diagrams.append((f"mermaid_diagram_{i+1}", match.strip()))
    
    return diagrams


def render_mermaid_to_png(mermaid_code: str, output_path: Path) -> bool:
    """Render a mermaid diagram to PNG using mermaid-cli."""
    try:
        # Create temporary file with mermaid code
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as f:
            f.write(mermaid_code)
            temp_file = f.name
        
        # Run mermaid-cli to generate PNG
        result = subprocess.run(
            ['npx', '-y', '@mermaid-js/mermaid-cli', '-i', temp_file, '-o', str(output_path)],
            capture_output=True,
            text=True
        )
        
        # Clean up temp file
        Path(temp_file).unlink()
        
        if result.returncode == 0:
            print(f"✓ Generated {output_path.name}")
            return True
        else:
            print(f"✗ Failed to generate {output_path.name}")
            print(f"  Error: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"✗ Error rendering {output_path.name}: {e}")
        return False


def replace_mermaid_with_images(markdown_content: str, image_prefix: str = "") -> str:
    """Replace mermaid code blocks with image references."""
    counter = [0]  # Use list to allow modification in nested function
    
    def replacer(match):
        counter[0] += 1
        image_name = f"mermaid_diagram_{counter[0]}.png"
        if image_prefix:
            image_path = f"{image_prefix}/{image_name}"
        else:
            image_path = image_name
        return f"![Mermaid Diagram {counter[0]}]({image_path})"
    
    pattern = r'```mermaid\n.*?```'
    return re.sub(pattern, replacer, markdown_content, flags=re.DOTALL)


def process_markdown_file(input_path: Path, output_dir: Path, replace_in_markdown: bool = True):
    """Process a markdown file: extract and render mermaid diagrams."""
    print(f"\nProcessing {input_path.name}...")
    
    # Read markdown content
    content = input_path.read_text()
    
    # Extract mermaid diagrams
    diagrams = extract_mermaid_diagrams(content)
    
    if not diagrams:
        print("No mermaid diagrams found.")
        return
    
    print(f"Found {len(diagrams)} mermaid diagram(s)")
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Render each diagram
    success_count = 0
    for name, code in diagrams:
        output_path = output_dir / f"{name}.png"
        if render_mermaid_to_png(code, output_path):
            success_count += 1
    
    print(f"\nRendered {success_count}/{len(diagrams)} diagrams successfully")
    
    # Optionally replace mermaid blocks with image references
    if replace_in_markdown and success_count > 0:
        modified_content = replace_mermaid_with_images(content)
        modified_path = output_dir / input_path.name
        modified_path.write_text(modified_content)
        print(f"✓ Created modified markdown: {modified_path}")


if __name__ == "__main__":
    # Process the evaluation report
    report_path = Path("evaluation/report/EVALUATION_REPORT.md")
    output_dir = Path("evaluation/report")
    
    if report_path.exists():
        process_markdown_file(report_path, output_dir, replace_in_markdown=False)
    else:
        print(f"Report not found: {report_path}")
