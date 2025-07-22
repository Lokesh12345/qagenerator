import requests
import json
import subprocess
import time
from typing import Dict, Any, List, Optional

class OllamaClient:
    def __init__(self, model: str = "qwen:7b"):
        self.base_url = "http://localhost:11434"
        self.model = model
        
    def test_connection(self) -> Dict[str, Any]:
        """Test if Ollama is running and accessible"""
        try:
            response = requests.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                models = response.json().get('models', [])
                return {
                    "status": "connected",
                    "message": f"Ollama is running with {len(models)} models available",
                    "models": [m['name'] for m in models]
                }
            else:
                return {
                    "status": "error",
                    "message": f"Ollama returned status code: {response.status_code}"
                }
        except requests.exceptions.ConnectionError:
            return {
                "status": "error",
                "message": "Cannot connect to Ollama. Please ensure Ollama is running (ollama serve)"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}"
            }
    
    def list_models(self) -> List[Dict[str, Any]]:
        """List all available Ollama models"""
        try:
            response = requests.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                models = response.json().get('models', [])
                return [
                    {
                        "name": model['name'],
                        "size": model.get('size', 0),
                        "modified": model.get('modified_at', ''),
                        "id": model.get('digest', '')[:12]
                    }
                    for model in models
                ]
            return []
        except:
            return []
    
    def process_question_streaming(self, question: str, answer: str, prompt_template: str, emit_callback=None) -> Dict[str, Any]:
        """Process a single Q&A pair using Ollama with streaming support"""
        # Use the multi-step approach for streaming too
        return self.process_question_multi_step(question, answer, emit_callback)
    
    def process_question_multi_step(self, question: str, answer: str, emit_callback=None) -> Dict[str, Any]:
        """Process Q&A using multiple simple steps instead of one complex prompt"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            logger.info(f"Starting multi-step Ollama processing for: {question[:50]}...")
            
            # Step 1: Generate basic structure
            basic_prompt = f"""Create a simple JSON response for this Q&A:

Question: {question}
Answer: {answer}

Return ONLY this JSON format:
{{
  "primaryQuestion": "{question}",
  "category": "appropriate category like HTML/CSS/JavaScript etc",
  "subcategory": "specific subcategory",
  "difficulty": "beginner/intermediate/advanced",
  "answer": {{
    "summary": "Brief 1-2 sentence summary",
    "detailed": "Detailed explanation with examples",
    "whenToUse": "When to use this concept",
    "realWorldContext": "Real world application"
  }}
}}"""

            basic_result = self._simple_ollama_call(basic_prompt, timeout=60)
            if not basic_result["success"]:
                logger.error(f"Step 1 failed: {basic_result.get('error', 'Unknown error')}")
                return basic_result
            
            basic_data = basic_result["data"]
            logger.info("✅ Step 1 (basic structure) completed")
            
            # Step 2: Generate alternative questions
            alt_prompt = f"""For the question "{question}", generate EXACTLY 15 alternative phrasings.

Return ONLY a JSON array of strings:
["alternative 1", "alternative 2", "alternative 3", ...]

Make each alternative unique and interview-focused."""

            alt_result = self._simple_ollama_call(alt_prompt)
            if alt_result["success"] and isinstance(alt_result["data"], list):
                basic_data["alternativeQuestions"] = alt_result["data"]
                logger.info(f"✅ Step 2 completed: {len(alt_result['data'])} alternatives")
            else:
                basic_data["alternativeQuestions"] = [question, f"What is {question.lower()}?", f"How does {question.lower()} work?"]
                logger.warning("Step 2 failed, using fallback alternatives")
            
            # Step 3: Generate answer descriptions
            desc_prompt = f"""For this topic: {question}

Generate EXACTLY 5 short bullet point descriptions.

Return ONLY a JSON array of strings:
["description 1", "description 2", "description 3", "description 4", "description 5"]

Each should be a concise explanation point."""

            desc_result = self._simple_ollama_call(desc_prompt)
            if desc_result["success"] and isinstance(desc_result["data"], list):
                basic_data["answerDescriptions"] = desc_result["data"]
                logger.info(f"✅ Step 3 completed: {len(desc_result['data'])} descriptions")
            else:
                basic_data["answerDescriptions"] = ["Key concept explanation", "Important for understanding", "Used in web development", "Essential knowledge", "Interview topic"]
                logger.warning("Step 3 failed, using fallback descriptions")
            
            # Step 4: Generate tags
            tags_prompt = f"""For this technical topic: {question}

Generate EXACTLY 10 relevant tags/keywords.

Return ONLY a JSON array of strings:
["tag1", "tag2", "tag3", ...]

Focus on technical keywords, concepts, and related terms."""

            tags_result = self._simple_ollama_call(tags_prompt)
            if tags_result["success"] and isinstance(tags_result["data"], list):
                basic_data["tags"] = tags_result["data"]
                logger.info(f"✅ Step 4 completed: {len(tags_result['data'])} tags")
            else:
                basic_data["tags"] = ["html", "web", "development", "frontend", "css", "javascript", "technical", "interview", "programming", "markup"]
                logger.warning("Step 4 failed, using fallback tags")
            
            # Step 5: Generate follow-up questions
            followup_prompt = f"""For the topic: {question}

Generate EXACTLY 12 natural follow-up questions someone might ask.

Return ONLY a JSON array of strings:
["followup 1", "followup 2", ...]

Make them interview-style follow-up questions."""

            followup_result = self._simple_ollama_call(followup_prompt)
            if followup_result["success"] and isinstance(followup_result["data"], list):
                basic_data["naturalFollowups"] = followup_result["data"]
                logger.info(f"✅ Step 5 completed: {len(followup_result['data'])} follow-ups")
            else:
                basic_data["naturalFollowups"] = ["Can you explain more about this?", "How is this used in practice?", "What are the benefits?", "Are there any drawbacks?", "How does this compare to alternatives?", "When should you use this?"]
                logger.warning("Step 5 failed, using fallback follow-ups")
            
            # Step 6: Generate related questions  
            related_prompt = f"""For the topic: {question}

Generate EXACTLY 12 related technical questions.

Return ONLY a JSON array of strings:
["related 1", "related 2", ...]

Focus on similar technical concepts and interview questions."""

            related_result = self._simple_ollama_call(related_prompt)
            if related_result["success"] and isinstance(related_result["data"], list):
                basic_data["relatedQuestions"] = related_result["data"]
                logger.info(f"✅ Step 6 completed: {len(related_result['data'])} related questions")
            else:
                basic_data["relatedQuestions"] = ["What are related concepts?", "How does this work with other technologies?", "What are best practices?", "How to implement this?", "What are common patterns?", "How to optimize this?"]
                logger.warning("Step 6 failed, using fallback related questions")
            
            # Step 7: Generate common mistakes
            mistakes_prompt = f"""For the topic: {question}

Generate EXACTLY 4 common mistakes with explanations.

Return ONLY this JSON format:
[
  {{"mistake": "mistake description", "explanation": "why it's wrong"}},
  {{"mistake": "mistake description", "explanation": "why it's wrong"}},
  {{"mistake": "mistake description", "explanation": "why it's wrong"}},
  {{"mistake": "mistake description", "explanation": "why it's wrong"}}
]"""

            mistakes_result = self._simple_ollama_call(mistakes_prompt)
            if mistakes_result["success"] and isinstance(mistakes_result["data"], list):
                basic_data["commonMistakes"] = mistakes_result["data"]
                logger.info(f"✅ Step 7 completed: {len(mistakes_result['data'])} mistakes")
            else:
                basic_data["commonMistakes"] = [
                    {"mistake": "Common error", "explanation": "Standard explanation"},
                    {"mistake": "Syntax mistake", "explanation": "Check syntax carefully"},
                    {"mistake": "Logic error", "explanation": "Review the logic"},
                    {"mistake": "Performance issue", "explanation": "Consider optimization"}
                ]
                logger.warning("Step 7 failed, using fallback mistakes")
            
            # Add final fields
            basic_data["conceptTriggers"] = basic_data.get("tags", [])[:5]  # Use first 5 tags
            basic_data["confidence"] = "high"
            basic_data["lastUpdated"] = "2025-07-22"
            basic_data["verified"] = False
            
            # Create final structure with question ID
            question_id = f"question-{question[:30].lower().replace(' ', '-').replace('?', '').replace(',', '').replace('.', '').replace('(', '').replace(')', '')}"
            
            # Emit final completion for streaming
            if emit_callback:
                emit_callback({
                    'provider': 'ollama',
                    'question': question,
                    'partial_response': json.dumps({question_id: basic_data}, indent=2),
                    'is_complete': True
                })
            
            logger.info("✅ Multi-step processing completed successfully!")
            return {
                "success": True,
                "data": {question_id: basic_data},
                "raw_response": "Multi-step processing completed"
            }
            
        except Exception as e:
            logger.error(f"Multi-step processing failed: {e}")
            return {
                "success": False,
                "error": f"Multi-step processing error: {str(e)}",
                "raw_response": ""
            }
    
    def _simple_ollama_call(self, prompt: str, timeout: int = 30) -> Dict[str, Any]:
        """Make a simple, fast Ollama call for specific tasks"""
        try:
            # Use higher token limits - no problem as per user
            token_limit = 4096 if "Return ONLY this JSON format:" in prompt else 2048
            
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.4,
                    "top_p": 0.9,
                    "num_predict": token_limit,
                    "repeat_penalty": 1.1
                }
            }
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                generated_text = result.get('response', '').strip()
                
                # Simple JSON extraction for focused responses
                if generated_text.startswith('[') or generated_text.startswith('{'):
                    # Direct JSON response
                    try:
                        parsed = json.loads(generated_text)
                        return {"success": True, "data": parsed}
                    except json.JSONDecodeError:
                        pass
                
                # Extract JSON from response more carefully
                import re
                
                # Method 1: Look for complete JSON object
                start_brace = generated_text.find('{')
                if start_brace != -1:
                    # Find the matching closing brace
                    brace_count = 0
                    end_pos = start_brace
                    for i, char in enumerate(generated_text[start_brace:], start_brace):
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_pos = i
                                break
                    
                    json_str = generated_text[start_brace:end_pos + 1]
                    try:
                        parsed = json.loads(json_str)
                        return {"success": True, "data": parsed}
                    except json.JSONDecodeError as e:
                        # Clean and try again
                        cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
                        cleaned = re.sub(r',(\s*[}\]])', r'\1', cleaned)  # Remove trailing commas
                        try:
                            parsed = json.loads(cleaned)
                            return {"success": True, "data": parsed}
                        except json.JSONDecodeError:
                            pass
                
                # Method 2: Look for JSON array
                start_bracket = generated_text.find('[')
                if start_bracket != -1:
                    end_bracket = generated_text.rfind(']')
                    if end_bracket > start_bracket:
                        json_str = generated_text[start_bracket:end_bracket + 1]
                        try:
                            parsed = json.loads(json_str)
                            return {"success": True, "data": parsed}
                        except json.JSONDecodeError:
                            pass
                
                # Last resort: try to complete incomplete JSON for basic structure
                if "primaryQuestion" in generated_text and "Return ONLY this JSON format:" in prompt:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning("Attempting to fix incomplete basic JSON structure")
                    # Find where the JSON cuts off and try to close it
                    incomplete_json = generated_text[start_brace:].strip() if start_brace != -1 else generated_text.strip()
                    # Add missing closing braces if needed
                    open_braces = incomplete_json.count('{') - incomplete_json.count('}')
                    if open_braces > 0:
                        incomplete_json += '}' * open_braces
                    
                    try:
                        parsed = json.loads(incomplete_json)
                        logger.info("✅ Successfully fixed incomplete JSON!")
                        return {"success": True, "data": parsed}
                    except json.JSONDecodeError:
                        pass
                
                # Failed to parse
                return {"success": False, "error": "Could not parse JSON", "raw": generated_text[:500]}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}

    def process_question(self, question: str, answer: str, prompt_template: str) -> Dict[str, Any]:
        """Process a single Q&A pair using Ollama - now uses multi-step approach"""
        # Use the new multi-step approach for better reliability
        return self.process_question_multi_step(question, answer)
    
    def get_available_models_from_cli(self) -> List[str]:
        """Get available models using ollama CLI as a fallback"""
        try:
            result = subprocess.run(['ollama', 'list'], capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                models = []
                for line in lines:
                    if line:
                        model_name = line.split()[0]
                        models.append(model_name)
                return models
            return []
        except:
            return []