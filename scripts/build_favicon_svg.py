import base64
import os

png_path = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'public', 'icons', 'nova-star-512x512.png')
svg_path = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'public', 'favicon.svg')

with open(png_path, 'rb') as f:
    b64_data = base64.b64encode(f.read()).decode('ascii')

svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <image href="data:image/png;base64,{b64_data}" width="512" height="512"/>
</svg>'''

with open(svg_path, 'w', encoding='utf-8') as f:
    f.write(svg_content)

print("favicon.svg successfully created with embedded base64 data.")
