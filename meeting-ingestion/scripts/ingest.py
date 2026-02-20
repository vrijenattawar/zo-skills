#!/usr/bin/env python3
"""
Ingest Module for Meeting System v3

Normalizes various transcript formats and creates v3 manifests with microsummaries.
Handles .md, .txt, .docx, .jsonl formats.

Usage:
    python3 ingest.py <file_or_folder> [--dry-run]

Examples:
    python3 ingest.py /path/to/transcript.md
    python3 ingest.py /path/to/inbox_folder --dry-run
    python3 ingest.py transcript.jsonl
"""

import argparse
import json
import os
import sys
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import requests

# Add workspace to path for imports
sys.path.insert(0, '.')

# For docx handling
try:
    from docx import Document
except ImportError:
    Document = None


class IngestError(Exception):
    """Custom exception for ingest errors"""
    pass


class TranscriptIngestor:
    """Main ingest class that handles various transcript formats"""
    
    def __init__(self):
        self.zo_api_url = "<YOUR_WEBHOOK_URL>"
        self.zo_token = os.environ.get("ZO_CLIENT_IDENTITY_TOKEN")
        if not self.zo_token:
            raise IngestError("ZO_CLIENT_IDENTITY_TOKEN environment variable not set")
        
        self.supported_formats = ['.md', '.txt', '.docx', '.jsonl']
    
    def ingest_file(self, file_path: str, dry_run: bool = False) -> Dict:
        """
        Ingest a single file and create a meeting folder with v3 manifest
        
        Args:
            file_path: Path to the transcript file
            dry_run: If True, don't create files, just show what would be done
            
        Returns:
            Dictionary with ingest results
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise IngestError(f"File not found: {file_path}")
        
        if file_path.suffix.lower() not in self.supported_formats:
            raise IngestError(f"Unsupported format: {file_path.suffix}. Supported: {self.supported_formats}")
        
        print(f"Ingesting: {file_path}")
        
        # Extract transcript text based on format
        transcript_text = self._extract_transcript(file_path)
        
        if len(transcript_text.strip()) < 100:
            raise IngestError(f"Transcript too short ({len(transcript_text)} chars), minimum 100 characters")
        
        # Generate microsummary via /zo/ask
        microsummary = self._generate_microsummary(transcript_text)
        
        # Extract meeting metadata from transcript
        meeting_metadata = self._extract_meeting_metadata(transcript_text, file_path)
        
        # Generate meeting ID
        meeting_id = self._generate_meeting_id(meeting_metadata, file_path)
        
        # Create meeting folder structure
        meeting_folder = file_path.parent / meeting_id
        
        if dry_run:
            print(f"[DRY-RUN] Would create folder: {meeting_folder}")
            print(f"[DRY-RUN] Would write transcript.md")
            print(f"[DRY-RUN] Would write manifest.json")
            print(f"[DRY-RUN] Microsummary: {microsummary[:100]}...")
            return {
                "status": "dry_run",
                "meeting_id": meeting_id,
                "folder_path": str(meeting_folder),
                "microsummary": microsummary
            }
        
        # Create folder
        meeting_folder.mkdir(exist_ok=True)
        
        # Write normalized transcript
        transcript_path = meeting_folder / "transcript.md"
        with open(transcript_path, 'w', encoding='utf-8') as f:
            f.write(transcript_text)
        
        # Create v3 manifest
        manifest = self._create_v3_manifest(
            meeting_id=meeting_id,
            meeting_metadata=meeting_metadata,
            microsummary=microsummary,
            original_filename=file_path.name
        )
        
        manifest_path = meeting_folder / "manifest.json"
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)
        
        print(f"✓ Created meeting folder: {meeting_folder}")
        print(f"✓ Wrote transcript.md ({len(transcript_text)} chars)")
        print(f"✓ Wrote manifest.json")
        print(f"✓ Status: ingested")
        
        return {
            "status": "completed",
            "meeting_id": meeting_id,
            "folder_path": str(meeting_folder),
            "transcript_chars": len(transcript_text),
            "microsummary": microsummary
        }
    
    def ingest_folder(self, folder_path: str, dry_run: bool = False) -> Dict:
        """
        Ingest all supported files in a folder
        
        Args:
            folder_path: Path to folder containing transcript files
            dry_run: If True, don't create files, just show what would be done
            
        Returns:
            Dictionary with ingest results for all files
        """
        folder_path = Path(folder_path)
        
        if not folder_path.is_dir():
            raise IngestError(f"Not a directory: {folder_path}")
        
        # Find all supported files
        files_to_ingest = []
        for ext in self.supported_formats:
            files_to_ingest.extend(folder_path.glob(f"*{ext}"))
        
        if not files_to_ingest:
            print(f"No supported files found in {folder_path}")
            print(f"Looking for: {self.supported_formats}")
            return {"status": "no_files", "files_processed": 0}
        
        print(f"Found {len(files_to_ingest)} files to ingest")
        
        results = []
        for file_path in files_to_ingest:
            try:
                result = self.ingest_file(file_path, dry_run)
                results.append(result)
            except IngestError as e:
                print(f"✗ Failed to ingest {file_path}: {e}")
                results.append({
                    "status": "failed",
                    "file": str(file_path),
                    "error": str(e)
                })
        
        successful = [r for r in results if r["status"] in ["completed", "dry_run"]]
        failed = [r for r in results if r["status"] == "failed"]
        
        print(f"\nIngest summary:")
        print(f"✓ Successful: {len(successful)}")
        print(f"✗ Failed: {len(failed)}")
        
        return {
            "status": "completed",
            "files_processed": len(files_to_ingest),
            "successful": len(successful),
            "failed": len(failed),
            "results": results
        }
    
    def _extract_transcript(self, file_path: Path) -> str:
        """Extract transcript text from various formats"""
        suffix = file_path.suffix.lower()
        
        if suffix in ['.md', '.txt']:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        elif suffix == '.docx':
            if Document is None:
                raise IngestError("python-docx not available. Install with: pip install python-docx")
            
            doc = Document(file_path)
            text_parts = []
            for paragraph in doc.paragraphs:
                text_parts.append(paragraph.text)
            return '\n'.join(text_parts)
        
        elif suffix == '.jsonl':
            # Convert JSONL to markdown format (speaker: text)
            lines = []
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        if isinstance(data, dict):
                            # Try common jsonl formats
                            speaker = data.get('speaker', data.get('name', data.get('user', 'Unknown')))
                            text = data.get('text', data.get('content', data.get('message', '')))
                            if text:
                                lines.append(f"{speaker}: {text}")
                        else:
                            # If it's just text, add it as is
                            lines.append(str(data))
                    except json.JSONDecodeError:
                        # If line isn't valid JSON, treat as plain text
                        line = line.strip()
                        if line:
                            lines.append(line)
            
            return '\n'.join(lines)
        
        else:
            raise IngestError(f"Unsupported format: {suffix}")
    
    def _generate_microsummary(self, transcript_text: str) -> str:
        """Generate a one-paragraph microsummary using /zo/ask"""
        # Truncate transcript if too long (to stay within token limits)
        if len(transcript_text) > 8000:
            transcript_text = transcript_text[:8000] + "...\n[Transcript truncated for summarization]"
        
        prompt = f"""Please read this meeting transcript and generate a concise one-paragraph microsummary.

The summary should:
- Be exactly one paragraph (no line breaks)
- Be 2-4 sentences long
- Capture the main topic, key participants, and primary outcomes
- Use clear, professional language
- Focus on what was discussed and decided, not who said what

Transcript:
{transcript_text}

Respond with just the microsummary paragraph, nothing else."""
        
        try:
            response = requests.post(
                self.zo_api_url,
                headers={
                    "authorization": self.zo_token,
                    "content-type": "application/json"
                },
                json={"input": prompt},
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                summary = result.get("output", "").strip()
                
                # Basic validation
                if len(summary) < 50:
                    return "Meeting summary could not be generated - transcript may be too short or unclear."
                
                # Ensure it's one paragraph
                summary = ' '.join(summary.split('\n'))
                
                return summary
            else:
                print(f"Warning: Failed to generate microsummary (HTTP {response.status_code})")
                return "Meeting summary could not be generated due to API error."
        
        except Exception as e:
            print(f"Warning: Failed to generate microsummary: {e}")
            return "Meeting summary could not be generated."
    
    def _extract_meeting_metadata(self, transcript_text: str, file_path: Path) -> Dict:
        """Extract meeting metadata from transcript and filename"""
        
        # Try to extract date from filename first
        filename = file_path.stem
        date_patterns = [
            r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD
            r'(\d{2}-\d{2}-\d{4})',  # MM-DD-YYYY  
            r'(\d{1,2}/\d{1,2}/\d{4})',  # M/D/YYYY
        ]
        
        extracted_date = None
        for pattern in date_patterns:
            match = re.search(pattern, filename)
            if match:
                date_str = match.group(1)
                try:
                    if '-' in date_str and len(date_str.split('-')[0]) == 4:
                        extracted_date = date_str  # Already YYYY-MM-DD
                    elif '-' in date_str:
                        # MM-DD-YYYY to YYYY-MM-DD
                        parts = date_str.split('-')
                        extracted_date = f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
                    elif '/' in date_str:
                        # M/D/YYYY to YYYY-MM-DD
                        parts = date_str.split('/')
                        extracted_date = f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
                    break
                except:
                    continue
        
        # Default to today if no date found
        if not extracted_date:
            extracted_date = datetime.now().strftime('%Y-%m-%d')
        
        # Extract basic info from transcript (simplified - real implementation might use LLM)
        duration = 30  # Default duration in minutes
        
        # Try to estimate duration from transcript length (rough heuristic)
        word_count = len(transcript_text.split())
        if word_count > 0:
            # Rough estimate: 150 words per minute of speech
            estimated_minutes = max(15, min(120, word_count // 150))
            duration = estimated_minutes
        
        # Try to extract title from filename
        title_parts = []
        for part in filename.split('_'):
            # Skip date-like parts
            if not re.match(r'(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4})', part):
                # Clean up part (replace hyphens with spaces, title case)
                clean_part = part.replace('-', ' ').replace('_', ' ')
                if clean_part and not clean_part.isdigit():
                    title_parts.append(clean_part)
        
        title = ' '.join(title_parts) if title_parts else "Meeting"
        
        # Convert title to proper case
        title = ' '.join(word.capitalize() for word in title.split())
        
        return {
            "date": extracted_date,
            "time_utc": "12:00:00",  # Default time
            "duration_minutes": duration,
            "title": title,
            "type": "external"  # Default type, will be determined later
        }
    
    def _generate_meeting_id(self, meeting_metadata: Dict, file_path: Path) -> str:
        """Generate a meeting ID in format YYYY-MM-DD_Meeting-Name"""
        date = meeting_metadata["date"]
        title = meeting_metadata["title"]
        
        # Clean title for use in ID
        title_clean = re.sub(r'[^\w\s-]', '', title)  # Remove special chars
        title_clean = re.sub(r'\s+', '-', title_clean.strip())  # Replace spaces with hyphens
        title_clean = title_clean.lower()
        
        # Ensure title isn't too long
        if len(title_clean) > 40:
            title_clean = title_clean[:40].rstrip('-')
        
        # Ensure title isn't empty
        if not title_clean:
            title_clean = file_path.stem.lower()
            title_clean = re.sub(r'[^\w\s-]', '', title_clean)
            title_clean = re.sub(r'\s+', '-', title_clean)[:40]
        
        if not title_clean:
            title_clean = "meeting"
        
        meeting_id = f"{date}_{title_clean}"
        
        # Ensure ID is valid (no double hyphens, etc.)
        meeting_id = re.sub(r'-+', '-', meeting_id)
        meeting_id = meeting_id.strip('-')
        
        return meeting_id
    
    def _create_v3_manifest(self, meeting_id: str, meeting_metadata: Dict, microsummary: str, original_filename: str) -> Dict:
        """Create a v3 manifest with initial state"""
        now = datetime.now(timezone.utc).isoformat()
        
        manifest = {
            "$schema": "manifest-v3",
            "meeting_id": meeting_id,
            "status": "ingested",
            "status_history": [
                {"status": "raw", "at": now},
                {"status": "ingested", "at": now}
            ],
            "source": {
                "type": "manual",  # Default for now
                "original_filename": original_filename,
                "ingested_at": now
            },
            "meeting": {
                "date": meeting_metadata["date"],
                "time_utc": meeting_metadata["time_utc"],
                "duration_minutes": meeting_metadata["duration_minutes"],
                "title": meeting_metadata["title"],
                "type": meeting_metadata["type"],
                "summary": microsummary
            },
            "participants": {
                "identified": [],
                "unidentified": [],
                "confidence": 0.0
            },
            "calendar_match": None,
            "quality_gate": {
                "passed": False,
                "checks": {
                    "has_transcript": True,
                    "participants_identified": False,
                    "meeting_type_determined": False,
                    "no_hitl_pending": True
                },
                "score": 0.25  # Only transcript check passes initially
            },
            "blocks": {
                "policy": "external_standard",  # Default policy, will be set properly by identify module
                "requested": [],
                "generated": [],
                "failed": [],
                "skipped": []
            },
            "hitl": {
                "queue_id": None,
                "reason": None,
                "resolved_at": None
            },
            "timestamps": {
                "created_at": now,
                "ingested_at": now,
                "identified_at": None,
                "gated_at": None,
                "processed_at": None,
                "archived_at": None
            }
        }
        
        return manifest


def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(
        description="Ingest meeting transcripts and create v3 manifests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s /path/to/transcript.md
    %(prog)s /path/to/inbox_folder --dry-run
    %(prog)s transcript.jsonl
        """
    )
    
    parser.add_argument(
        'path',
        help='File or folder to ingest'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without creating files'
    )
    
    args = parser.parse_args()
    
    try:
        ingestor = TranscriptIngestor()
        
        input_path = Path(args.path)
        
        if input_path.is_file():
            result = ingestor.ingest_file(args.path, args.dry_run)
            print(f"\nResult: {result['status']}")
            if result['status'] == 'completed':
                print(f"Meeting ID: {result['meeting_id']}")
                print(f"Folder: {result['folder_path']}")
        
        elif input_path.is_dir():
            result = ingestor.ingest_folder(args.path, args.dry_run)
            print(f"\nOverall result: {result['status']}")
            
        else:
            print(f"Error: Path not found: {args.path}")
            sys.exit(1)
    
    except IngestError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()