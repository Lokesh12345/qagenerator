"""
Enhanced web scraper with answer extraction support
"""
import re
import json
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Tuple, Optional
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.configs = self._load_configs()
        
    def _load_configs(self) -> Dict:
        """Load site-specific scraping configurations"""
        configs = {}
        config_dir = os.path.join(os.path.dirname(__file__), 'scraper_configs')
        
        if os.path.exists(config_dir):
            for filename in os.listdir(config_dir):
                if filename.endswith('.json'):
                    with open(os.path.join(config_dir, filename), 'r') as f:
                        config = json.load(f)
                        for pattern in config.get('patterns', []):
                            configs[pattern] = config
        
        return configs
    
    def _get_site_config(self, url: str) -> Optional[Dict]:
        """Get configuration for a specific site"""
        domain = urlparse(url).netloc
        for pattern, config in self.configs.items():
            if pattern in domain:
                return config
        return None
    
    def _extract_text_from_elements(self, soup, selectors: List[str], parent=None) -> str:
        """Extract and combine text from multiple elements"""
        texts = []
        search_in = parent if parent else soup
        
        for selector in selectors:
            elements = search_in.find_all(selector)
            for elem in elements:
                text = elem.get_text(strip=True)
                if text and len(text) > 10:  # Skip very short texts
                    texts.append(text)
        
        return '\n\n'.join(texts)
    
    def _extract_answer_interviewbit(self, question_elem, soup) -> Optional[str]:
        """Extract answer for InterviewBit based on their HTML structure"""
        answer_parts = []
        
        # Look for the next siblings after the question
        current = question_elem.find_next_sibling()
        
        while current and current.name not in ['h2', 'h3', 'section']:
            if current.name in ['p', 'div', 'ul', 'ol', 'pre']:
                text = current.get_text(strip=True)
                if text:
                    answer_parts.append(text)
                    
                # Check for code blocks
                code_blocks = current.find_all(['pre', 'code'])
                for code in code_blocks:
                    code_text = code.get_text(strip=True)
                    if code_text and code_text not in answer_parts:
                        answer_parts.append(f"```\n{code_text}\n```")
            
            current = current.find_next_sibling()
            
            # Stop if we've collected enough content
            if len('\n'.join(answer_parts)) > 2000:
                break
        
        return '\n\n'.join(answer_parts) if answer_parts else None
    
    def scrape_with_answers(self, url: str, limit: int = 50) -> List[Dict]:
        """Scrape questions and answers from a given URL"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            qa_pairs = []
            config = self._get_site_config(url)
            
            if not config:
                logger.warning(f"No configuration found for {url}, using default scraping")
                return self._scrape_default(soup, url, limit)
            
            # Use site-specific scraping based on config
            if 'interviewbit.com' in url:
                return self._scrape_interviewbit_with_answers(soup, url, limit)
            elif 'geeksforgeeks.org' in url:
                return self._scrape_geeksforgeeks_with_answers(soup, url, limit)
            elif 'javatpoint.com' in url:
                return self._scrape_javatpoint_with_answers(soup, url, limit)
            else:
                return self._scrape_default(soup, url, limit)
                
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return []
    
    def _scrape_interviewbit_with_answers(self, soup, url: str, limit: int) -> List[Dict]:
        """Scrape InterviewBit with answer extraction"""
        qa_pairs = []
        
        # Method 1: Look for h3 questions
        questions = soup.find_all('h3')
        
        for i, q_elem in enumerate(questions):
            if len(qa_pairs) >= limit:
                break
                
            question_text = q_elem.get_text(strip=True)
            
            # Filter out non-questions
            if not any(keyword in question_text.lower() for keyword in ['?', 'what', 'how', 'why', 'when', 'which', 'explain']):
                continue
            
            # Extract answer
            answer = self._extract_answer_interviewbit(q_elem, soup)
            
            qa_pairs.append({
                'id': f'ib-q{i+1}',
                'question': question_text,
                'answer': answer or "Answer not found - will be generated by AI",
                'source': url,
                'has_answer': answer is not None
            })
        
        # Method 2: Look for numbered questions
        if len(qa_pairs) < limit:
            pattern = re.compile(r'^(\d+)\.\s+(.+\?)', re.MULTILINE)
            text_content = soup.get_text()
            matches = pattern.findall(text_content)
            
            for i, (num, question) in enumerate(matches[len(qa_pairs):]):
                if len(qa_pairs) >= limit:
                    break
                    
                qa_pairs.append({
                    'id': f'ib-q{len(qa_pairs)+1}',
                    'question': question.strip(),
                    'answer': "Answer not found - will be generated by AI",
                    'source': url,
                    'has_answer': False
                })
        
        return qa_pairs
    
    def _scrape_geeksforgeeks_with_answers(self, soup, url: str, limit: int) -> List[Dict]:
        """Scrape GeeksforGeeks with answer extraction"""
        qa_pairs = []
        
        # Look for question-answer pairs
        articles = soup.find_all(['article', 'div'], class_=['article-content', 'content'])
        
        for article in articles:
            questions = article.find_all(['h2', 'h3', 'strong'])
            
            for q_elem in questions:
                if len(qa_pairs) >= limit:
                    break
                    
                question_text = q_elem.get_text(strip=True)
                if '?' in question_text or any(kw in question_text.lower() for kw in ['what', 'how', 'explain']):
                    # Find answer in following elements
                    answer_parts = []
                    next_elem = q_elem.find_next_sibling()
                    
                    while next_elem and next_elem.name not in ['h2', 'h3', 'strong']:
                        if next_elem.name in ['p', 'div', 'ul', 'pre']:
                            answer_parts.append(next_elem.get_text(strip=True))
                        next_elem = next_elem.find_next_sibling()
                    
                    answer = '\n\n'.join(answer_parts) if answer_parts else None
                    
                    qa_pairs.append({
                        'id': f'gfg-q{len(qa_pairs)+1}',
                        'question': question_text,
                        'answer': answer or "Answer not found - will be generated by AI",
                        'source': url,
                        'has_answer': answer is not None
                    })
        
        return qa_pairs
    
    def _scrape_javatpoint_with_answers(self, soup, url: str, limit: int) -> List[Dict]:
        """Scrape JavaTpoint with answer extraction"""
        qa_pairs = []
        
        # Look for h2/h3 questions
        headers = soup.find_all(['h2', 'h3'])
        
        for header in headers:
            if len(qa_pairs) >= limit:
                break
                
            question_text = header.get_text(strip=True)
            
            # Check if it's a question
            if '?' in question_text or re.match(r'^\d+\)', question_text):
                # Extract answer from following elements
                answer_parts = []
                current = header.find_next_sibling()
                
                while current and current.name not in ['h2', 'h3']:
                    if current.name in ['p', 'div', 'table', 'pre', 'ul']:
                        text = current.get_text(strip=True)
                        if text:
                            answer_parts.append(text)
                    current = current.find_next_sibling()
                
                answer = '\n\n'.join(answer_parts) if answer_parts else None
                
                qa_pairs.append({
                    'id': f'jtp-q{len(qa_pairs)+1}',
                    'question': question_text,
                    'answer': answer or "Answer not found - will be generated by AI",
                    'source': url,
                    'has_answer': answer is not None
                })
        
        return qa_pairs
    
    def _scrape_default(self, soup, url: str, limit: int) -> List[Dict]:
        """Default scraping when no specific config is available"""
        qa_pairs = []
        
        # Look for common question patterns
        potential_questions = soup.find_all(['h1', 'h2', 'h3', 'strong', 'b'])
        
        for elem in potential_questions:
            if len(qa_pairs) >= limit:
                break
                
            text = elem.get_text(strip=True)
            
            # Check if it looks like a question
            if ('?' in text or 
                any(kw in text.lower() for kw in ['what', 'how', 'why', 'when', 'explain', 'describe']) or
                re.match(r'^\d+[\.\)]\s+', text)):
                
                qa_pairs.append({
                    'id': f'q{len(qa_pairs)+1}',
                    'question': text,
                    'answer': "Answer not found - will be generated by AI",
                    'source': url,
                    'has_answer': False
                })
        
        return qa_pairs
    
    def discover_question_count(self, url: str) -> int:
        """Quick discovery of available questions without full scraping"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Count potential questions
            count = 0
            
            # Count h3 tags (common for questions)
            h3_tags = soup.find_all('h3')
            count += len([h for h in h3_tags if '?' in h.get_text() or any(kw in h.get_text().lower() for kw in ['what', 'how', 'explain'])])
            
            # Count numbered patterns
            text = soup.get_text()
            numbered_pattern = re.compile(r'^\d+[\.\)]\s+.+\?', re.MULTILINE)
            count += len(numbered_pattern.findall(text))
            
            return count
            
        except Exception as e:
            logger.error(f"Error discovering questions in {url}: {e}")
            return 0