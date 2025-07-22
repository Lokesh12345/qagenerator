"""
Clean AI Client supporting OpenAI and Claude for Q&A processing
"""
import os
import json
import logging
from typing import Dict, Optional, Any
import requests
from datetime import datetime
from dotenv import load_dotenv
from .cache_manager import get_cache

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

class AIClient:
    def __init__(self, provider: str = "openai", model: str = None):
        self.provider = provider.lower()
        self.model = model or self._get_default_model()
        
        # Only support OpenAI and Claude
        if self.provider not in ['openai', 'claude']:
            raise ValueError(f"Unsupported provider: {self.provider}. Only 'openai' and 'claude' are supported.")
        
        # Load API keys from environment
        self.openai_key = os.getenv('OPENAI_API_KEY')
        self.claude_key = os.getenv('ANTHROPIC_API_KEY')
        
        # Load prompt template
        self.prompt_template = self._load_prompt_template()
        
        # Initialize cache
        self.cache = get_cache()
        
        if self.provider == "openai" and not self.openai_key:
            raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")
        elif self.provider == "claude" and not self.claude_key:
            raise ValueError("Claude API key not found. Set ANTHROPIC_API_KEY environment variable.")
    
    def _get_default_model(self):
        """Get default model for each provider"""
        defaults = {
            "openai": "gpt-4o-mini",
            "claude": "claude-3-5-haiku-20241022"
        }
        return defaults.get(self.provider, "gpt-4o-mini")
    
    def _load_prompt_template(self):
        """Load the prompt template from file"""
        try:
            with open('ollama/prompt_template.txt', 'r') as f:
                return f.read().strip()
        except Exception as e:
            logger.error(f"Error loading prompt template: {e}")
            return self._get_fallback_prompt()
    
    def _get_fallback_prompt(self):
        """Fallback prompt if file not found"""
        return """You are an expert data-structuring bot for interview preparation.

Convert the given Q&A into a comprehensive JSON structure for technical interviews.

REQUIRED JSON FIELDS:
- primaryQuestion
- alternativeQuestions (20 variations)
- answerDescriptions (5 key points)
- answer (summary, detailed, whenToUse, realWorldContext)
- category, subcategory, difficulty
- tags (10 items), conceptTriggers (5 items), naturalFollowups (10 items)
- relatedQuestions (10 items)
- commonMistakes (3 objects with mistake/explanation)
- confidence, lastUpdated, verified

For programming questions, include code examples and technical details.
Return only valid JSON, no commentary."""
    
    def format_question_to_json(self, question: str, qa_id: str = None) -> Optional[Dict[str, Any]]:
        """Convert question to structured JSON, generating answer automatically"""
        
        try:
            logger.info(f"Processing question with {self.provider}/{self.model}: {question[:50]}...")
            
            # Check cache first
            cached_result = self.cache.get_cached_response(question, self.provider, self.model)
            if cached_result:
                return cached_result
            
            # Create prompt for question-only processing
            full_prompt = f"""{self.prompt_template}

Question: {question}

Generate a comprehensive answer and convert into the required JSON format. Create a detailed, interview-ready response."""

            # Call the appropriate AI service
            if self.provider == "openai":
                result = self._call_openai(full_prompt, qa_id)
            elif self.provider == "claude":
                result = self._call_claude(full_prompt, qa_id)
            else:
                logger.error(f"Unsupported provider: {self.provider}")
                return None
            
            if result:
                # Cache the successful result
                self.cache.store_response(question, self.provider, self.model, result)
                logger.info(f"✅ Successfully processed with {self.provider}: {question[:50]}...")
                return result
            else:
                logger.warning(f"AI processing failed")
                return None
                
        except Exception as e:
            logger.error(f"Error in AI processing: {e}")
            return None

    def format_qa_to_json(self, question: str, answer: str, qa_id: str = None) -> Optional[Dict[str, Any]]:
        """Convert Q&A to structured JSON using AI"""
        
        try:
            logger.info(f"Processing with {self.provider}/{self.model}: {question[:50]}...")
            
            # Check cache first (use question as cache key since it's the primary identifier)
            cached_result = self.cache.get_cached_response(question, self.provider, self.model)
            if cached_result:
                return cached_result
            
            # Create the full prompt
            full_prompt = f"""{self.prompt_template}

Question: {question}
Answer: {answer}
ID: {qa_id or self._generate_id(question)}

Convert this into the required JSON format."""

            # Call the appropriate AI service
            if self.provider == "openai":
                result = self._call_openai(full_prompt, qa_id)
            elif self.provider == "claude":
                result = self._call_claude(full_prompt, qa_id)
            else:
                logger.error(f"Unsupported provider: {self.provider}")
                return None
            
            if result:
                # Cache the successful result
                self.cache.store_response(question, self.provider, self.model, result)
                logger.info(f"✅ Successfully processed with {self.provider}: {question[:50]}...")
                return result
            else:
                logger.warning(f"AI processing failed")
                return None
                
        except Exception as e:
            logger.error(f"Error in AI processing: {e}")
            return None
    
    def _call_openai(self, prompt: str, qa_id: str = None) -> Optional[Dict[str, Any]]:
        """Call OpenAI API"""
        if not self.openai_key:
            logger.error("OpenAI API key not available")
            return None
        
        try:
            headers = {
                'Authorization': f'Bearer {self.openai_key}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'model': self.model,
                'messages': [
                    {
                        'role': 'system',
                        'content': 'You are an expert at creating structured interview preparation data. Return only valid JSON.'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'temperature': 0.3,
                'max_tokens': 4000
            }
            
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers=headers,
                json=data,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                return self._parse_json_response(content)
            else:
                logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"OpenAI call failed: {e}")
            return None
    
    def _call_claude(self, prompt: str, qa_id: str = None) -> Optional[Dict[str, Any]]:
        """Call Claude API"""
        if not self.claude_key:
            logger.error("Claude API key not available")
            return None
        
        try:
            headers = {
                'x-api-key': self.claude_key,
                'Content-Type': 'application/json',
                'anthropic-version': '2023-06-01'
            }
            
            data = {
                'model': self.model,
                'max_tokens': 4000,
                'temperature': 0.3,
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ]
            }
            
            response = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers=headers,
                json=data,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['content'][0]['text']
                return self._parse_json_response(content)
            else:
                logger.error(f"Claude API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Claude call failed: {e}")
            return None
    
    def _parse_json_response(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse JSON response from AI"""
        try:
            # Remove markdown code blocks if present
            content = content.strip()
            if content.startswith('```json'):
                content = content[7:]
            if content.startswith('```'):
                content = content[3:]
            if content.endswith('```'):
                content = content[:-3]
            
            # Find the JSON part
            start = content.find('{')
            end = content.rfind('}') + 1
            
            if start != -1 and end > start:
                json_str = content[start:end]
                return json.loads(json_str)
            else:
                logger.error("No valid JSON found in response")
                return None
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            logger.debug(f"Raw content: {content[:500]}...")
            return None
        except Exception as e:
            logger.error(f"Response parsing error: {e}")
            return None
    
    def _generate_id(self, question: str) -> str:
        """Generate ID from question"""
        return question[:30].lower().replace(' ', '-').replace('?', '').replace(',', '').replace('.', '')
    
    def test_connection(self) -> bool:
        """Test if the AI service is available"""
        try:
            if self.provider == "openai":
                return bool(self.openai_key)
            elif self.provider == "claude":
                return bool(self.claude_key)
            return False
        except Exception:
            return False
    
    def get_available_models(self) -> list:
        """Get list of available models for the provider"""
        if self.provider == "openai":
            return [
                "gpt-4o",
                "gpt-4o-mini", 
                "gpt-4-turbo",
                "gpt-3.5-turbo"
            ]
        elif self.provider == "claude":
            return [
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307"
            ]
        return []
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return self.cache.get_stats()