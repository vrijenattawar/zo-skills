#!/usr/bin/env python3
"""
Mentor Handler - VA-side escalation request processor

Handles escalation requests from <YOUR_INSTANCE> instances and provides 
mentor guidance based on precedent and context analysis.
"""

import json
import argparse
import uuid
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pathlib import Path
import difflib

# Add workspace to path for imports
sys.path.insert(0, '/home/workspace')

WORKSPACE_ROOT = Path('/home/workspace')
PRECEDENT_FILE = WORKSPACE_ROOT / 'N5/data/mentor_precedents.json'
AUDIT_LOG = WORKSPACE_ROOT / 'N5/data/mentor_audit.jsonl'

def load_precedents() -> Dict[str, Any]:
    """Load existing precedents from storage."""
    if not PRECEDENT_FILE.exists():
        PRECEDENT_FILE.parent.mkdir(parents=True, exist_ok=True)
        initial_data = {"precedents": []}
        save_precedents(initial_data)
        return initial_data
    
    try:
        with open(PRECEDENT_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {"precedents": []}

def save_precedents(data: Dict[str, Any]) -> None:
    """Save precedents to storage."""
    with open(PRECEDENT_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def validate_request(request: Dict[str, Any]) -> bool:
    """Validate the escalation request format."""
    required_fields = [
        'type', 'from', 'confidence', 'situation', 
        'context', 'question', 'correlation_id', 'timestamp'
    ]
    
    if not all(field in request for field in required_fields):
        return False
    
    if request['type'] != 'mentor_escalation':
        return False
    
    if not isinstance(request['confidence'], (int, float)):
        return False
        
    if not 0.0 <= request['confidence'] <= 1.0:
        return False
    
    return True

def fuzzy_match_situation(situation: str, precedents: List[Dict]) -> Optional[Dict]:
    """Find the best matching precedent for a situation."""
    if not precedents:
        return None
    
    best_match = None
    best_score = 0.0
    
    for precedent in precedents:
        if not precedent.get('reusable', True):
            continue
            
        pattern = precedent.get('situation_pattern', '')
        # Use sequence matching for fuzzy comparison
        score = difflib.SequenceMatcher(None, situation.lower(), pattern.lower()).ratio()
        
        if score > best_score and score > 0.6:  # 60% similarity threshold
            best_match = precedent
            best_score = score
    
    return best_match

def assess_mentor_confidence(request: Dict[str, Any], precedent: Optional[Dict]) -> float:
    """Assess VA's confidence in providing guidance."""
    base_confidence = 0.5
    
    # Boost confidence if we have strong precedent
    if precedent:
        precedent_confidence = precedent.get('confidence_used', 0.5)
        outcome = precedent.get('outcome', 'unknown')
        if outcome == 'successful':
            base_confidence += 0.2
        base_confidence += (precedent_confidence - 0.5) * 0.3
    
    # Adjust based on context factors
    context = request.get('context', {})
    
    # Well-defined change types boost confidence
    change_type = context.get('change_type', '')
    if change_type in ['security_gate_change', 'audit_protocol_change', 'privacy_policy_change']:
        base_confidence += 0.1
    
    # Risk level adjustment
    risk_level = context.get('risk_level', 'medium')
    if risk_level == 'low':
        base_confidence += 0.1
    elif risk_level == 'high':
        base_confidence -= 0.1
    
    # Client tier consideration
    client_tier = context.get('client_tier', 'unknown')
    if client_tier in ['enterprise', 'premium']:
        base_confidence += 0.05  # Slightly more confident with known tiers
    
    return max(0.0, min(1.0, base_confidence))

def generate_guidance(request: Dict[str, Any], precedent: Optional[Dict]) -> Dict[str, Any]:
    """Generate mentor guidance based on request and precedent."""
    situation = request.get('situation', '')
    context = request.get('context', {})
    question = request.get('question', '')
    
    # Assess our confidence
    mentor_confidence = assess_mentor_confidence(request, precedent)
    
    # Check if we should escalate to human
    if mentor_confidence < 0.5:
        return {
            "type": "mentor_response",
            "recommendation": None,
            "confidence": mentor_confidence,
            "rationale": "Both <YOUR_INSTANCE> and va uncertain about this decision",
            "needs_human": True,
            "human_escalation_reason": "Insufficient confidence from both systems",
            "packaged_context": {
                "original_request": request,
                "precedent_searched": precedent is not None,
                "confidence_breakdown": {
                    "<YOUR_INSTANCE>_confidence": request.get('confidence', 0.0),
                    "va_confidence": mentor_confidence
                }
            },
            "correlation_id": request.get('correlation_id')
        }
    
    # Generate actual guidance
    recommendation = "review_required"  # Safe default
    rationale = ""
    learning_guidance = ""
    sets_new_precedent = precedent is None
    
    # Context-based decision logic
    change_type = context.get('change_type', '')
    risk_level = context.get('risk_level', 'medium')
    client_tier = context.get('client_tier', 'unknown')
    
    if precedent:
        # Base guidance on precedent
        precedent_guidance = precedent.get('guidance_given', '')
        recommendation = precedent_guidance
        rationale = f"Based on precedent {precedent['id']}: {precedent_guidance}"
        learning_guidance = f"This follows established pattern: {precedent['situation_pattern']}"
    else:
        # Generate new guidance
        if 'security' in situation.lower() or change_type == 'security_gate_change':
            recommendation = "deny"
            rationale = "Security-related changes require careful review. Default to deny unless exceptional business justification provided."
            learning_guidance = "Always err on side of caution with security changes. Require explicit approval path."
        
        elif 'remove' in question.lower() and 'gate' in question.lower():
            recommendation = "require_justification" 
            rationale = "Removing protective gates needs strong business case. Ask client to document justification."
            learning_guidance = "Gates exist for protection. Removal should be exceptional and well-documented."
        
        elif risk_level == 'high':
            recommendation = "escalate_to_human"
            rationale = "High-risk changes need human review regardless of confidence levels."
            learning_guidance = "High-risk decisions should always involve human judgment, even with high confidence."
        
        elif client_tier == 'enterprise' and risk_level == 'low':
            recommendation = "approve_with_monitoring"
            rationale = "Enterprise clients with low-risk changes can proceed with enhanced monitoring."
            learning_guidance = "Enterprise tier gets more autonomy for low-risk changes, but maintain audit trail."
    
    return {
        "type": "mentor_response",
        "recommendation": recommendation,
        "confidence": mentor_confidence,
        "rationale": rationale,
        "precedent_id": precedent.get('id') if precedent else None,
        "sets_new_precedent": sets_new_precedent,
        "needs_human": False,
        "correlation_id": request.get('correlation_id'),
        "learning_guidance": learning_guidance
    }

def log_precedent(request: Dict[str, Any], response: Dict[str, Any]) -> None:
    """Store this interaction as a precedent for future reference."""
    if response.get('needs_human', False):
        return  # Don't store precedents for human escalations
    
    precedents_data = load_precedents()
    
    # Generate new precedent
    new_precedent = {
        "id": f"prec_{len(precedents_data['precedents']) + 1:03d}",
        "created": datetime.now(timezone.utc).isoformat(),
        "situation_pattern": request.get('situation', ''),
        "guidance_given": response.get('recommendation', ''),
        "outcome": "pending",  # Will be updated when we learn outcome
        "reusable": True,
        "context_factors": list(request.get('context', {}).keys()),
        "confidence_used": response.get('confidence', 0.5),
        "original_request": {
            "situation": request.get('situation', ''),
            "context": request.get('context', {}),
            "question": request.get('question', ''),
            "<YOUR_INSTANCE>_confidence": request.get('confidence', 0.0)
        }
    }
    
    precedents_data['precedents'].append(new_precedent)
    save_precedents(precedents_data)
    
    # Also log to audit trail
    log_audit_event(request, response, new_precedent['id'])

def log_audit_event(request: Dict[str, Any], response: Dict[str, Any], precedent_id: Optional[str] = None) -> None:
    """Log the escalation interaction to audit trail."""
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    
    audit_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": "mentor_escalation_handled",
        "correlation_id": request.get('correlation_id'),
        "from_instance": request.get('from', 'unknown'),
        "va_confidence": response.get('confidence', 0.0),
        "<YOUR_INSTANCE>_confidence": request.get('confidence', 0.0),
        "recommendation": response.get('recommendation'),
        "needs_human": response.get('needs_human', False),
        "precedent_id": precedent_id,
        "sets_new_precedent": response.get('sets_new_precedent', False)
    }
    
    with open(AUDIT_LOG, 'a') as f:
        f.write(json.dumps(audit_entry) + '\n')

def handle_escalation(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main escalation handler function.
    
    Process flow:
    1. Validate request format
    2. Check for relevant precedent  
    3. Assess our confidence
    4. Generate guidance or escalate to human
    5. Log the interaction
    6. Return response
    """
    
    # 1. Validate request
    if not validate_request(request):
        return {
            "type": "mentor_response",
            "error": "Invalid request format",
            "correlation_id": request.get('correlation_id', 'unknown')
        }
    
    # 2. Check precedent
    precedents_data = load_precedents()
    situation = request.get('situation', '')
    precedent = fuzzy_match_situation(situation, precedents_data['precedents'])
    
    # 3. Generate guidance
    response = generate_guidance(request, precedent)
    
    # 4. Log interaction (if not error response)
    if 'error' not in response:
        log_precedent(request, response)
    
    return response

def list_precedents() -> None:
    """List all stored precedents."""
    precedents_data = load_precedents()
    precedents = precedents_data.get('precedents', [])
    
    if not precedents:
        print("No precedents stored yet.")
        return
    
    print(f"Found {len(precedents)} precedents:")
    print()
    
    for prec in precedents:
        print(f"ID: {prec['id']}")
        print(f"Pattern: {prec['situation_pattern']}")
        print(f"Guidance: {prec['guidance_given']}")
        print(f"Confidence: {prec['confidence_used']}")
        print(f"Reusable: {prec['reusable']}")
        print(f"Created: {prec['created']}")
        print("-" * 50)

def run_test() -> None:
    """Run test with sample escalation request."""
    test_request = {
        "type": "mentor_escalation",
        "from": "<YOUR_INSTANCE>-test",
        "confidence": 0.4,
        "situation": "Client requests removing security review gate for faster deployments",
        "context": {
            "client_tier": "enterprise", 
            "change_type": "security_gate_change",
            "risk_level": "medium"
        },
        "question": "Should we allow disabling the security review gate for this enterprise client?",
        "correlation_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    print("Running test with sample escalation request:")
    print(json.dumps(test_request, indent=2))
    print()
    
    response = handle_escalation(test_request)
    
    print("Generated response:")
    print(json.dumps(response, indent=2))

def main():
    parser = argparse.ArgumentParser(description='Handle mentor escalation requests from <YOUR_INSTANCE>')
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--request', type=str, help='JSON escalation request to process')
    group.add_argument('--test', action='store_true', help='Run test with sample data')
    group.add_argument('--list-precedents', action='store_true', help='List all stored precedents')
    
    args = parser.parse_args()
    
    if args.list_precedents:
        list_precedents()
    elif args.test:
        run_test()
    elif args.request:
        try:
            request_data = json.loads(args.request)
            response = handle_escalation(request_data)
            print(json.dumps(response, indent=2))
        except json.JSONDecodeError as e:
            print(f"Error parsing request JSON: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error processing request: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == '__main__':
    main()