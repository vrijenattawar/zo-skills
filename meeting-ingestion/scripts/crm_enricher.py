#!/usr/bin/env python3
"""
CRM Enricher Module

Enriches meetings with CRM data and classifies internal/external status.
Handles participant identification with fuzzy matching via LLM.

Usage:
    python3 crm_enricher.py enrich <meeting_folder>
    python3 crm_enricher.py identify-participants <meeting_folder>
    python3 crm_enricher.py classify <meeting_folder>
    python3 crm_enricher.py --help

Classification Logic:
    - If ALL identified participants have is_internal=true → internal
    - If ANY participant has is_internal=false or unknown → external  
    - If unable to identify ANY participant → HITL queue
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
import requests
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Database paths
CRM_DB = Path("./scripts/data/crm.db")
PROFILES_DB = Path("./scripts/data/profiles.db")

# HITL integration
try:
    from scripts.hitl import add_hitl_item
except ImportError:
    logger.warning("HITL module not found - will skip HITL integration")
    add_hitl_item = None


class ParticipantMatch:
    """Represents a participant match result"""
    def __init__(self, input_name: str, matched_name: Optional[str] = None, 
                 email: Optional[str] = None, is_internal: Optional[bool] = None,
                 source: Optional[str] = None, confidence: float = 0.0,
                 company: Optional[str] = None):
        self.input_name = input_name
        self.matched_name = matched_name
        self.email = email
        self.is_internal = is_internal
        self.source = source  # 'crm' or 'profiles'
        self.confidence = confidence
        self.company = company
        
    def is_identified(self) -> bool:
        """True if we successfully identified this participant"""
        return self.matched_name is not None and self.confidence > 0.6
        
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            'input_name': self.input_name,
            'matched_name': self.matched_name,
            'email': self.email,
            'is_internal': self.is_internal,
            'source': self.source,
            'confidence': self.confidence,
            'company': self.company
        }


class CRMEnricher:
    """Main CRM enrichment class"""
    
    def __init__(self):
        self.crm_conn = None
        self.profiles_conn = None
        self._connect_databases()
        
    def _connect_databases(self):
        """Initialize database connections"""
        try:
            self.crm_conn = sqlite3.connect(CRM_DB)
            self.crm_conn.row_factory = sqlite3.Row
            logger.info(f"Connected to CRM database: {CRM_DB}")
        except Exception as e:
            logger.error(f"Failed to connect to CRM database: {e}")
            raise
            
        try:
            self.profiles_conn = sqlite3.connect(PROFILES_DB)
            self.profiles_conn.row_factory = sqlite3.Row
            logger.info(f"Connected to profiles database: {PROFILES_DB}")
        except Exception as e:
            logger.error(f"Failed to connect to profiles database: {e}")
            raise
    
    def get_all_crm_contacts(self) -> List[Dict]:
        """Fetch all CRM contacts for fuzzy matching"""
        cursor = self.crm_conn.cursor()
        cursor.execute("""
            SELECT full_name, email, company, is_internal, category
            FROM individuals 
            WHERE full_name IS NOT NULL AND full_name != ''
        """)
        
        contacts = []
        for row in cursor.fetchall():
            contacts.append({
                'full_name': row['full_name'],
                'email': row['email'],
                'company': row['company'],
                'is_internal': bool(row['is_internal']) if row['is_internal'] is not None else False,
                'category': row['category']
            })
        return contacts
    
    def get_all_profile_contacts(self) -> List[Dict]:
        """Fetch all profile contacts for fuzzy matching"""
        cursor = self.profiles_conn.cursor()
        cursor.execute("""
            SELECT email, name, organization
            FROM profiles 
            WHERE name IS NOT NULL AND name != ''
        """)
        
        contacts = []
        for row in cursor.fetchall():
            contacts.append({
                'name': row['name'],
                'email': row['email'],
                'organization': row['organization'],
                'is_internal': True  # All profiles are internal team members
            })
        return contacts
    
    def llm_fuzzy_match(self, input_names: List[str], crm_contacts: List[Dict], 
                       profile_contacts: List[Dict]) -> List[ParticipantMatch]:
        """Use LLM to perform fuzzy matching of participant names"""
        
        # Prepare the prompt for LLM matching
        prompt = f"""You are helping match meeting participant names to a database of contacts.

INPUT PARTICIPANT NAMES:
{json.dumps(input_names, indent=2)}

CRM CONTACTS (external contacts):
{json.dumps([{'name': c['full_name'], 'email': c.get('email', ''), 'company': c.get('company', ''), 'is_internal': c['is_internal']} for c in crm_contacts], indent=2)}

PROFILE CONTACTS (internal team members):
{json.dumps([{'name': c['name'], 'email': c.get('email', ''), 'organization': c.get('organization', ''), 'is_internal': c['is_internal']} for c in profile_contacts], indent=2)}

For each input name, find the best match from either database. Consider:
- Exact name matches (highest confidence)
- Partial matches (first name, last name, nicknames)
- Common variations (Bob/Robert, Mike/Michael, etc.)
- Fuzzy spelling similarities
- Email domain matching if available

Respond with ONLY a JSON array of match objects, one for each input name:
[
  {{
    "input_name": "exact input name",
    "matched_name": "best matching name or null",
    "email": "email or null",
    "is_internal": true/false/null,
    "source": "crm"/"profiles"/null,
    "confidence": 0.0-1.0,
    "company": "company or organization or null"
  }}
]

Confidence scores:
- 1.0: Exact name match
- 0.9: Very close match (minor variations)
- 0.8: Good match (nickname/common variation)
- 0.7: Partial match (first or last name)
- 0.6: Fuzzy match (spelling similarity)
- <0.6: Poor match (return null for matched_name)

If no reasonable match is found, set matched_name to null and confidence to 0.0.
"""

        try:
            # Call the /zo/ask API for LLM matching
            response = requests.post(
                "<YOUR_WEBHOOK_URL>",
                headers={
                    "authorization": os.environ["ZO_CLIENT_IDENTITY_TOKEN"],
                    "content-type": "application/json"
                },
                json={"input": prompt}
            )
            
            if response.status_code != 200:
                logger.error(f"LLM API call failed: {response.status_code} - {response.text}")
                # Return default unmatched results
                return [ParticipantMatch(name) for name in input_names]
            
            result = response.json()
            output_text = result.get("output", "")
            
            # Parse the JSON response
            try:
                # Handle markdown code blocks
                if output_text.strip().startswith('```'):
                    # Extract JSON from code block
                    lines = output_text.strip().split('\n')
                    json_lines = []
                    in_code_block = False
                    for line in lines:
                        if line.strip().startswith('```'):
                            in_code_block = not in_code_block
                            continue
                        if in_code_block:
                            json_lines.append(line)
                    json_text = '\n'.join(json_lines)
                else:
                    json_text = output_text
                
                matches_data = json.loads(json_text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {e}")
                logger.debug(f"LLM response was: {output_text}")
                return [ParticipantMatch(name) for name in input_names]
            
            # Convert to ParticipantMatch objects
            matches = []
            for match_data in matches_data:
                match = ParticipantMatch(
                    input_name=match_data["input_name"],
                    matched_name=match_data.get("matched_name"),
                    email=match_data.get("email"),
                    is_internal=match_data.get("is_internal"),
                    source=match_data.get("source"),
                    confidence=match_data.get("confidence", 0.0),
                    company=match_data.get("company")
                )
                matches.append(match)
            
            logger.info(f"LLM fuzzy matching completed for {len(matches)} participants")
            return matches
            
        except Exception as e:
            logger.error(f"LLM fuzzy matching failed: {e}")
            # Return default unmatched results
            return [ParticipantMatch(name) for name in input_names]
    
    def identify_participants(self, meeting_folder: Path) -> List[ParticipantMatch]:
        """Identify participants from meeting manifest"""
        
        manifest_path = meeting_folder / "manifest.json"
        if not manifest_path.exists():
            logger.error(f"No manifest.json found in {meeting_folder}")
            return []
        
        try:
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read manifest: {e}")
            return []
        
        # Extract participant names from manifest
        participants_data = manifest.get('participants', {})
        
        # Handle v3 manifest format
        if isinstance(participants_data, dict):
            # V3 format: participants.identified is the array
            participants_list = participants_data.get('identified', [])
            if not participants_list:
                logger.warning(f"No identified participants found in manifest for {meeting_folder}")
                return []
        else:
            # Legacy format: participants is a direct array
            participants_list = participants_data if isinstance(participants_data, list) else []
            if not participants_list:
                logger.warning(f"No participants found in manifest for {meeting_folder}")
                return []
        
        input_names = []
        for participant in participants_list:
            if isinstance(participant, str):
                input_names.append(participant)
            elif isinstance(participant, dict):
                name = participant.get('name', participant.get('participant', ''))
                if name:
                    input_names.append(name)
        
        if not input_names:
            logger.warning(f"No valid participant names found in manifest for {meeting_folder}")
            return []
        
        logger.info(f"Found {len(input_names)} participants to identify: {input_names}")
        
        # Get all contacts for fuzzy matching
        crm_contacts = self.get_all_crm_contacts()
        profile_contacts = self.get_all_profile_contacts()
        
        logger.info(f"Loaded {len(crm_contacts)} CRM contacts and {len(profile_contacts)} profile contacts")
        
        # Perform LLM-based fuzzy matching
        matches = self.llm_fuzzy_match(input_names, crm_contacts, profile_contacts)
        
        return matches
    
    def classify_meeting(self, matches: List[ParticipantMatch]) -> Tuple[str, str]:
        """
        Classify meeting as internal/external based on participant matches
        
        Returns:
            (classification, reason) where classification is 'internal'|'external'|'unknown'
        """
        
        identified_matches = [m for m in matches if m.is_identified()]
        unidentified_matches = [m for m in matches if not m.is_identified()]
        
        # If we can't identify ANY participants, mark for HITL
        if not identified_matches:
            return 'unknown', f"Unable to identify any participants ({len(unidentified_matches)} unidentified)"
        
        # Check internal status of identified participants
        internal_count = 0
        external_count = 0
        
        for match in identified_matches:
            if match.is_internal:
                internal_count += 1
            else:
                external_count += 1
        
        # Classification logic
        if external_count > 0:
            # ANY external participant makes it external
            reason = f"{external_count} external, {internal_count} internal participants identified"
            return 'external', reason
        elif internal_count > 0:
            # ALL identified participants are internal
            if unidentified_matches:
                # But we have unidentified participants - could be external
                reason = f"{internal_count} internal participants, {len(unidentified_matches)} unidentified"
                return 'external', reason  # Conservative: assume external if uncertain
            else:
                # All participants identified and internal
                reason = f"All {internal_count} participants are internal"
                return 'internal', reason
        else:
            # No internal participants (shouldn't happen if we have identified matches)
            return 'unknown', "No internal status information available"
    
    def add_to_hitl_queue(self, meeting_folder: Path, matches: List[ParticipantMatch], 
                         classification: str, reason: str):
        """Add unidentified participants to HITL queue"""
        
        if not add_hitl_item:
            logger.warning("HITL module not available - skipping queue addition")
            return
        
        unidentified_matches = [m for m in matches if not m.is_identified()]
        
        if not unidentified_matches and classification != 'unknown':
            return  # Nothing to add to queue
        
        meeting_id = meeting_folder.name
        unknown_speakers = [m.input_name for m in unidentified_matches]
        identified_speakers = [m.matched_name for m in matches if m.is_identified()]
        
        # Read a sample of the transcript if available
        transcript_excerpt = ""
        transcript_files = list(meeting_folder.glob("*transcript*"))
        if transcript_files:
            try:
                with open(transcript_files[0], 'r') as f:
                    content = f.read()
                    # Get first 500 characters as excerpt
                    transcript_excerpt = content[:500] + "..." if len(content) > 500 else content
            except Exception as e:
                logger.warning(f"Failed to read transcript for excerpt: {e}")
        
        context = {
            "transcript_excerpt": transcript_excerpt,
            "known_participants": identified_speakers,
            "unknown_speakers": unknown_speakers,
            "confidence_scores": {m.input_name: m.confidence for m in matches},
            "classification_reason": reason
        }
        
        try:
            add_hitl_item(
                meeting_id=meeting_id,
                reason="unidentified_participant",
                context=context
            )
            logger.info(f"Added {len(unknown_speakers)} unidentified participants to HITL queue for {meeting_id}")
        except Exception as e:
            logger.error(f"Failed to add to HITL queue: {e}")
    
    def enrich_meeting(self, meeting_folder: Path) -> Dict:
        """
        Complete enrichment workflow for a meeting
        
        Returns enrichment result with participant matches and classification
        """
        
        # Ensure meeting_folder is a Path object
        if not isinstance(meeting_folder, Path):
            meeting_folder = Path(meeting_folder)
        
        logger.info(f"Starting CRM enrichment for {meeting_folder}")
        
        # Step 1: Identify participants
        matches = self.identify_participants(meeting_folder)
        
        if not matches:
            logger.error(f"No participants found to enrich for {meeting_folder}")
            return {
                'status': 'error',
                'error': 'No participants found',
                'participants': [],
                'classification': 'unknown',
                'classification_reason': 'No participants to classify'
            }
        
        # Step 2: Classify meeting
        classification, classification_reason = self.classify_meeting(matches)
        
        # Step 3: Handle unidentified participants
        if classification == 'unknown' or any(not m.is_identified() for m in matches):
            self.add_to_hitl_queue(meeting_folder, matches, classification, classification_reason)
        
        # Step 4: Write enrichment results to manifest
        self.update_manifest_with_enrichment(meeting_folder, matches, classification, classification_reason)
        
        result = {
            'status': 'success',
            'participants': [m.to_dict() for m in matches],
            'classification': classification,
            'classification_reason': classification_reason,
            'identified_count': len([m for m in matches if m.is_identified()]),
            'unidentified_count': len([m for m in matches if not m.is_identified()])
        }
        
        logger.info(f"CRM enrichment completed for {meeting_folder}: {classification} ({result['identified_count']} identified, {result['unidentified_count']} unidentified)")
        
        return result
    
    def update_manifest_with_enrichment(self, meeting_folder: Path, matches: List[ParticipantMatch], 
                                       classification: str, classification_reason: str):
        """Update meeting manifest with enrichment results"""
        
        manifest_path = meeting_folder / "manifest.json"
        
        try:
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read manifest for update: {e}")
            return
        
        # Add CRM enrichment section
        crm_enrichment = {
            'enriched_at': datetime.now(UTC).isoformat(),
            'classification': classification,
            'classification_reason': classification_reason,
            'participant_matches': [m.to_dict() for m in matches],
            'identified_count': len([m for m in matches if m.is_identified()]),
            'unidentified_count': len([m for m in matches if not m.is_identified()])
        }
        
        manifest['crm_enrichment'] = crm_enrichment
        
        # Update meeting type if we have a confident classification
        if classification in ['internal', 'external']:
            manifest['meeting_type'] = classification
        
        try:
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            logger.info(f"Updated manifest with CRM enrichment for {meeting_folder}")
        except Exception as e:
            logger.error(f"Failed to update manifest: {e}")
    
    def close(self):
        """Close database connections"""
        if self.crm_conn:
            self.crm_conn.close()
        if self.profiles_conn:
            self.profiles_conn.close()


def main():
    """Main CLI interface"""
    
    parser = argparse.ArgumentParser(
        description="CRM Enricher - Enrich meetings with CRM data and classify internal/external",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('command', choices=['enrich', 'identify-participants', 'classify'],
                       help='Command to execute')
    parser.add_argument('meeting_folder', type=Path,
                       help='Path to meeting folder containing manifest.json')
    parser.add_argument('--output', '-o', type=Path,
                       help='Output file for results (JSON format)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if not args.meeting_folder.exists():
        logger.error(f"Meeting folder does not exist: {args.meeting_folder}")
        sys.exit(1)
    
    if not (args.meeting_folder / "manifest.json").exists():
        logger.error(f"No manifest.json found in {args.meeting_folder}")
        sys.exit(1)
    
    try:
        enricher = CRMEnricher()
        
        if args.command == 'enrich':
            result = enricher.enrich_meeting(args.meeting_folder)
        elif args.command == 'identify-participants':
            matches = enricher.identify_participants(args.meeting_folder)
            result = {
                'participants': [m.to_dict() for m in matches],
                'identified_count': len([m for m in matches if m.is_identified()]),
                'unidentified_count': len([m for m in matches if not m.is_identified()])
            }
        elif args.command == 'classify':
            matches = enricher.identify_participants(args.meeting_folder)
            classification, reason = enricher.classify_meeting(matches)
            result = {
                'classification': classification,
                'classification_reason': reason,
                'participants': [m.to_dict() for m in matches]
            }
        
        # Output results
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(result, f, indent=2)
            logger.info(f"Results written to {args.output}")
        else:
            print(json.dumps(result, indent=2))
        
        enricher.close()
        
    except Exception as e:
        logger.error(f"Command failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()