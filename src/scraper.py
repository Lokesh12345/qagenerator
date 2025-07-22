"""
Intelligent web scraper for interview questions and answers
"""
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Tuple, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InterviewScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def scrape_interviewbit_angular(self, limit: int = 50) -> List[Dict]:
        """Scrape Angular questions from InterviewBit"""
        url = "https://www.interviewbit.com/angular-interview-questions/"
        return self._scrape_interviewbit_generic(url, 'Angular', limit)
    
    def scrape_interviewbit_javascript(self, limit: int = 50) -> List[Dict]:
        """Scrape JavaScript questions from InterviewBit"""
        url = "https://www.interviewbit.com/javascript-interview-questions/"
        return self._scrape_interviewbit_generic(url, 'JavaScript', limit)
    
    def _scrape_interviewbit_generic(self, url: str, category: str, limit: int = 50) -> List[Dict]:
        """Generic InterviewBit scraper that works for all topics"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            qa_pairs = []
            
            # Method 1: Look for sections with h3 questions and following article content
            sections = soup.find_all('section', class_='ibpage-article-header')
            
            for i, section in enumerate(sections):
                if len(qa_pairs) >= limit:
                    break
                    
                try:
                    # Extract question from h3
                    question_elem = section.find('h3')
                    if not question_elem:
                        continue
                        
                    question = self._clean_text(question_elem.get_text())
                    if not question or len(question) < 10:
                        continue
                    
                    # Extract answer from next sibling article element
                    article = section.find_next_sibling('article', class_='ibpage-article')
                    if not article:
                        # Try finding article within the section
                        article = section.find('article', class_='ibpage-article')
                    
                    if not article:
                        continue
                    
                    answer_parts = []
                    # Get text from various elements in the article
                    for elem in article.find_all(['p', 'div', 'ul', 'ol', 'li', 'pre', 'code']):
                        text = self._clean_text(elem.get_text())
                        if text and len(text) > 15:  # Lower threshold for better extraction
                            answer_parts.append(text)
                    
                    answer = ' '.join(answer_parts[:6])  # Increase limit for better answers
                    
                    if answer and len(answer) > 30:  # Lower threshold for better coverage
                        qa_pairs.append({
                            'id': f"{category.lower()}-q{len(qa_pairs)+1}",
                            'question': question,
                            'answer': answer,
                            'source': url,
                            'category': category
                        })
                        
                        logger.info(f"Scraped Q{len(qa_pairs)}: {question[:60]}...")
                        
                except Exception as e:
                    logger.error(f"Error processing section {i}: {e}")
                    continue
            
            # Method 2: Alternative approach - find h3 elements and their following content
            if len(qa_pairs) < limit // 2:  # If we didn't get enough questions
                h3_elements = soup.find_all('h3')
                
                for h3 in h3_elements:
                    if len(qa_pairs) >= limit:
                        break
                        
                    try:
                        question = self._clean_text(h3.get_text())
                        if not question or len(question) < 10:
                            continue
                        
                        # Skip if this question is already captured
                        if any(qa['question'] == question for qa in qa_pairs):
                            continue
                        
                        # Find answer in following siblings
                        answer_parts = []
                        current = h3.find_next_sibling()
                        collected = 0
                        
                        while current and collected < 4:
                            if current.name == 'h3':  # Stop at next question
                                break
                            if current.name in ['p', 'div', 'ul', 'ol', 'article']:
                                text = self._clean_text(current.get_text())
                                if text and len(text) > 15:
                                    answer_parts.append(text)
                                    collected += 1
                            current = current.find_next_sibling()
                        
                        answer = ' '.join(answer_parts)
                        
                        if answer and len(answer) > 30:
                            qa_pairs.append({
                                'id': f"{category.lower()}-q{len(qa_pairs)+1}",
                                'question': question,
                                'answer': answer,
                                'source': url,
                                'category': category
                            })
                            
                            logger.info(f"Alternative scraped Q{len(qa_pairs)}: {question[:60]}...")
                            
                    except Exception as e:
                        logger.error(f"Error processing h3 element: {e}")
                        continue
            
            # Method 3: Fallback for any remaining content
            if not qa_pairs:
                qa_pairs = self._fallback_scraping(soup, url, limit)
            
            logger.info(f"Total scraped from {category}: {len(qa_pairs)} Q&A pairs")
            return qa_pairs
            
        except Exception as e:
            logger.error(f"Error scraping InterviewBit {category}: {e}")
            return []
    
    def scrape_geeksforgeeks(self, topic: str = "angular", limit: int = 20) -> List[Dict]:
        """Scrape from GeeksforGeeks interview questions"""
        url = f"https://www.geeksforgeeks.org/{topic}-interview-questions/"
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            qa_pairs = []
            
            # Look for question-answer patterns
            questions = soup.find_all(['h2', 'h3', 'h4'], string=re.compile(r'\d+\.|\?|What|How|Why|Explain'))
            
            for i, q_elem in enumerate(questions[:limit]):
                try:
                    question = self._clean_text(q_elem.get_text())
                    if not question or len(question) < 10:
                        continue
                    
                    # Find following content as answer
                    answer_parts = []
                    current = q_elem.find_next_sibling()
                    
                    while current and len(answer_parts) < 3:
                        if current.name in ['h1', 'h2', 'h3', 'h4'] and i < len(questions) - 1:
                            break
                        if current.name in ['p', 'div', 'ul', 'ol']:
                            text = self._clean_text(current.get_text())
                            if text and len(text) > 20:
                                answer_parts.append(text)
                        current = current.find_next_sibling()
                    
                    answer = ' '.join(answer_parts)
                    
                    if answer and len(answer) > 50:
                        qa_pairs.append({
                            'id': f"gfg-{topic}-q{i+1}",
                            'question': question,
                            'answer': answer,
                            'source': url,
                            'category': topic.title()
                        })
                        
                        logger.info(f"Scraped GFG Q{i+1}: {question[:60]}...")
                        
                except Exception as e:
                    logger.error(f"Error processing GFG question {i}: {e}")
                    continue
            
            return qa_pairs
            
        except Exception as e:
            logger.error(f"Error scraping GeeksforGeeks: {e}")
            return []
    
    def scrape_javatpoint(self, topic: str = "angular", limit: int = 20) -> List[Dict]:
        """Scrape from JavaTpoint interview questions"""
        url = f"https://www.javatpoint.com/{topic}-interview-questions"
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            qa_pairs = []
            
            # Look for numbered questions
            questions = soup.find_all(['h2', 'h3', 'p'], string=re.compile(r'^\d+[\.)]\s*'))
            
            for i, q_elem in enumerate(questions[:limit]):
                try:
                    question = self._clean_text(q_elem.get_text())
                    if not question or len(question) < 10:
                        continue
                    
                    # Find answer in next elements
                    answer_parts = []
                    current = q_elem.find_next_sibling()
                    
                    while current and len(answer_parts) < 3:
                        if current.name in ['h1', 'h2', 'h3'] and re.search(r'^\d+[\.)]', current.get_text()):
                            break
                        if current.name in ['p', 'div', 'ul', 'ol']:
                            text = self._clean_text(current.get_text())
                            if text and len(text) > 20:
                                answer_parts.append(text)
                        current = current.find_next_sibling()
                    
                    answer = ' '.join(answer_parts)
                    
                    if answer and len(answer) > 50:
                        qa_pairs.append({
                            'id': f"jtp-{topic}-q{i+1}",
                            'question': question,
                            'answer': answer,
                            'source': url,
                            'category': topic.title()
                        })
                        
                        logger.info(f"Scraped JTP Q{i+1}: {question[:60]}...")
                        
                except Exception as e:
                    logger.error(f"Error processing JavaTpoint question {i}: {e}")
                    continue
            
            return qa_pairs
            
        except Exception as e:
            logger.error(f"Error scraping JavaTpoint: {e}")
            return []
    
    def _fallback_scraping(self, soup: BeautifulSoup, url: str, limit: int) -> List[Dict]:
        """Fallback method for scraping when primary method fails"""
        qa_pairs = []
        
        # Look for any h3 tags that might be questions
        h3_tags = soup.find_all('h3')
        
        for i, h3 in enumerate(h3_tags[:limit]):
            try:
                question = self._clean_text(h3.get_text())
                if not question or len(question) < 10:
                    continue
                
                # Look for following paragraphs as answer
                answer_parts = []
                current = h3.find_next_sibling()
                
                while current and len(answer_parts) < 2:
                    if current.name == 'h3':
                        break
                    if current.name in ['p', 'div']:
                        text = self._clean_text(current.get_text())
                        if text and len(text) > 30:
                            answer_parts.append(text)
                    current = current.find_next_sibling()
                
                answer = ' '.join(answer_parts)
                
                if answer and len(answer) > 50:
                    qa_pairs.append({
                        'id': f"fallback-q{i+1}",
                        'question': question,
                        'answer': answer,
                        'source': url,
                        'category': 'General'
                    })
                    
                    logger.info(f"Fallback scraped Q{i+1}: {question[:60]}...")
                    
            except Exception as e:
                logger.error(f"Error in fallback scraping {i}: {e}")
                continue
        
        return qa_pairs
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Remove unwanted characters
        text = re.sub(r'[^\w\s\.\?\!\,\(\)\-\:\;]', '', text)
        
        # Remove question numbers at start
        text = re.sub(r'^\d+[\.)]\s*', '', text)
        
        return text
    
    def scrape_custom_url(self, url: str, limit: int = 20) -> List[Dict]:
        """Scrape from a custom URL using intelligent detection"""
        try:
            # First, check if this is a known site and use specialized scraper
            if 'interviewbit.com' in url.lower():
                if 'angular' in url.lower():
                    logger.info("Detected InterviewBit Angular URL, using specialized scraper")
                    return self.scrape_interviewbit_angular(limit)
                elif 'javascript' in url.lower():
                    logger.info("Detected InterviewBit JavaScript URL, using specialized scraper")
                    return self.scrape_interviewbit_javascript(limit)
                else:
                    logger.info("Detected InterviewBit URL, using generic InterviewBit scraper")
                    # Extract topic from URL if possible
                    topic = 'general'
                    url_parts = url.lower().split('/')
                    for part in url_parts:
                        if 'interview-questions' in part:
                            topic = part.replace('-interview-questions', '')
                            break
                    return self._scrape_interviewbit_generic(url, topic.title(), limit)
                    
            elif 'geeksforgeeks.org' in url.lower():
                # Extract topic from URL if possible
                topic = 'javascript'  # Default
                if 'angular' in url.lower():
                    topic = 'angular'
                elif 'react' in url.lower():
                    topic = 'react'
                elif 'python' in url.lower():
                    topic = 'python'
                logger.info(f"Detected GeeksforGeeks URL, using specialized scraper for {topic}")
                return self.scrape_geeksforgeeks(topic, limit)
                
            elif 'javatpoint.com' in url.lower():
                # Extract topic from URL if possible
                topic = 'javascript'  # Default
                if 'angular' in url.lower():
                    topic = 'angular'
                elif 'react' in url.lower():
                    topic = 'react'
                elif 'python' in url.lower():
                    topic = 'python'
                logger.info(f"Detected JavaTpoint URL, using specialized scraper for {topic}")
                return self.scrape_javatpoint(topic, limit)
            
            # For unknown sites, use generic scraping
            logger.info(f"Unknown site, using generic scraping for: {url}")
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            qa_pairs = []
            
            # Try multiple strategies for detecting Q&A patterns
            
            # Strategy 1: Look for numbered questions (1., 2., Q1, Q2, etc.)
            numbered_questions = soup.find_all(['h1', 'h2', 'h3', 'h4', 'p'], 
                                             string=re.compile(r'(^\d+[\.)]\s*)|(^Q\d+)|(Question\s*\d+)', re.IGNORECASE))
            
            for i, q_elem in enumerate(numbered_questions[:limit]):
                try:
                    question = self._clean_text(q_elem.get_text())
                    if len(question) < 10:
                        continue
                    
                    # Find answer in following elements
                    answer_parts = []
                    current = q_elem.find_next_sibling()
                    count = 0
                    
                    while current and count < 5:
                        if current.name in ['h1', 'h2', 'h3', 'h4'] and \
                           re.search(r'(^\d+[\.)]\s*)|(^Q\d+)|(Question\s*\d+)', current.get_text(), re.IGNORECASE):
                            break
                        if current.name in ['p', 'div', 'ul', 'ol']:
                            text = self._clean_text(current.get_text())
                            if text and len(text) > 30:
                                answer_parts.append(text)
                        current = current.find_next_sibling()
                        count += 1
                    
                    answer = ' '.join(answer_parts[:3])
                    
                    if answer and len(answer) > 50:
                        qa_pairs.append({
                            'id': f"custom-{len(qa_pairs)+1}",
                            'question': question,
                            'answer': answer,
                            'source': url,
                            'category': 'Custom'
                        })
                        
                        logger.info(f"Custom scraped Q{len(qa_pairs)}: {question[:60]}...")
                        
                except Exception as e:
                    logger.error(f"Error processing custom question {i}: {e}")
                    continue
            
            # Strategy 2: Look for question words (What, How, Why, etc.)
            if not qa_pairs:
                question_words = soup.find_all(['h1', 'h2', 'h3', 'h4'], 
                                             string=re.compile(r'^(What|How|Why|When|Where|Which|Explain|Describe|Define)', re.IGNORECASE))
                
                for i, q_elem in enumerate(question_words[:limit]):
                    try:
                        question = self._clean_text(q_elem.get_text())
                        if len(question) < 10:
                            continue
                        
                        # Find answer in following elements
                        answer_parts = []
                        for sibling in q_elem.find_next_siblings():
                            if sibling.name in ['h1', 'h2', 'h3', 'h4']:
                                break
                            if sibling.name in ['p', 'div']:
                                text = self._clean_text(sibling.get_text())
                                if text and len(text) > 30:
                                    answer_parts.append(text)
                                if len(answer_parts) >= 2:
                                    break
                        
                        answer = ' '.join(answer_parts)
                        
                        if answer and len(answer) > 50:
                            qa_pairs.append({
                                'id': f"custom-{len(qa_pairs)+1}",
                                'question': question,
                                'answer': answer,
                                'source': url,
                                'category': 'Custom'
                            })
                            
                            logger.info(f"Custom scraped Q{len(qa_pairs)}: {question[:60]}...")
                            
                    except Exception as e:
                        logger.error(f"Error processing custom question {i}: {e}")
                        continue
            
            return qa_pairs
            
        except Exception as e:
            logger.error(f"Error scraping custom URL {url}: {e}")
            return []

    def discover_question_count(self, topic: str, source: str) -> int:
        """Discover how many questions are available from a source without full scraping"""
        try:
            logger.info(f"Discovering question count for {topic} from {source}")
            
            if source == 'interviewbit':
                return self._discover_interviewbit_count(topic)
            elif source == 'geeksforgeeks':
                return self._discover_geeksforgeeks_count(topic)
            elif source == 'javatpoint':
                return self._discover_javatpoint_count(topic)
            else:
                logger.warning(f"Unknown source: {source}")
                return 0
                
        except Exception as e:
            logger.error(f"Error discovering question count from {source}: {e}")
            return 0
    
    def _discover_interviewbit_count(self, topic: str) -> int:
        """Count questions on InterviewBit without full extraction"""
        if topic.lower() == 'angular':
            url = "https://www.interviewbit.com/angular-interview-questions/"
        elif topic.lower() == 'react':
            url = "https://www.interviewbit.com/react-interview-questions/"
        elif topic.lower() == 'javascript':
            url = "https://www.interviewbit.com/javascript-interview-questions/"
        else:
            url = f"https://www.interviewbit.com/{topic.lower()}-interview-questions/"
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Count h3 elements that likely contain questions
            question_headings = soup.find_all('h3')
            valid_questions = 0
            
            for h3 in question_headings:
                text = self._clean_text(h3.get_text())
                if text and len(text) > 10 and ('?' in text or 'what' in text.lower() or 'how' in text.lower() or 'explain' in text.lower()):
                    valid_questions += 1
            
            logger.info(f"InterviewBit {topic}: Found {valid_questions} questions")
            return valid_questions
            
        except Exception as e:
            logger.error(f"Error discovering InterviewBit count: {e}")
            return 0
    
    def _discover_geeksforgeeks_count(self, topic: str) -> int:
        """Count questions on GeeksforGeeks without full extraction"""
        search_terms = {
            'angular': ['angular', 'angularjs'],
            'react': ['react', 'reactjs'],
            'javascript': ['javascript', 'js'],
            'typescript': ['typescript'],
            'nodejs': ['nodejs', 'node.js'],
            'python': ['python']
        }
        
        terms = search_terms.get(topic.lower(), [topic.lower()])
        total_count = 0
        
        for term in terms:
            try:
                url = f"https://www.geeksforgeeks.org/{term}-interview-questions/"
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Count question-like elements
                question_elements = soup.find_all(['h2', 'h3', 'h4'])
                valid_questions = 0
                
                for elem in question_elements:
                    text = self._clean_text(elem.get_text())
                    if text and len(text) > 10 and ('?' in text or 'Q.' in text or text.lower().startswith(('what', 'how', 'explain', 'describe'))):
                        valid_questions += 1
                
                total_count += valid_questions
                logger.info(f"GeeksforGeeks {term}: Found {valid_questions} questions")
                
            except Exception as e:
                logger.error(f"Error discovering GeeksforGeeks count for {term}: {e}")
        
        return total_count
    
    def _discover_javatpoint_count(self, topic: str) -> int:
        """Count questions on JavaTpoint without full extraction"""
        topic_urls = {
            'angular': 'https://www.javatpoint.com/angular-interview-questions',
            'react': 'https://www.javatpoint.com/react-interview-questions',
            'javascript': 'https://www.javatpoint.com/javascript-interview-questions',
            'nodejs': 'https://www.javatpoint.com/node-js-interview-questions',
            'python': 'https://www.javatpoint.com/python-interview-questions'
        }
        
        url = topic_urls.get(topic.lower())
        if not url:
            url = f"https://www.javatpoint.com/{topic.lower()}-interview-questions"
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Count numbered questions (1), 2), etc.)
            question_patterns = [
                r'^\d+\)',  # 1), 2), etc.
                r'^Q\.\d+',  # Q.1, Q.2, etc.
                r'^\d+\.',   # 1., 2., etc.
            ]
            
            valid_questions = 0
            text_content = soup.get_text()
            
            for pattern in question_patterns:
                matches = re.findall(pattern, text_content, re.MULTILINE)
                valid_questions += len(matches)
            
            # Alternative: count elements with question-like content
            if valid_questions == 0:
                question_elements = soup.find_all(['h2', 'h3', 'h4', 'p'])
                for elem in question_elements:
                    text = self._clean_text(elem.get_text())
                    if text and ('?' in text or text.lower().startswith(('what', 'how', 'explain', 'describe'))):
                        valid_questions += 1
            
            logger.info(f"JavaTpoint {topic}: Found {valid_questions} questions")
            return valid_questions
            
        except Exception as e:
            logger.error(f"Error discovering JavaTpoint count: {e}")
            return 0

    def scrape_multiple_sources(self, topic: str = "angular", limit_per_source: int = 10) -> List[Dict]:
        """Scrape from multiple sources"""
        all_qa_pairs = []
        
        logger.info(f"Starting to scrape {topic} questions from multiple sources...")
        
        # InterviewBit
        if topic.lower() == "angular":
            qa_pairs = self.scrape_interviewbit_angular(limit_per_source)
            all_qa_pairs.extend(qa_pairs)
            time.sleep(2)  # Rate limiting
        elif topic.lower() == "javascript":
            qa_pairs = self.scrape_interviewbit_javascript(limit_per_source)
            all_qa_pairs.extend(qa_pairs)
            time.sleep(2)  # Rate limiting
        
        # GeeksforGeeks
        qa_pairs = self.scrape_geeksforgeeks(topic, limit_per_source)
        all_qa_pairs.extend(qa_pairs)
        time.sleep(2)
        
        # JavaTpoint
        qa_pairs = self.scrape_javatpoint(topic, limit_per_source)
        all_qa_pairs.extend(qa_pairs)
        
        logger.info(f"Total scraped: {len(all_qa_pairs)} Q&A pairs")
        return all_qa_pairs