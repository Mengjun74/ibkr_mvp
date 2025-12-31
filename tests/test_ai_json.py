import pytest
import json
from src.ai.gemini_filter import GeminiFilter

class MockResponse:
    def __init__(self, text):
        self.text = text

class MockModel:
    def __init__(self, output_text):
        self.output_text = output_text
        
    def generate_content(self, *args, **kwargs):
        return MockResponse(self.output_text)

def test_ai_valid_json():
    # Setup
    f = GeminiFilter()
    f.enabled = True
    f.model = MockModel('{"decision": "ALLOW", "rationale": "Looks good", "confidence": 0.9}')
    
    # Execute
    res = f.analyze_signal({'context': 'test'})
    
    # Verify
    assert res['decision'] == 'ALLOW'
    assert res['rationale'] == 'Looks good'

def test_ai_invalid_json():
    # Setup
    f = GeminiFilter()
    f.enabled = True
    f.model = MockModel('INVALID JSON')
    
    # Execute
    res = f.analyze_signal({'context': 'test'})
    
    # Verify (Default Fallback)
    assert res['decision'] == 'ALLOW'
    assert res['rationale'] == 'AI Disabled or Failed'
