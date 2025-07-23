# /Users/lokesh/Desktop/projects/qa-generator/src/ollama_client.py
import requests
import json
import subprocess
import hashlib
import logging
import re
import os
import time
from datetime import date
from typing import Dict, Any, List, Optional, Callable, Type

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class OllamaClient:
    def __init__(self, model: str = "qwen:7b"):
        self.base_url = "http://localhost:11434"
        self.model = model
        # Configurable timeout with environment variable support
        self.default_timeout = int(os.getenv('OLLAMA_TIMEOUT', '60'))  # Default 60 seconds
        self.max_retries = int(os.getenv('OLLAMA_MAX_RETRIES', '3'))
        self.retry_delay = float(os.getenv('OLLAMA_RETRY_DELAY', '2.0'))

    # ───────────────────── PUBLIC API ───────────────────── #

    def test_connection(self) -> Dict[str, Any]:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if r.status_code == 200:
                models = r.json().get("models", [])
                return {
                    "status": "connected",
                    "message": f"Ollama is running with {len(models)} models available",
                    "models": [m["name"] for m in models]
                }
            return {"status": "error", "message": f"HTTP {r.status_code}"}
        except requests.exceptions.ConnectionError:
            return {"status": "error", "message": "Cannot connect to Ollama. Run `ollama serve`."}
        except Exception as e:
            return {"status": "error", "message": f"Unexpected: {e}"}

    def list_models(self) -> List[Dict[str, Any]]:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if r.status_code == 200:
                return [
                    {
                        "name": m["name"],
                        "size": m.get("size", 0),
                        "modified": m.get("modified_at", ""),
                        "id": m.get("digest", "")[:12]
                    } for m in r.json().get("models", [])
                ]
        except Exception:
            pass
        return []

    def process_question_streaming(self, question: str, answer: str, prompt_template: str, emit_callback=None) -> Dict[str, Any]:
        return self.process_question_multi_step(question, answer, emit_callback)

    def process_question(self, question: str, answer: str, prompt_template: str) -> Dict[str, Any]:
        return self.process_question_multi_step(question, answer)

    # ─────────────────── CORE MULTI-STEP ─────────────────── #

    def process_question_multi_step(self, question: str, answer: str, emit_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Task-based processing - 13 separate Ollama tasks with temp file storage
        """
        import tempfile
        import os
        
        try:
            logger.info(f"🚀 Start 13-task processing for: {question[:60]}")
            logger.info(f"Timeout config: default={self.default_timeout}s, max_retries={self.max_retries}, retry_delay={self.retry_delay}s")
            
            # Create temp directory for task results
            temp_dir = tempfile.mkdtemp(prefix="qa_tasks_")
            task_results = {}
            
            # Task 1: Primary Question
            task_results["primaryQuestion"] = self._execute_task_1(question, temp_dir)
            
            # Task 2: Alternative Questions
            task_results["alternativeQuestions"] = self._execute_task_2(question, answer, temp_dir)
            
            # Task 3: Answer Descriptions
            task_results["answerDescriptions"] = self._execute_task_3(question, answer, temp_dir)
            
            # Task 4: Summary
            task_results["summary"] = self._execute_task_4(question, answer, temp_dir)
            
            # Task 5: Detailed Answer
            task_results["detailed"] = self._execute_task_5(question, answer, temp_dir)
            
            # Task 6: When to Use
            task_results["whenToUse"] = self._execute_task_6(question, answer, temp_dir)
            
            # Task 7: Real World Context
            task_results["realWorldContext"] = self._execute_task_7(question, answer, temp_dir)
            
            # Task 8: Category Details
            task_results["category"], task_results["subcategory"], task_results["difficulty"] = self._execute_task_8(question, temp_dir)
            
            # Task 9: Tags
            task_results["tags"] = self._execute_task_9(question, answer, temp_dir)
            
            # Task 10: Concept Triggers
            task_results["conceptTriggers"] = self._execute_task_10(question, answer, temp_dir)
            
            # Task 11: Natural Followups
            task_results["naturalFollowups"] = self._execute_task_11(question, answer, temp_dir)
            
            # Task 12: Related Questions
            task_results["relatedQuestions"] = self._execute_task_12(question, answer, temp_dir)
            
            # Task 13: Common Mistakes
            task_results["commonMistakes"] = self._execute_task_13(question, answer, temp_dir)
            
            # Assemble final JSON structure
            final_obj = self._assemble_final_json(question, task_results)
            
            # Clean up temp directory
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            if emit_callback:
                emit_callback({
                    "provider": "ollama",
                    "question": question,
                    "partial_response": json.dumps(final_obj, indent=2),
                    "is_complete": True
                })
            
            logger.info("✅ 13-task processing completed")
            return {"success": True, "data": final_obj, "raw_response": "ok"}
            
        except Exception as e:
            logger.exception("❌ 13-task processing failed")
            return {"success": False, "error": str(e), "raw_response": ""}

    # ─────────────────── HELPER METHODS ─────────────────── #

    def _ask_json(self, prompt: str, expect_type: Type, step: str, timeout: int = 60, max_attempts: int = 3) -> Any:
        """
        Call Ollama, extract JSON, type-check. If invalid, auto-repair up to max_attempts.
        """
        last_err = None
        last_raw = ""
        original_prompt = prompt
        for attempt in range(1, max_attempts + 1):
            res = self._simple_ollama_call(prompt, timeout=timeout)
            if res["success"]:
                data = res["data"]
                if isinstance(data, expect_type):
                    return data
                last_err = f"type mismatch (expected {expect_type.__name__}, got {type(data).__name__})"
                last_raw = json.dumps(data, ensure_ascii=False) if isinstance(data, (dict, list)) else str(data)
                logger.debug(f"[{step}] Type mismatch - expected {expect_type.__name__}, got: {last_raw[:200]}")
            else:
                last_err = res.get("error", "unknown")
                last_raw = res.get("raw", "")

            # Only try repair if we have more attempts left
            if attempt < max_attempts:
                # Simple repair prompt
                prompt = f"The previous attempt failed. Please try again:\n{original_prompt}"

        raise ValueError(f"[{step}] Failed after {max_attempts} attempts. Last error: {last_err}")

    def _simple_ollama_call(self, prompt: str, timeout: int = 60) -> Dict[str, Any]:
        actual_timeout = timeout or self.default_timeout
        
        for attempt in range(self.max_retries):
            try:
                payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Lower temperature for more consistent output
                        "top_p": 0.8,
                        "num_predict": 2048,  # Reduced prediction length
                        "repeat_penalty": 1.1
                    }
                }
                resp = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=actual_timeout)
                if resp.status_code != 200:
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                    return {"success": False, "error": f"HTTP {resp.status_code}"}

                text = resp.json().get("response", "").strip()
                parsed = self._extract_json(text)
                if parsed is not None:
                    return {"success": True, "data": parsed}
                return {"success": False, "error": "Could not parse JSON", "raw": text[:1000]}
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout on attempt {attempt + 1}/{self.max_retries} (timeout: {actual_timeout}s)")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                    continue
                return {"success": False, "error": f"Request timed out after {actual_timeout}s"}
            except Exception as e:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
                    continue
                return {"success": False, "error": str(e)}
        
        return {"success": False, "error": "Max retries exceeded"}

    def _ollama_request_with_retry(self, payload: dict, timeout: int = None) -> Optional[requests.Response]:
        """Make an Ollama API request with retry logic"""
        actual_timeout = timeout or self.default_timeout
        prompt_preview = payload.get('prompt', '')[:100] + '...' if len(payload.get('prompt', '')) > 100 else payload.get('prompt', '')
        logger.debug(f"Making Ollama request with timeout={actual_timeout}s for prompt: {prompt_preview}")
        
        for attempt in range(self.max_retries):
            try:
                start_time = time.time()
                resp = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=actual_timeout)
                elapsed = time.time() - start_time
                
                if resp.status_code == 200:
                    logger.debug(f"Request successful in {elapsed:.1f}s")
                    return resp
                elif attempt < self.max_retries - 1:
                    logger.warning(f"HTTP {resp.status_code} on attempt {attempt + 1}/{self.max_retries} (took {elapsed:.1f}s)")
                    time.sleep(self.retry_delay * (2 ** attempt))
                    continue
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout on attempt {attempt + 1}/{self.max_retries} after {actual_timeout}s")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
                    continue
            except Exception as e:
                logger.warning(f"Error on attempt {attempt + 1}/{self.max_retries}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
                    continue
        
        logger.error(f"All {self.max_retries} attempts failed for prompt: {prompt_preview}")
        return None

    def _extract_json(self, text: str) -> Optional[Any]:
        text = text.strip()
        
        # Handle markdown code blocks
        if "```json" in text:
            match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
            if match:
                text = match.group(1).strip()
        elif "```" in text:
            match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
            if match:
                text = match.group(1).strip()
        
        # Try direct parsing first
        if text.startswith("{") or text.startswith("["):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

        # Find JSON in text
        start_obj = text.find("{")
        start_arr = text.find("[")
        starts = [i for i in [start_obj, start_arr] if i != -1]
        if not starts:
            return None
        start = min(starts)

        opener = text[start]
        closer = "}" if opener == "{" else "]"
        end = self._find_matching(text, start, opener, closer)
        snippet = text[start:] if end == -1 else text[start:end + 1]

        try:
            return json.loads(snippet)
        except Exception:
            cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', snippet)
            cleaned = re.sub(r',(\s*[}\]])', r'\1', cleaned)
            try:
                return json.loads(cleaned)
            except Exception:
                return None

    @staticmethod
    def _find_matching(s: str, start: int, open_ch: str, close_ch: str) -> int:
        depth = 0
        for i, ch in enumerate(s[start:], start):
            if ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    return i
        return -1

    @staticmethod
    def _slugify(text: str) -> str:
        text = text.lower()
        text = re.sub(r'[^a-z0-9]+', '-', text).strip('-')
        return re.sub(r'-+', '-', text)

    def _make_id(self, question: str) -> str:
        slug = self._slugify(question)[:30]
        h = hashlib.md5(question.encode("utf-8")).hexdigest()[:6]
        return f"question-{slug}-{h}"

    @staticmethod
    def _ensure_len(arr: list, exact: int, field: str):
        if len(arr) != exact:
            raise ValueError(f"{field} must have EXACTLY {exact} items. Got {len(arr)}")

    @staticmethod
    def _ensure_len_range(arr: list, lo: int, hi: int, field: str):
        if not (lo <= len(arr) <= hi):
            raise ValueError(f"{field} must have between {lo} and {hi} items. Got {len(arr)}")

    @staticmethod
    def _ensure_keys(obj: dict, keys: List[str], ctx: str):
        missing = [k for k in keys if k not in obj]
        if missing:
            raise ValueError(f"{ctx} missing keys: {missing}")

    @staticmethod
    def _ensure_all_str(arr: list, field: str):
        if not all(isinstance(x, str) for x in arr):
            raise ValueError(f"All items in {field} must be strings.")
    
    def _clean_array_response(self, arr: list) -> list:
        """Clean array response from qwen - handle objects, extract strings"""
        cleaned = []
        for item in arr:
            if isinstance(item, str):
                cleaned.append(item)
            elif isinstance(item, dict):
                # Try common keys
                val = item.get('question') or item.get('tag') or item.get('point') or list(item.values())[0] if item else str(item)
                cleaned.append(str(val))
            else:
                cleaned.append(str(item))
        return cleaned

    def _extract_category(self, question: str) -> str:
        """Extract category from question - simple approach"""
        q_lower = question.lower()
        if 'angular' in q_lower:
            return "Frameworks"
        elif 'react' in q_lower:
            return "Frameworks"
        elif 'html' in q_lower or '<' in q_lower:
            return "HTML"
        elif 'css' in q_lower or 'style' in q_lower:
            return "CSS"
        elif 'javascript' in q_lower or 'js' in q_lower:
            return "JavaScript"
        else:
            return "Web Development"
    
    def _extract_subcategory(self, question: str) -> str:
        """Extract subcategory - simple approach"""
        q_lower = question.lower()
        if 'angular' in q_lower:
            return "Angular"
        elif 'react' in q_lower:
            return "React"
        elif 'tag' in q_lower:
            return "Tags"
        elif 'form' in q_lower:
            return "Forms"
        elif 'style' in q_lower:
            return "Styling"
        else:
            return "General"
    
    
    def _get_simple_text(self, prompt: str, field_name: str) -> Optional[str]:
        """Get a simple text response from Ollama"""
        try:
            payload = {
                "model": self.model,
                "prompt": prompt + "\n\nRespond with only the text, no JSON or formatting.",
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 200
                }
            }
            resp = self._ollama_request_with_retry(payload, timeout=45)
            if resp:
                text = resp.json().get("response", "").strip()
                # Clean up any markdown or formatting
                text = text.replace('```', '').strip()
                return text if text else None
        except Exception as e:
            logger.debug(f"Failed to get {field_name}: {e}")
        return None
    
    def _get_text_list(self, prompt: str, field_name: str, expected_count: int) -> List[str]:
        """Get a list of text items from Ollama"""
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.5,
                    "num_predict": 1000
                }
            }
            resp = self._ollama_request_with_retry(payload, timeout=45)
            if resp:
                text = resp.json().get("response", "").strip()
                # Split by newlines and clean up
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                # Remove any numbering like "1. " or "- "
                cleaned = []
                for line in lines:
                    # Remove common prefixes
                    line = re.sub(r'^\d+\.\s*', '', line)  # Remove "1. "
                    line = re.sub(r'^-\s*', '', line)      # Remove "- "
                    line = re.sub(r'^\*\s*', '', line)     # Remove "* "
                    line = line.strip('"\'')               # Remove quotes
                    if line and len(line) > 5:  # Skip very short responses
                        cleaned.append(line)
                
                # If we got some good responses, use them
                if len(cleaned) >= expected_count // 2:  # At least half
                    # Pad with variations if needed
                    while len(cleaned) < expected_count:
                        base = cleaned[len(cleaned) % len(cleaned)]
                        cleaned.append(f"{base} - variation {len(cleaned) + 1}")
                    return cleaned[:expected_count]
                    
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout getting {field_name}, using defaults")
        except Exception as e:
            logger.debug(f"Failed to get {field_name}: {e}")
        
        # Return reasonable defaults based on field type
        if "question" in field_name.lower():
            # Extract base question from prompt if possible
            base_q = prompt.split('"')[1] if '"' in prompt else "this topic"
            return self._generate_default_questions(base_q, expected_count)
        elif "tag" in field_name.lower():
            # Extract base question from prompt if possible
            base_q = prompt.split('"')[1] if '"' in prompt else "topic"
            return self._generate_default_tags(base_q, expected_count)
        else:
            return [f"{field_name} {i+1}" for i in range(expected_count)]
    
    def _generate_default_questions(self, base_question: str, count: int) -> List[str]:
        """Generate default question variations"""
        variations = [
            f"Can you explain {base_question.lower()}",
            f"What do you mean by {base_question.lower()}",
            f"Tell me about {base_question.lower()}",
            f"How would you describe {base_question.lower()}",
            f"What's the answer to {base_question.lower()}",
            f"Could you clarify {base_question.lower()}",
            f"Please elaborate on {base_question.lower()}",
            f"What are the details of {base_question.lower()}",
            f"Can you provide information about {base_question.lower()}",
            f"What should I know about {base_question.lower()}"
        ]
        return variations[:count]
    
    def _generate_default_tags(self, question: str, count: int) -> List[str]:
        """Generate default tags based on question"""
        words = re.findall(r'\w+', question.lower())
        tags = []
        
        # Add relevant words as tags
        for word in words:
            if len(word) > 3 and word not in ['what', 'how', 'when', 'where', 'why', 'which', 'the', 'and', 'or']:
                tags.append(word)
        
        # Add some generic tags
        tags.extend(['web-development', 'programming', 'technical', 'interview'])
        
        # Ensure we have enough
        while len(tags) < count:
            tags.append(f'tag-{len(tags)+1}')
            
        return tags[:count]
    
    def _get_mistakes(self, question: str) -> List[Dict[str, str]]:
        """Get common mistakes"""
        try:
            prompt = f'List 3 common mistakes people make regarding: "{question}"\nFormat each as: mistake: description'
            
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.5,
                    "num_predict": 500
                }
            }
            resp = self._ollama_request_with_retry(payload, timeout=45)
            
            mistakes = []
            if resp:
                text = resp.json().get("response", "").strip()
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                
                for line in lines[:3]:
                    # Try to parse "mistake: description" format
                    if ':' in line:
                        parts = line.split(':', 1)
                        mistake = parts[0].strip()
                        desc = parts[1].strip() if len(parts) > 1 else "Common error"
                        
                        # Clean up
                        mistake = re.sub(r'^\d+\.\s*', '', mistake)
                        mistake = re.sub(r'^-\s*', '', mistake)
                        
                        mistakes.append({
                            "mistake": mistake,
                            "description": desc
                        })
            
            # Ensure we have at least 3
            while len(mistakes) < 3:
                mistakes.append({
                    "mistake": f"Common mistake {len(mistakes) + 1}",
                    "description": "Be careful with this aspect."
                })
            
            return mistakes[:3]
            
        except Exception as e:
            logger.debug(f"Failed to get mistakes: {e}")
            
        return [
            {"mistake": "Not understanding the concept", "description": "Take time to learn the basics."},
            {"mistake": "Incorrect implementation", "description": "Follow best practices."},
            {"mistake": "Poor error handling", "description": "Always handle edge cases."}
        ]
    
    def _generate_default_mistakes(self, question: str) -> List[Dict[str, str]]:
        """Generate default mistakes based on question"""
        topic = question.lower()
        
        if 'html' in topic or 'tag' in topic:
            return [
                {"mistake": "Not closing HTML tags properly", "description": "Always ensure every opening tag has a matching closing tag"},
                {"mistake": "Using incorrect attributes", "description": "Check documentation for valid attributes for each HTML element"},
                {"mistake": "Poor semantic structure", "description": "Use appropriate HTML elements for their intended purpose"}
            ]
        elif 'css' in topic or 'style' in topic:
            return [
                {"mistake": "Not using proper selectors", "description": "Learn CSS selector specificity and best practices"},
                {"mistake": "Inline styles everywhere", "description": "Use external CSS files for better maintainability"},
                {"mistake": "Not considering responsive design", "description": "Always design with mobile-first approach"}
            ]
        else:
            return [
                {"mistake": "Not understanding the fundamentals", "description": "Build a strong foundation before advanced concepts"},
                {"mistake": "Skipping best practices", "description": "Follow industry standards and conventions"},
                {"mistake": "Not testing thoroughly", "description": "Test your implementation in different scenarios"}
            ]

    # ─────────────────── 13 INDIVIDUAL TASKS ─────────────────── #
    
    def _execute_task_1(self, question: str, temp_dir: str) -> str:
        """Task 1: Generate primaryQuestion"""
        start_time = time.time()
        result = question  # Use input question as primary
        self._save_task_result(temp_dir, "task1_primary.txt", result)
        logger.debug(f"Task 1 completed in {time.time() - start_time:.1f}s: primaryQuestion")
        return result
    
    def _execute_task_2(self, question: str, answer: str, temp_dir: str) -> List[str]:
        """Task 2: Generate alternativeQuestions (10 items)"""
        start_time = time.time()
        prompt = f'Generate 10 alternative ways to ask this question: "{question}"\nAnswer context: {answer[:200]}\nRespond ONLY in English. Return only the questions, one per line, no numbering.'
        result = self._ollama_call_for_list(prompt, 10, "alternative questions")
        self._save_task_result(temp_dir, "task2_alternatives.json", json.dumps(result, indent=2))
        logger.debug(f"Task 2 completed in {time.time() - start_time:.1f}s: alternativeQuestions (got {len(result)} items)")
        return result
    
    def _execute_task_3(self, question: str, answer: str, temp_dir: str) -> List[str]:
        """Task 3: Generate answerDescriptions (4 items)"""
        prompt = f'List 4 key points that describe the answer to: "{question}"\nAnswer context: {answer[:200]}\nRespond ONLY in English. Return only the points, one per line.'
        result = self._ollama_call_for_list(prompt, 4, "answer descriptions")
        self._save_task_result(temp_dir, "task3_descriptions.json", json.dumps(result, indent=2))
        logger.debug("Task 3 completed: answerDescriptions")
        return result
    
    def _execute_task_4(self, question: str, answer: str, temp_dir: str) -> str:
        """Task 4: Generate summary"""
        prompt = f'Write a concise one-sentence summary for: "{question}"\nBased on: {answer[:300]}\nRespond ONLY in English. Return only the summary text.'
        result = self._ollama_call_for_text(prompt, "summary")
        self._save_task_result(temp_dir, "task4_summary.txt", result)
        logger.debug("Task 4 completed: summary")
        return result
    
    def _execute_task_5(self, question: str, answer: str, temp_dir: str) -> str:
        """Task 5: Generate detailed answer"""
        prompt = f'Write a detailed explanation for: "{question}"\nExpand on: {answer}\nRespond ONLY in English. Include examples and technical details.'
        result = self._ollama_call_for_text(prompt, "detailed answer")
        self._save_task_result(temp_dir, "task5_detailed.txt", result)
        logger.debug("Task 5 completed: detailed answer")
        return result
    
    def _execute_task_6(self, question: str, answer: str, temp_dir: str) -> str:
        """Task 6: Generate whenToUse"""
        prompt = f'Based on this Q&A: "{question}" -> "{answer[:200]}"\nComplete: "Use this when..."\nRespond ONLY in English. Return only the completion text.'
        result = self._ollama_call_for_text(prompt, "when to use")
        if not result.startswith("Use"):
            result = f"Use {result}" if result else "Use when needed."
        self._save_task_result(temp_dir, "task6_whentouse.txt", result)
        logger.debug("Task 6 completed: whenToUse")
        return result
    
    def _execute_task_7(self, question: str, answer: str, temp_dir: str) -> str:
        """Task 7: Generate realWorldContext"""
        prompt = f'Based on this Q&A: "{question}" -> "{answer[:200]}"\nGive a real-world context or example where this applies.\nRespond ONLY in English. Return only the context description.'
        result = self._ollama_call_for_text(prompt, "real world context")
        self._save_task_result(temp_dir, "task7_context.txt", result)
        logger.debug("Task 7 completed: realWorldContext")
        return result
    
    def _execute_task_8(self, question: str, temp_dir: str) -> tuple:
        """Task 8: Generate category, subcategory, difficulty"""
        category = self._extract_category(question)
        subcategory = self._extract_subcategory(question)
        difficulty = "Intermediate"  # Default
        
        result = {"category": category, "subcategory": subcategory, "difficulty": difficulty}
        self._save_task_result(temp_dir, "task8_categories.json", json.dumps(result, indent=2))
        logger.debug("Task 8 completed: category details")
        return category, subcategory, difficulty
    
    def _execute_task_9(self, question: str, answer: str, temp_dir: str) -> List[str]:
        """Task 9: Generate tags (5-10 items)"""
        prompt = f'Generate 8 relevant technical tags based on this Q&A:\nQ: "{question}"\nA: "{answer[:200]}"\nRespond ONLY in English. Use only English words. Return only the tags, one per line.'
        result = self._ollama_call_for_list(prompt, 8, "tags")
        self._save_task_result(temp_dir, "task9_tags.json", json.dumps(result, indent=2))
        logger.debug("Task 9 completed: tags")
        return result
    
    def _execute_task_10(self, question: str, answer: str, temp_dir: str) -> List[str]:
        """Task 10: Generate conceptTriggers (5-10 items)"""
        prompt = f'List 10 key concepts or triggers based on this Q&A:\nQ: "{question}"\nA: "{answer[:200]}"\nRespond ONLY in English. Return only the concepts, one per line.'
        result = self._ollama_call_for_list(prompt, 10, "concept triggers")
        self._save_task_result(temp_dir, "task10_triggers.json", json.dumps(result, indent=2))
        logger.debug("Task 10 completed: conceptTriggers")
        return result
    
    def _execute_task_11(self, question: str, answer: str, temp_dir: str) -> List[str]:
        """Task 11: Generate naturalFollowups (5-10 items)"""
        prompt = f'Generate 10 natural follow-up questions based on this Q&A:\nQ: "{question}"\nA: "{answer[:200]}"\nRespond ONLY in English. Return only the questions, one per line.'
        result = self._ollama_call_for_list(prompt, 10, "natural followups")
        self._save_task_result(temp_dir, "task11_followups.json", json.dumps(result, indent=2))
        logger.debug("Task 11 completed: naturalFollowups")
        return result
    
    def _execute_task_12(self, question: str, answer: str, temp_dir: str) -> List[str]:
        """Task 12: Generate relatedQuestions (5-10 items)"""
        prompt = f'List 10 related questions based on this Q&A:\nQ: "{question}"\nA: "{answer[:200]}"\nRespond ONLY in English. Return only the questions, one per line.'
        result = self._ollama_call_for_list(prompt, 10, "related questions")
        self._save_task_result(temp_dir, "task12_related.json", json.dumps(result, indent=2))
        logger.debug("Task 12 completed: relatedQuestions")
        return result
    
    def _execute_task_13(self, question: str, answer: str, temp_dir: str) -> List[Dict[str, str]]:
        """Task 13: Generate commonMistakes (3-5 items)"""
        prompt = f'List 3 common mistakes based on this Q&A:\nQ: "{question}"\nA: "{answer[:200]}"\nRespond ONLY in English. Format: mistake|description (separated by pipe)'
        result = self._ollama_call_for_mistakes(prompt, 3, "common mistakes")
        self._save_task_result(temp_dir, "task13_mistakes.json", json.dumps(result, indent=2))
        logger.debug("Task 13 completed: commonMistakes")
        return result
    
    def _save_task_result(self, temp_dir: str, filename: str, content: str):
        """Save task result to temp file"""
        filepath = f"{temp_dir}/{filename}"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _assemble_final_json(self, question: str, task_results: dict) -> dict:
        """Assemble all task results into final JSON format"""
        qid = self._make_id(question)
        
        final_obj = {
            qid: {
                "primaryQuestion": task_results["primaryQuestion"],
                "alternativeQuestions": task_results["alternativeQuestions"],
                "answerDescriptions": task_results["answerDescriptions"],
                "answer": {
                    "summary": task_results["summary"],
                    "detailed": task_results["detailed"],
                    "whenToUse": task_results["whenToUse"],
                    "realWorldContext": task_results["realWorldContext"]
                },
                "category": task_results["category"],
                "subcategory": task_results["subcategory"],
                "difficulty": task_results["difficulty"],
                "tags": task_results["tags"],
                "conceptTriggers": task_results["conceptTriggers"],
                "naturalFollowups": task_results["naturalFollowups"],
                "relatedQuestions": task_results["relatedQuestions"],
                "commonMistakes": task_results["commonMistakes"],
                "confidence": "high",
                "lastUpdated": str(date.today()),
                "verified": False
            }
        }
        return final_obj
    
    def _ollama_call_for_text(self, prompt: str, field_name: str) -> str:
        """Call Ollama for simple text response"""
        try:
            logger.debug(f"Calling Ollama for {field_name}, prompt length: {len(prompt)} chars")
            payload = {
                "model": self.model,
                "prompt": prompt + "\n\nRespond ONLY in English. Use only English words. No formatting or extra words.",
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 300
                }
            }
            resp = self._ollama_request_with_retry(payload, timeout=60)
            if resp:
                text = resp.json().get("response", "").strip()
                return text if text else f"Generated {field_name}"
        except Exception as e:
            logger.debug(f"Failed to get {field_name}: {e}")
        return f"Generated {field_name}"
    
    def _ollama_call_for_list(self, prompt: str, expected_count: int, field_name: str) -> List[str]:
        """Call Ollama for list response"""
        try:
            logger.debug(f"Calling Ollama for {field_name}, expected {expected_count} items, prompt length: {len(prompt)} chars")
            payload = {
                "model": self.model,
                "prompt": prompt + "\n\nRespond ONLY in English. Use only English words.",
                "stream": False,
                "options": {
                    "temperature": 0.5,
                    "num_predict": 800
                }
            }
            resp = self._ollama_request_with_retry(payload, timeout=60)
            if resp:
                text = resp.json().get("response", "").strip()
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                
                cleaned = []
                for line in lines:
                    line = re.sub(r'^\d+\.\s*', '', line)  # Remove "1. "
                    line = re.sub(r'^-\s*', '', line)      # Remove "- "
                    line = re.sub(r'^\*\s*', '', line)     # Remove "* "
                    line = line.strip('"\'')               # Remove quotes
                    if line and len(line) > 3:
                        cleaned.append(line)
                
                if len(cleaned) > 0:
                    # Return what we got, don't add artificial variations
                    return cleaned[:expected_count] if len(cleaned) >= expected_count else cleaned
                    
        except Exception as e:
            logger.debug(f"Failed to get {field_name}: {e}")
        
        # Generate minimal defaults or return empty
        if "question" in field_name.lower():
            base_q = prompt.split('"')[1] if '"' in prompt else "topic"
            return self._generate_default_questions(base_q, min(3, expected_count))  # Only 3 defaults max
        elif "tag" in field_name.lower():
            base_q = prompt.split('"')[1] if '"' in prompt else "topic"  
            return self._generate_default_tags(base_q, min(3, expected_count))  # Only 3 defaults max
        else:
            # For other fields, return fewer items rather than filling with junk
            return []  # Return empty instead of artificial items
    
    def _ollama_call_for_mistakes(self, prompt: str, expected_count: int, field_name: str) -> List[Dict[str, str]]:
        """Call Ollama for mistakes response"""
        try:
            payload = {
                "model": self.model,
                "prompt": prompt + "\n\nRespond ONLY in English. Use only English words.",
                "stream": False,
                "options": {
                    "temperature": 0.5,
                    "num_predict": 600
                }
            }
            resp = self._ollama_request_with_retry(payload, timeout=60)
            
            mistakes = []
            if resp:
                text = resp.json().get("response", "").strip()
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                
                for line in lines[:expected_count]:
                    if '|' in line:
                        parts = line.split('|', 1)
                        mistake = parts[0].strip()
                        desc = parts[1].strip() if len(parts) > 1 else "Common error"
                    elif ':' in line:
                        parts = line.split(':', 1)
                        mistake = parts[0].strip()
                        desc = parts[1].strip() if len(parts) > 1 else "Common error"
                    else:
                        mistake = line
                        desc = "Be careful with this aspect."
                    
                    # Clean up
                    mistake = re.sub(r'^\d+\.\s*', '', mistake)
                    mistake = re.sub(r'^-\s*', '', mistake)
                    
                    mistakes.append({
                        "mistake": mistake,
                        "description": desc
                    })
            
            # Don't pad with artificial mistakes - return what we got
            return mistakes[:expected_count] if len(mistakes) >= expected_count else mistakes
            
        except Exception as e:
            logger.debug(f"Failed to get {field_name}: {e}")
            
        # Return minimal fallback - only 1-2 generic mistakes rather than filling expected_count
        return [
            {"mistake": "Not understanding the fundamentals", "description": "Take time to learn the basics."},
            {"mistake": "Skipping best practices", "description": "Follow proper implementation guidelines."}
        ][:min(2, expected_count)]

    def get_available_models_from_cli(self) -> List[str]:
        try:
            result = subprocess.run(['ollama', 'list'], capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]
                return [line.split()[0] for line in lines if line]
        except Exception:
            pass
        return []


