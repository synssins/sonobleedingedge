#!/usr/bin/env python3
"""
AmbientMixerHarvester.py - Extract and download audio from ambient-mixer.com

For use with Sonorium - organizes downloads into theme folders with attribution.

Usage:
    python AmbientMixerHarvester.py <url> [options]
    python AmbientMixerHarvester.py --url-file <file> [options]

License: Audio from ambient-mixer.com is under Creative Commons Sampling Plus 1.0
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

# Constants
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
XML_API_BASE = "http://xml.ambient-mixer.com/audio-template?player=html5&id_template="
AUDIO_BASE = "http://xml.ambient-mixer.com/audio/"


@dataclass
class AudioChannel:
    """Represents a single audio channel from an ambient-mixer template."""
    channel_num: int
    name: str
    audio_id: str
    url: str
    volume: int = 100
    balance: int = 0
    is_random: bool = False
    random_counter: int = 1
    random_unit: str = "1h"
    crossfade: bool = False
    mute: bool = False
    
    # Post-download info
    local_filename: Optional[str] = None
    file_hash: Optional[str] = None
    
    def __post_init__(self):
        # Clean up URL
        if self.url:
            self.url = self.url.strip()


@dataclass 
class AmbientMix:
    """Represents a complete ambient-mixer template/mix."""
    template_id: str
    source_url: str
    name: str = ""
    channels: list = field(default_factory=list)
    
    # Metadata
    creator: str = ""
    category: str = ""
    harvested_at: str = ""
    
    def to_manifest(self) -> dict:
        """Convert to manifest dict for JSON export."""
        return {
            "source": {
                "site": "ambient-mixer.com",
                "url": self.source_url,
                "template_id": self.template_id,
                "creator": self.creator,
                "harvested_at": self.harvested_at,
            },
            "license": {
                "name": "Creative Commons Sampling Plus 1.0",
                "url": "https://creativecommons.org/licenses/sampling+/1.0/",
                "requires_attribution": True,
            },
            "mix_name": self.name,
            "category": self.category,
            "channels": [asdict(ch) for ch in self.channels if ch.url],
        }


class AmbientMixerHarvester:
    """Harvests audio files from ambient-mixer.com for Sonorium."""
    
    def __init__(self, output_dir: str, verbose: bool = False):
        self.output_dir = Path(output_dir)
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
    
    def log(self, msg: str, force: bool = False):
        """Print log message if verbose or forced."""
        if self.verbose or force:
            print(msg)
    
    def get_template_id(self, page_url: str) -> Optional[str]:
        """Extract template ID from an ambient-mixer page."""
        self.log(f"Fetching page: {page_url}")
        
        try:
            resp = self.session.get(page_url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"ERROR: Failed to fetch page: {e}", file=sys.stderr)
            return None
        
        # Try AmbientMixer.setup() pattern first
        match = re.search(r'AmbientMixer\.setup\((\d+)\)', resp.text)
        if match:
            self.log(f"Found template ID via setup(): {match.group(1)}")
            return match.group(1)
        
        # Try vote link pattern
        match = re.search(r'/vote/(\d+)', resp.text)
        if match:
            self.log(f"Found template ID via vote link: {match.group(1)}")
            return match.group(1)
        
        # Try other patterns
        match = re.search(r'id_template[=:][\s"\']*(\d+)', resp.text)
        if match:
            self.log(f"Found template ID via id_template: {match.group(1)}")
            return match.group(1)
        
        print(f"ERROR: Could not find template ID in page", file=sys.stderr)
        return None
    
    def fetch_template_xml(self, template_id: str) -> Optional[str]:
        """Fetch the XML configuration for a template."""
        url = f"{XML_API_BASE}{template_id}"
        self.log(f"Fetching XML: {url}")
        
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            print(f"ERROR: Failed to fetch XML: {e}", file=sys.stderr)
            return None
    
    def parse_template_xml(self, xml_content: str, source_url: str, template_id: str) -> Optional[AmbientMix]:
        """Parse XML content into an AmbientMix object."""
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            print(f"ERROR: Failed to parse XML: {e}", file=sys.stderr)
            return None
        
        mix = AmbientMix(
            template_id=template_id,
            source_url=source_url,
            harvested_at=datetime.now().isoformat(),
        )
        
        # Extract mix name from URL
        parsed = urlparse(source_url)
        mix.name = parsed.path.strip('/').split('/')[-1].replace('-', '_')
        mix.category = parsed.netloc.split('.')[0]  # e.g., "christmas" from christmas.ambient-mixer.com
        
        # Parse channels
        for i in range(1, 9):
            channel_elem = root.find(f'channel{i}')
            if channel_elem is None:
                continue
            
            url_elem = channel_elem.find('url_audio')
            if url_elem is None or not url_elem.text or not url_elem.text.strip():
                continue
            
            def get_text(elem_name: str, default: str = "") -> str:
                elem = channel_elem.find(elem_name)
                return elem.text.strip() if elem is not None and elem.text else default
            
            def get_int(elem_name: str, default: int = 0) -> int:
                try:
                    return int(get_text(elem_name, str(default)))
                except ValueError:
                    return default
            
            def get_bool(elem_name: str, default: bool = False) -> bool:
                val = get_text(elem_name, "").lower()
                return val in ("true", "1", "yes")
            
            channel = AudioChannel(
                channel_num=i,
                name=get_text('name_audio', f'channel_{i}'),
                audio_id=get_text('id_audio'),
                url=get_text('url_audio'),
                volume=get_int('volume', 100),
                balance=get_int('balance', 0),
                is_random=get_bool('random'),
                random_counter=get_int('random_counter', 1),
                random_unit=get_text('random_unit', '1h'),
                crossfade=get_bool('crossfade'),
                mute=get_bool('mute'),
            )
            
            mix.channels.append(channel)
            self.log(f"  Channel {i}: {channel.name} ({channel.audio_id})")
        
        return mix
    
    def download_audio(self, channel: AudioChannel, dest_dir: Path) -> bool:
        """Download a single audio file."""
        if not channel.url:
            return False
        
        # Generate filename: sanitized name + original extension
        ext = Path(urlparse(channel.url).path).suffix or '.mp3'
        safe_name = re.sub(r'[^\w\s-]', '', channel.name).strip().replace(' ', '_')[:50]
        filename = f"{safe_name}_{channel.audio_id}{ext}"
        dest_path = dest_dir / filename
        
        # Skip if already exists
        if dest_path.exists():
            self.log(f"  Skipping (exists): {filename}")
            channel.local_filename = filename
            return True
        
        self.log(f"  Downloading: {channel.name} -> {filename}")
        
        try:
            resp = self.session.get(channel.url, timeout=60, stream=True)
            resp.raise_for_status()
            
            # Download with progress
            with open(dest_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Calculate hash
            channel.file_hash = self._file_hash(dest_path)
            channel.local_filename = filename
            
            return True
            
        except requests.RequestException as e:
            print(f"  ERROR downloading {channel.name}: {e}", file=sys.stderr)
            return False
    
    def _file_hash(self, filepath: Path) -> str:
        """Calculate MD5 hash of file."""
        h = hashlib.md5()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()
    
    def harvest_url(self, url: str, theme_name: Optional[str] = None) -> Optional[AmbientMix]:
        """Harvest audio from a single ambient-mixer URL."""
        print(f"\n{'='*60}")
        print(f"Harvesting: {url}")
        print('='*60)
        
        # Get template ID
        template_id = self.get_template_id(url)
        if not template_id:
            return None
        
        # Fetch and parse XML
        xml_content = self.fetch_template_xml(template_id)
        if not xml_content:
            return None
        
        mix = self.parse_template_xml(xml_content, url, template_id)
        if not mix:
            return None
        
        print(f"Mix: {mix.name} ({len(mix.channels)} channels)")
        
        # Determine output folder
        folder_name = theme_name or mix.name or f"mix_{template_id}"
        dest_dir = self.output_dir / folder_name
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        # Download audio files
        success_count = 0
        for channel in mix.channels:
            if self.download_audio(channel, dest_dir):
                success_count += 1
            time.sleep(0.5)  # Be polite to the server
        
        print(f"Downloaded: {success_count}/{len(mix.channels)} files")
        
        # Write manifest
        manifest_path = dest_dir / "MANIFEST.json"
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(mix.to_manifest(), f, indent=2)
        self.log(f"Manifest: {manifest_path}")
        
        # Write attribution
        attr_path = dest_dir / "ATTRIBUTION.md"
        self._write_attribution(mix, attr_path)
        self.log(f"Attribution: {attr_path}")
        
        return mix
    
    def _write_attribution(self, mix: AmbientMix, filepath: Path):
        """Write human-readable attribution file."""
        lines = [
            f"# Attribution for {mix.name}",
            "",
            f"**Source:** [{mix.source_url}]({mix.source_url})",
            f"**Harvested:** {mix.harvested_at}",
            "",
            "## License",
            "",
            "All audio files in this folder are licensed under:",
            "[Creative Commons Sampling Plus 1.0](https://creativecommons.org/licenses/sampling+/1.0/)",
            "",
            "This license permits:",
            "- Sampling and remixing (including commercial use)",
            "- Distribution of derivative works",
            "",
            "**Attribution is required.** Credit the original creators listed below.",
            "",
            "## Audio Files",
            "",
        ]
        
        for ch in mix.channels:
            if ch.local_filename:
                lines.append(f"- **{ch.local_filename}**")
                lines.append(f"  - Original name: {ch.name}")
                lines.append(f"  - Source ID: {ch.audio_id}")
                lines.append(f"  - Default volume: {ch.volume}%")
                lines.append("")
        
        lines.extend([
            "---",
            f"*Generated by AmbientMixerHarvester for Sonorium*",
        ])
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
    
    def harvest_from_file(self, filepath: str, theme_prefix: Optional[str] = None) -> list:
        """Harvest from a file containing URLs (one per line)."""
        results = []
        
        with open(filepath, 'r') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        print(f"Found {len(urls)} URLs to harvest")
        
        for i, url in enumerate(urls, 1):
            theme_name = f"{theme_prefix}_{i}" if theme_prefix else None
            mix = self.harvest_url(url, theme_name)
            if mix:
                results.append(mix)
            time.sleep(1)  # Pause between mixes
        
        return results


def main():
    parser = argparse.ArgumentParser(
        description="Harvest audio from ambient-mixer.com for Sonorium",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s https://christmas.ambient-mixer.com/christmas-sleigh-ride
  %(prog)s https://nature.ambient-mixer.com/forest-rain -o D:\\Audio\\Themes
  %(prog)s --url-file urls.txt --theme-prefix nature
  %(prog)s --list-only https://christmas.ambient-mixer.com/christmas-sleigh-ride
        """
    )
    
    parser.add_argument('url', nargs='?', help='URL of ambient-mixer page to harvest')
    parser.add_argument('--url-file', '-f', help='File containing URLs (one per line)')
    parser.add_argument('--output', '-o', default='.', help='Output directory (default: current)')
    parser.add_argument('--theme', '-t', help='Theme folder name (default: derived from URL)')
    parser.add_argument('--theme-prefix', help='Prefix for theme folders when using --url-file')
    parser.add_argument('--list-only', '-l', action='store_true', help='List audio URLs without downloading')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    if not args.url and not args.url_file:
        parser.error("Either URL or --url-file is required")
    
    harvester = AmbientMixerHarvester(args.output, verbose=args.verbose)
    
    if args.list_only and args.url:
        # Just list the audio URLs
        template_id = harvester.get_template_id(args.url)
        if template_id:
            xml_content = harvester.fetch_template_xml(template_id)
            if xml_content:
                mix = harvester.parse_template_xml(xml_content, args.url, template_id)
                if mix:
                    print(f"\nAudio files for: {mix.name}")
                    print(f"Template ID: {template_id}\n")
                    for ch in mix.channels:
                        print(f"{ch.channel_num}. {ch.name}")
                        print(f"   URL: {ch.url}")
                        print(f"   ID: {ch.audio_id}")
                        print(f"   Volume: {ch.volume}%, Balance: {ch.balance}")
                        print()
        return
    
    if args.url_file:
        results = harvester.harvest_from_file(args.url_file, args.theme_prefix)
        print(f"\n{'='*60}")
        print(f"Completed: {len(results)} mixes harvested")
    elif args.url:
        harvester.harvest_url(args.url, args.theme)
    
    print("\nDone!")


if __name__ == '__main__':
    main()
