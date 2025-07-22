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
            
            # Step 1: Generate basic structure following strict format
            basic_prompt = f"""You are a highly structured, rule-based data-generation assistant.

Generate the basic structure for this Q&A following STRICT formatting rules:

Question: {question}
Answer: {answer}

Return ONLY this JSON format with NO markdown, NO wrapping, NO commentary:
{{
  "primaryQuestion": "{question}",
  "category": "single word like HTML, CSS, JavaScript, Angular, etc",
  "subcategory": "specific subcategory like Layout, Forms, Events",
  "difficulty": "beginner",
  "answer": {{
    "summary": "1-2 sentence plain summary of the concept",
    "detailed": "Detailed explanation following programming format rules if applicable",
    "whenToUse": "1-2 lines on when this is practically applied", 
    "realWorldContext": "Short real-world use case or example scenario"
  }}
}}

CRITICAL: Use double quotes only, no nested objects except in answer section."""

            basic_result = self._simple_ollama_call(basic_prompt, timeout=60)
            if not basic_result["success"]:
                logger.error(f"Step 1 failed: {basic_result.get('error', 'Unknown error')}")
                return basic_result
            
            basic_data = basic_result["data"]
            logger.info("✅ Step 1 (basic structure) completed")
            
            # Step 2: Generate alternative questions following strict format
            alt_prompt = f"""You are a highly structured, rule-based data-generation assistant.

For the question "{question}", generate EXACTLY 15-20 alternative phrasings following STRICT rules.

REQUIRED: Return ONLY a JSON array of simple double-quoted strings - NO nested objects, NO markdown:
["alternative question 1", "alternative question 2", "alternative question 3", ...]

CORRECT FORMAT: Simple strings in array
WRONG FORMAT: Objects with "question" key

Make each alternative unique, interview-focused, and clearly different phrasing."""

            alt_result = self._simple_ollama_call(alt_prompt)
            if alt_result["success"] and isinstance(alt_result["data"], list):
                basic_data["alternativeQuestions"] = alt_result["data"]
                logger.info(f"✅ Step 2 completed: {len(alt_result['data'])} alternatives")
            else:
                basic_data["alternativeQuestions"] = [question, f"What is {question.lower()}?", f"How does {question.lower()} work?"]
                logger.warning("Step 2 failed, using fallback alternatives")
            
            # Step 3: Generate answer descriptions following strict format  
            desc_prompt = f"""You are a highly structured, rule-based data-generation assistant.

For this topic: {question}

Generate EXACTLY 5 clear, standalone one-line bullets following STRICT rules.

REQUIRED: Return ONLY a JSON array of simple double-quoted strings:
["bullet point 1", "bullet point 2", "bullet point 3", "bullet point 4", "bullet point 5"]

CORRECT: Clear standalone explanations, no numbered lists
WRONG: Numbered bullets, incomplete sentences, nested objects

Each bullet should be concise but complete explanation."""

            desc_result = self._simple_ollama_call(desc_prompt)
            if desc_result["success"] and isinstance(desc_result["data"], list):
                basic_data["answerDescriptions"] = desc_result["data"]
                logger.info(f"✅ Step 3 completed: {len(desc_result['data'])} descriptions")
            else:
                basic_data["answerDescriptions"] = ["Fundamental web development concept", "Essential for creating structured content", "Used in all modern web applications", "Required knowledge for frontend developers", "Common topic in technical interviews"]
                logger.warning("Step 3 failed, using fallback descriptions")
            
            # Step 4: Generate tags following strict format
            category = basic_data.get("category", "").lower()
            tags_prompt = f"""You are a highly structured, rule-based data-generation assistant.

For this technical topic: {question}
Category: {category}

Generate EXACTLY 8-12 highly relevant keywords following STRICT rules.

REQUIRED: Return ONLY a JSON array of simple double-quoted strings:
["tag1", "tag2", "tag3", ...]

CRITICAL RULE: If category is HTML-only, DO NOT include CSS terms like "styling", "layout", "design"
CORRECT: Focus on technical keywords directly related to the specific category
WRONG: Mixing CSS terms in HTML questions, generic terms

Focus on precise technical keywords and concepts."""

            tags_result = self._simple_ollama_call(tags_prompt)
            if tags_result["success"] and isinstance(tags_result["data"], list):
                basic_data["tags"] = tags_result["data"]
                logger.info(f"✅ Step 4 completed: {len(tags_result['data'])} tags")
            else:
                basic_data["tags"] = ["html", "web-development", "frontend", "markup", "elements", "attributes", "semantic", "structure", "technical-interview", "programming"]
                logger.warning("Step 4 failed, using fallback tags")
            
            # Step 5: Generate follow-up questions following strict format
            followup_prompt = f"""You are a highly structured, rule-based data-generation assistant.

For the topic: {question}

Generate EXACTLY 10-15 natural follow-up interview questions following STRICT rules.

REQUIRED: Return ONLY a JSON array of simple double-quoted strings:
["followup question 1", "followup question 2", ...]

CORRECT: Interview-style questions that naturally follow from the main topic
WRONG: Nested objects, generic questions, non-interview format

Make them specific, technical follow-up questions an interviewer would ask."""

            followup_result = self._simple_ollama_call(followup_prompt)
            if followup_result["success"] and isinstance(followup_result["data"], list):
                basic_data["naturalFollowups"] = followup_result["data"]
                logger.info(f"✅ Step 5 completed: {len(followup_result['data'])} follow-ups")
            else:
                basic_data["naturalFollowups"] = ["Can you provide a practical example of implementing this?", "How does this concept integrate with modern web frameworks?", "What are the performance implications of using this approach?", "How would you explain this to a junior developer?", "What are common pitfalls when working with this concept?", "How does this relate to accessibility standards?"]
                logger.warning("Step 5 failed, using fallback follow-ups")
            
            # Step 6: Generate related questions following strict format
            related_prompt = f"""You are a highly structured, rule-based data-generation assistant.

For the topic: {question}

Generate EXACTLY 10-15 related technical interview questions following STRICT rules.

REQUIRED: Return ONLY a JSON array of simple double-quoted strings:
["related question 1", "related question 2", ...]

CORRECT: Similar technical concepts, associated interview questions
WRONG: Nested objects, unrelated topics, non-technical questions

Focus on similar technical concepts and related interview topics."""

            related_result = self._simple_ollama_call(related_prompt)
            if related_result["success"] and isinstance(related_result["data"], list):
                basic_data["relatedQuestions"] = related_result["data"]
                logger.info(f"✅ Step 6 completed: {len(related_result['data'])} related questions")
            else:
                basic_data["relatedQuestions"] = ["How do semantic HTML elements improve accessibility?", "What is the difference between block and inline elements?", "How does HTML validation affect browser rendering?", "What are the best practices for HTML document structure?", "How do HTML attributes enhance element functionality?", "What is the role of DOCTYPE in HTML documents?"]
                logger.warning("Step 6 failed, using fallback related questions")
            
            # Step 7: Generate common mistakes following strict format
            mistakes_prompt = f"""You are a highly structured, rule-based data-generation assistant.

For the topic: {question}

Generate EXACTLY 3-5 common real-world mistakes with explanations following STRICT rules.

REQUIRED: Return ONLY this JSON format - NO markdown, NO wrapping:
[
  {{"mistake": "brief real-world mistake description", "explanation": "how to fix or avoid it"}},
  {{"mistake": "specific technical error", "explanation": "detailed solution"}},
  {{"mistake": "practical implementation mistake", "explanation": "best practice guidance"}}
]

CRITICAL: NO placeholder values like "Common error" or "Standard explanation"
CORRECT: Real, specific mistakes developers actually make

Focus on genuine, practical mistakes with actionable solutions."""

            mistakes_result = self._simple_ollama_call(mistakes_prompt)
            if mistakes_result["success"] and isinstance(mistakes_result["data"], list):
                basic_data["commonMistakes"] = mistakes_result["data"]
                logger.info(f"✅ Step 7 completed: {len(mistakes_result['data'])} mistakes")
            else:
                basic_data["commonMistakes"] = [
                    {"mistake": "Not properly closing HTML tags", "explanation": "Always ensure every opening tag has a matching closing tag to prevent layout issues"},
                    {"mistake": "Using incorrect attribute syntax", "explanation": "Use proper attribute format with quotes and valid values"},
                    {"mistake": "Missing required attributes", "explanation": "Include all necessary attributes for proper functionality and accessibility"},
                    {"mistake": "Improper nesting of elements", "explanation": "Follow HTML hierarchy rules and avoid invalid parent-child relationships"}
                ]
                logger.warning("Step 7 failed, using fallback mistakes")
            
            # Add final fields following strict format requirements
            concept_triggers = basic_data.get("tags", [])[:5] if basic_data.get("tags") else ["concept1", "concept2", "concept3", "concept4", "concept5"]
            basic_data["conceptTriggers"] = concept_triggers
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