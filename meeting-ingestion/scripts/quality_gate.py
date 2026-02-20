#!/usr/bin/env python3
"""
Quality Gate Module for Meeting Processing Pipeline

Validates meeting readiness before block generation using comprehensive quality checks
defined in the quality harness specification.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import unicodedata

# Import HITL functions
from hitl import add_hitl_item


def extract_conversation_content(content: str) -> str:
    """Extract actual spoken content from transcript."""
    lines = content.split('\n')
    clean_lines = []
    
    for line in lines:
        # Skip markdown headers
        if line.startswith('#'):
            continue
            
        # Skip metadata lines like "**Date:** February 1, 2026"
        if re.match(r'\*\*[A-Za-z\s]+:\*\*', line):
            continue
            
        # Skip horizontal rules
        if re.match(r'^-{3,}$', line.strip()):
            continue
            
        # Process speaker lines with timestamps like "**V [00:00:15]:**"
        speaker_match = re.match(r'\*\*([A-Za-z\s]+)\s*\[[\d:]+\]:\*\*\s*(.*)', line)
        if speaker_match:
            spoken_text = speaker_match.group(2).strip()
            if spoken_text:
                clean_lines.append(spoken_text)
            continue
            
        # Process simple speaker lines like "Speaker Name: content"
        simple_speaker_match = re.match(r'^([A-Za-z\s]+):\s*(.*)', line)
        if simple_speaker_match:
            spoken_text = simple_speaker_match.group(2).strip()
            if spoken_text:
                clean_lines.append(spoken_text)
            continue
            
        # Keep other content lines if they have meaningful text
        line = line.strip()
        if line and not re.match(r'^[\s\-\*]*$', line):
            clean_lines.append(line)
    
    return ' '.join(clean_lines)

def old_extract_conversation_content(content: str) -> str:
    """Extract actual spoken content from transcript."""
    # Strip metadata, timestamps, speaker labels
    clean_content = re.sub(r'^---.*?^---', '', content, flags=re.MULTILINE | re.DOTALL)
    clean_content = re.sub(r'\[?\d{2}:\d{2}:\d{2}\]?', '', clean_content)
    clean_content = re.sub(r'^[A-Za-z\s]+:\s*', '', clean_content, flags=re.MULTILINE)
    clean_content = re.sub(r'\s+', ' ', clean_content).strip()
    return clean_content


class QualityCheck:
    """Base class for quality checks."""
    
    def __init__(self, name: str, threshold: float = 0.7):
        self.name = name
        self.threshold = threshold
        self.score = 0.0
        self.passed = False
        self.warnings = []
        self.errors = []
        self.escalate_hitl = False
    
    def execute(self, manifest: Dict, transcript_path: Optional[Path] = None) -> bool:
        """Execute the quality check. Returns True if passed."""
        raise NotImplementedError()
    
    def to_dict(self) -> Dict:
        """Convert check result to dictionary."""
        return {
            "name": self.name,
            "score": self.score,
            "passed": self.passed,
            "threshold": self.threshold,
            "warnings": self.warnings,
            "errors": self.errors,
            "escalate_hitl": self.escalate_hitl
        }


class TranscriptLengthCheck(QualityCheck):
    """Check transcript has sufficient content for analysis."""
    
    def __init__(self):
        super().__init__("transcript_length", threshold=300)
    
    def execute(self, manifest: Dict, transcript_path: Optional[Path] = None) -> bool:
        if not transcript_path or not transcript_path.exists():
            self.errors.append("Transcript file not found")
            self.escalate_hitl = True
            return False
        
        try:
            with open(transcript_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Strip metadata, timestamps, speaker labels
            clean_content = extract_conversation_content(content)
            
            char_count = len(clean_content)
            self.score = min(1.0, char_count / 1000)  # Score based on content richness
            
            if char_count >= self.threshold:
                self.passed = True
            elif char_count >= 100:
                self.warnings.append(f"Transcript short ({char_count} chars) but processable")
            else:
                self.errors.append(f"Transcript too short ({char_count} chars) for meaningful processing")
                self.escalate_hitl = True
            
            return self.passed
            
        except Exception as e:
            self.errors.append(f"Error reading transcript: {str(e)}")
            self.escalate_hitl = True
            return False


class TranscriptFormatCheck(QualityCheck):
    """Validate transcript format and encoding."""
    
    def __init__(self):
        super().__init__("transcript_format", threshold=0.8)
    
    def execute(self, manifest: Dict, transcript_path: Optional[Path] = None) -> bool:
        if not transcript_path or not transcript_path.exists():
            self.errors.append("Transcript file not found")
            self.escalate_hitl = True
            return False
        
        try:
            with open(transcript_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for speaker patterns
            speaker_patterns = [
                r'^[A-Za-z\s]+:\s*',  # "Speaker Name: "
                r'\[[A-Za-z\s]+\]',   # "[Speaker]"
                r'\d{2}:\d{2}:\d{2}', # Timestamps
            ]
            
            pattern_matches = 0
            for pattern in speaker_patterns:
                if re.search(pattern, content, re.MULTILINE):
                    pattern_matches += 1
            
            # Check for encoding issues
            has_replacement_chars = '�' in content
            
            # Check if it's mostly readable text
            printable_ratio = sum(1 for c in content if c.isprintable() or c.isspace()) / len(content)
            
            self.score = (pattern_matches / len(speaker_patterns) + printable_ratio) / 2
            
            if has_replacement_chars:
                self.errors.append("Encoding corruption detected (replacement characters)")
                self.escalate_hitl = True
            elif printable_ratio < 0.9:
                self.errors.append("Non-text content detected")
                self.escalate_hitl = True
            elif pattern_matches == 0:
                self.warnings.append("No speaker patterns detected")
            
            self.passed = self.score >= self.threshold and not has_replacement_chars
            return self.passed
            
        except UnicodeDecodeError:
            self.errors.append("UTF-8 encoding error")
            self.escalate_hitl = True
            return False
        except Exception as e:
            self.errors.append(f"Error validating transcript format: {str(e)}")
            return False


class DurationConsistencyCheck(QualityCheck):
    """Check transcript length matches expected meeting duration."""
    
    def __init__(self):
        super().__init__("meeting_duration_consistency", threshold=0.5)
    
    def execute(self, manifest: Dict, transcript_path: Optional[Path] = None) -> bool:
        if not transcript_path or not transcript_path.exists():
            self.errors.append("Transcript file not found")
            return False
        
        try:
            duration_minutes = manifest.get('meeting', {}).get('duration_minutes', 0)
            if duration_minutes <= 0:
                self.warnings.append("Meeting duration not specified")
                self.score = 0.5
                self.passed = True  # Not a hard failure
                return True
            
            with open(transcript_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Strip metadata, timestamps, speaker labels
            clean_content = extract_conversation_content(content)
            
            # Count words (rough approximation)
            word_count = len(re.findall(r'\b\w+\b', clean_content))
            
            # Expected: 75-300 words per minute
            expected_min = duration_minutes * 75
            expected_max = duration_minutes * 300
            expected_avg = duration_minutes * 150
            
            if expected_min <= word_count <= expected_max:
                self.score = 1.0
                self.passed = True
            else:
                ratio = word_count / expected_avg if expected_avg > 0 else 0
                self.score = min(1.0, max(0.1, 1 - abs(1 - ratio)))
                
                if ratio < 0.2 or ratio > 6.0:
                    self.errors.append(f"Suspicious length discrepancy: {word_count} words for {duration_minutes}min meeting")
                    self.escalate_hitl = True
                elif ratio < 0.3 or ratio > 3.0:
                    self.warnings.append(f"Length mismatch: {word_count} words for {duration_minutes}min meeting")
                
                self.passed = self.score >= self.threshold
            
            return self.passed
            
        except Exception as e:
            self.errors.append(f"Error checking duration consistency: {str(e)}")
            return False


class ParticipantConfidenceCheck(QualityCheck):
    """Check participant identification confidence."""
    
    def __init__(self):
        super().__init__("participant_confidence", threshold=0.7)
    
    def execute(self, manifest: Dict, transcript_path: Optional[Path] = None) -> bool:
        participants = manifest.get('participants', {})
        confidence = participants.get('confidence', 0.0)
        
        self.score = confidence
        
        if confidence >= self.threshold:
            self.passed = True
        elif confidence >= 0.4:
            self.warnings.append(f"Low participant confidence: {confidence:.2f}")
        else:
            self.errors.append(f"Very low participant confidence: {confidence:.2f}")
            self.escalate_hitl = True
        
        self.passed = confidence >= self.threshold
        return self.passed


class HostIdentifiedCheck(QualityCheck):
    """Validate meeting host is identified."""
    
    def __init__(self):
        super().__init__("host_identified", threshold=1.0)
    
    def execute(self, manifest: Dict, transcript_path: Optional[Path] = None) -> bool:
        participants = manifest.get('participants', {})
        identified = participants.get('identified', [])
        
        has_host = any(p.get('role') == 'host' for p in identified)
        
        self.score = 1.0 if has_host else 0.0
        self.passed = has_host
        
        if not has_host:
            self.errors.append("No host identified")
            # Determine escalation based on meeting type
            meeting_type = manifest.get('meeting', {}).get('type')
            if meeting_type == 'external':
                self.escalate_hitl = True
        
        return self.passed


class ExternalParticipantVerificationCheck(QualityCheck):
    """Verify external participants are properly identified."""
    
    def __init__(self):
        super().__init__("external_participant_verification", threshold=1.0)
    
    def execute(self, manifest: Dict, transcript_path: Optional[Path] = None) -> bool:
        meeting_type = manifest.get('meeting', {}).get('type')
        participants = manifest.get('participants', {})
        identified = participants.get('identified', [])
        
        if meeting_type == 'external':
            # External meetings should have at least one non-V participant
            external_participants = [p for p in identified if p.get('name', '').lower() != 'v']
            has_external = len(external_participants) > 0
            
            # Check for generic speaker names
            generic_names = [p for p in identified if re.match(r'Speaker \d+', p.get('name', ''))]
            has_generic = len(generic_names) > 0
            
            if has_external and not has_generic:
                self.score = 1.0
                self.passed = True
            elif has_external:
                self.score = 0.7
                self.warnings.append("External meeting has generic speaker names")
                self.passed = False
            else:
                self.score = 0.0
                self.errors.append("External meeting with only V identified")
                self.escalate_hitl = True
                self.passed = False
        
        elif meeting_type == 'internal':
            # Internal meetings should have known participants
            unknown_external = [p for p in identified if not p.get('email')]
            if unknown_external:
                self.score = 0.7
                self.warnings.append("Internal meeting with unidentified participants")
            else:
                self.score = 1.0
                self.passed = True
        
        else:
            # Unknown meeting type
            self.score = 0.5
            self.warnings.append("Meeting type not specified")
            self.passed = True  # Not a hard failure
        
        return self.passed


class CalendarMatchScoreCheck(QualityCheck):
    """Validate calendar event matching."""
    
    def __init__(self):
        super().__init__("calendar_match_score", threshold=0.6)
    
    def execute(self, manifest: Dict, transcript_path: Optional[Path] = None) -> bool:
        calendar_match = manifest.get('calendar_match')
        
        if not calendar_match:
            self.score = 0.0
            self.warnings.append("No calendar match attempted")
            self.passed = True  # Not required for all meetings
            return True
        
        confidence = calendar_match.get('confidence', 0.0)
        method = calendar_match.get('method', '')
        
        self.score = confidence
        
        if confidence >= self.threshold:
            self.passed = True
        elif confidence >= 0.3:
            self.warnings.append(f"Low calendar match confidence: {confidence:.2f} ({method})")
            self.passed = False
        else:
            self.errors.append(f"Very low calendar match confidence: {confidence:.2f}")
            self.escalate_hitl = True
            self.passed = False
        
        return self.passed


class MeetingTypeConsistencyCheck(QualityCheck):
    """Check meeting type aligns with participants."""
    
    def __init__(self):
        super().__init__("meeting_type_consistency", threshold=1.0)
    
    def execute(self, manifest: Dict, transcript_path: Optional[Path] = None) -> bool:
        meeting_type = manifest.get('meeting', {}).get('type')
        participants = manifest.get('participants', {})
        identified = participants.get('identified', [])
        
        if not meeting_type:
            self.score = 0.0
            self.warnings.append("Meeting type not specified")
            self.passed = True  # Not a hard failure
            return True
        
        # Check consistency
        external_participants = [p for p in identified if not p.get('email') or '@' not in p.get('email', '')]
        has_external = len(external_participants) > 0
        
        if meeting_type == 'external' and has_external:
            self.score = 1.0
            self.passed = True
        elif meeting_type == 'internal' and not has_external:
            self.score = 1.0
            self.passed = True
        else:
            self.score = 0.0
            self.errors.append(f"Meeting type '{meeting_type}' inconsistent with participant roster")
            if has_external:
                self.escalate_hitl = True  # Ambiguous participant roster
            self.passed = False
        
        return self.passed


class QualityGate:
    """Main quality gate implementation."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config = self._load_config(config_path)
        self.checks = self._init_checks()
        self.overall_score = 0.0
        self.passed = False
        self.warnings = []
        self.errors = []
        
    def _load_config(self, config_path: Optional[Path]) -> Dict:
        """Load quality gate configuration."""
        default_config = {
            "enabled": True,
            "overall_threshold": 0.8,
            "retry_max_attempts": 3,
            "hitl_escalation": True,
            "checks_enabled": {
                "transcript_length": True,
                "transcript_format": True,
                "meeting_duration_consistency": True,
                "participant_confidence": True,
                "host_identified": True,
                "external_participant_verification": True,
                "calendar_match_score": True,
                "meeting_type_consistency": True
            }
        }
        
        if config_path and config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    import yaml
                    user_config = yaml.safe_load(f)
                    default_config.update(user_config)
            except Exception:
                pass  # Use defaults on error
        
        return default_config
    
    def _init_checks(self) -> List[QualityCheck]:
        """Initialize quality checks."""
        all_checks = [
            TranscriptLengthCheck(),
            TranscriptFormatCheck(),
            DurationConsistencyCheck(),
            ParticipantConfidenceCheck(),
            HostIdentifiedCheck(),
            ExternalParticipantVerificationCheck(),
            CalendarMatchScoreCheck(),
            MeetingTypeConsistencyCheck(),
        ]
        
        # Filter enabled checks
        enabled = self.config.get("checks_enabled", {})
        return [check for check in all_checks if enabled.get(check.name, True)]
    
    def execute(self, manifest_path: Path, transcript_path: Optional[Path] = None) -> Dict:
        """Execute all quality checks."""
        
        # Load manifest
        try:
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
        except Exception as e:
            return {
                "passed": False,
                "score": 0.0,
                "error": f"Failed to load manifest: {str(e)}",
                "checks": []
            }
        
        # Ensure transcript_path is a Path object
        if transcript_path is not None and not isinstance(transcript_path, Path):
            transcript_path = Path(transcript_path)

        # Run checks
        check_results = []
        total_score = 0.0
        critical_failures = 0
        hitl_escalations = []
        
        for check in self.checks:
            try:
                check.execute(manifest, transcript_path)
                check_results.append(check.to_dict())
                total_score += check.score
                
                if not check.passed:
                    critical_failures += 1
                
                if check.escalate_hitl:
                    hitl_escalations.append({
                        "check": check.name,
                        "reason": check.errors[0] if check.errors else "Quality check failed",
                        "context": {
                            "check_name": check.name,
                            "score": check.score,
                            "errors": check.errors,
                            "warnings": check.warnings
                        }
                    })
                
            except Exception as e:
                check_results.append({
                    "name": check.name,
                    "error": str(e),
                    "passed": False,
                    "score": 0.0
                })
                critical_failures += 1
        
        # Calculate overall score
        if len(self.checks) > 0:
            self.overall_score = total_score / len(self.checks)
        else:
            self.overall_score = 0.0
        
        # Determine pass/fail
        threshold = self.config.get("overall_threshold", 0.8)
        self.passed = (self.overall_score >= threshold and 
                      critical_failures == 0 and
                      len(hitl_escalations) == 0)
        
        # Update manifest quality gate
        quality_gate = {
            "passed": self.passed,
            "checks": {
                "has_transcript": transcript_path is not None and transcript_path.exists(),
                "participants_identified": manifest.get('participants', {}).get('confidence', 0) >= 0.5,
                "meeting_type_determined": bool(manifest.get('meeting', {}).get('type')),
                "no_hitl_pending": len(hitl_escalations) == 0
            },
            "score": self.overall_score,
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "check_results": check_results
        }
        
        # Save updated manifest
        manifest["quality_gate"] = quality_gate
        if self.passed:
            # Update status to gated
            manifest["status"] = "gated"
            manifest["timestamps"]["gated_at"] = datetime.now(timezone.utc).isoformat()
            
            # Add to status history
            if "status_history" not in manifest:
                manifest["status_history"] = []
            manifest["status_history"].append({
                "status": "gated",
                "at": datetime.now(timezone.utc).isoformat()
            })
        
        try:
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
        except Exception as e:
            quality_gate["manifest_update_error"] = str(e)
        
        # Handle HITL escalations
        if self.config.get("hitl_escalation", True) and hitl_escalations:
            meeting_id = manifest.get("meeting_id", "unknown")
            
            for escalation in hitl_escalations:
                try:
                    hitl_id = add_hitl_item(
                        meeting_id=meeting_id,
                        reason="quality_check_failure",
                        context=escalation["context"]
                    )
                    escalation["hitl_id"] = hitl_id
                except Exception as e:
                    escalation["hitl_error"] = str(e)
        
        return {
            "passed": self.passed,
            "score": self.overall_score,
            "threshold": threshold,
            "checks": check_results,
            "hitl_escalations": hitl_escalations,
            "critical_failures": critical_failures,
            "manifest_updated": True
        }


def main():
    parser = argparse.ArgumentParser(description="Meeting Quality Gate")
    parser.add_argument("manifest_path", help="Path to meeting manifest JSON file")
    parser.add_argument("--transcript", help="Path to transcript file")
    parser.add_argument("--config", help="Path to quality gate config YAML")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    
    args = parser.parse_args()
    
    # Initialize quality gate
    config_path = Path(args.config) if args.config else None
    gate = QualityGate(config_path)
    
    # Execute checks
    manifest_path = Path(args.manifest_path)
    transcript_path = Path(args.transcript) if args.transcript else None
    
    results = gate.execute(manifest_path, transcript_path)
    
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        # Human-readable output
        print(f"Quality Gate: {'✓ PASSED' if results['passed'] else '✗ FAILED'}")
        print(f"Overall Score: {results['score']:.3f} (threshold: {results['threshold']:.3f})")
        
        if args.verbose or not results['passed']:
            print(f"\nCheck Results ({len(results['checks'])} checks):")
            for check in results['checks']:
                status = "✓" if check.get('passed', False) else "✗"
                score = check.get('score', 0)
                print(f"  {status} {check['name']}: {score:.3f}")
                
                if args.verbose or not check.get('passed', False):
                    for warning in check.get('warnings', []):
                        print(f"    ⚠ {warning}")
                    for error in check.get('errors', []):
                        print(f"    ✗ {error}")
        
        if results.get('hitl_escalations'):
            print(f"\nHITL Escalations ({len(results['hitl_escalations'])}):")
            for escalation in results['hitl_escalations']:
                print(f"  • {escalation['check']}: {escalation['reason']}")
                if 'hitl_id' in escalation:
                    print(f"    HITL ID: {escalation['hitl_id']}")
    
    # Exit with appropriate code
    sys.exit(0 if results['passed'] else 1)


if __name__ == "__main__":
    main()