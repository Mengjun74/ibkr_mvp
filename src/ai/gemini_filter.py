import os
import json
import datetime
from google import genai
from typing import Dict, Any, Optional

from ..config import GEMINI_API_KEY
from ..utils import logger

class GeminiFilter:
    def __init__(self):
        self.api_key = GEMINI_API_KEY
        self.enabled = bool(self.api_key)
        self.last_call_time = None
        self.client = None
        self.model_name = "gemini-1.5-flash"
        
        if self.enabled:
            # New SDK initialization
            self.client = genai.Client(api_key=self.api_key)

    def analyze_signal(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        context: {
            'time': str,
            'signal': 'BUY'/'SELL',
            'market_data': { ... recent bars stats ... },
            'risk_state': { ... },
            'pnl': float
        }
        """
        default_response = {
            "decision": "ALLOW", 
            "rationale": "AI Disabled or Failed", 
            "confidence": 0.0,
            "raw_json": ""
        }

        if not self.enabled:
            return default_response

        # Rate warning / check
        if self.last_call_time:
            elapsed = (datetime.datetime.now() - self.last_call_time).total_seconds()
            if elapsed < 300: # 5 min
                logger.info("Skipping AI call (cooldown)")
                return {**default_response, "rationale": "AI Cooldown"}

        try:
            self.last_call_time = datetime.datetime.now()
            
            prompt = self._construct_prompt(context)
            
            # New SDK call
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={
                    'temperature': 0.2,
                    'max_output_tokens': 500,
                    'response_mime_type': 'application/json'
                }
            )
            
            # Response handling might differ slightly, usually response.text
            result_text = response.text
            result_json = json.loads(result_text)
            result_json['raw_json'] = result_text
            
            # validate fields
            if result_json.get('decision') not in ['ALLOW', 'DENY', 'REDUCE_RISK']:
                result_json['decision'] = 'ALLOW'
                
            return result_json

        except Exception as e:
            logger.error(f"AI Call Failed: {e}")
            return default_response

    def _construct_prompt(self, context: Dict[str, Any]) -> str:
        return f"""
        You are a cautious Risk Manager for a Futures Trading Bot (MES).
        
        Current State:
        Time: {context.get('time')}
        Signal: {context.get('signal')}
        PnL: {context.get('pnl')}
        
        Recent Market Data (Stats):
        {json.dumps(context.get('market_data'), indent=2)}
        
        Risk State:
        {json.dumps(context.get('risk_state'), indent=2)}
        
        Task:
        Analyze the proposed signal. Look for reasons to DENY it (high volatility, fighting strong trend, recent losses).
        If the signal looks standard and safe, ALLOW it.
        
        Output JSON Schema:
        {{
            "decision": "ALLOW" | "DENY" | "REDUCE_RISK",
            "rationale": "string explanation max 20 words",
            "confidence": 0.0 to 1.0
        }}
        """
