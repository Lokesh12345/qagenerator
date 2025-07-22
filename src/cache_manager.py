"""
Intelligent caching system for OpenAI and Claude API calls
Reduces costs by avoiding duplicate API calls for similar questions
"""
import os
import json
import hashlib
import time
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class AICache:
    def __init__(self, cache_dir: str = "cache", max_age_hours: int = 24):
        self.cache_dir = cache_dir
        self.max_age = timedelta(hours=max_age_hours)
        
        # Create cache directory
        os.makedirs(cache_dir, exist_ok=True)
        
        # Cache files for different providers
        self.openai_cache_file = os.path.join(cache_dir, "openai_cache.json")
        self.claude_cache_file = os.path.join(cache_dir, "claude_cache.json")
        
        # Load existing caches
        self.openai_cache = self._load_cache(self.openai_cache_file)
        self.claude_cache = self._load_cache(self.claude_cache_file)
        
        # Statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "cost_saved": 0.0
        }
        
        logger.info(f"Cache initialized: OpenAI={len(self.openai_cache)}, Claude={len(self.claude_cache)} entries")
    
    def _load_cache(self, cache_file: str) -> Dict:
        """Load cache from file"""
        try:
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    cache = json.load(f)
                # Clean expired entries
                cleaned_cache = self._clean_expired_entries(cache)
                logger.info(f"Loaded {len(cleaned_cache)} valid cache entries from {cache_file}")
                return cleaned_cache
        except Exception as e:
            logger.error(f"Error loading cache {cache_file}: {e}")
        return {}
    
    def _clean_expired_entries(self, cache: Dict) -> Dict:
        """Remove expired cache entries"""
        now = datetime.now()
        cleaned = {}
        
        for key, entry in cache.items():
            try:
                cached_time = datetime.fromisoformat(entry['timestamp'])
                if now - cached_time < self.max_age:
                    cleaned[key] = entry
                else:
                    logger.debug(f"Expired cache entry removed: {key[:20]}...")
            except Exception as e:
                logger.warning(f"Invalid cache entry removed: {e}")
        
        return cleaned
    
    def _save_cache(self, cache: Dict, cache_file: str):
        """Save cache to file"""
        try:
            with open(cache_file, 'w') as f:
                json.dump(cache, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving cache {cache_file}: {e}")
    
    def _generate_cache_key(self, question: str, provider: str, model: str) -> str:
        """Generate cache key for question"""
        # Normalize question for better cache hits
        normalized_question = self._normalize_question(question)
        
        # Create hash from question + provider + model
        content = f"{normalized_question}:{provider}:{model}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _normalize_question(self, question: str) -> str:
        """Normalize question for better cache matching"""
        # Remove extra whitespace and normalize case
        normalized = question.strip().lower()
        
        # Remove common punctuation variations
        normalized = normalized.rstrip('?!.')
        
        # Handle common question variations
        variations = {
            "what is": "what is",
            "what are": "what are", 
            "how does": "how does",
            "how do": "how do",
            "explain": "explain",
            "describe": "explain",
            "tell me about": "explain"
        }
        
        for variant, standard in variations.items():
            if normalized.startswith(variant):
                normalized = normalized.replace(variant, standard, 1)
                break
        
        return normalized
    
    def _calculate_similarity(self, question1: str, question2: str) -> float:
        """Calculate similarity between two questions"""
        norm1 = self._normalize_question(question1)
        norm2 = self._normalize_question(question2)
        
        # Simple word overlap similarity
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
    
    def _find_similar_cached_question(self, question: str, cache: Dict, threshold: float = 0.8) -> Optional[str]:
        """Find similar cached question above threshold"""
        best_match = None
        best_similarity = 0.0
        
        for cache_key, entry in cache.items():
            cached_question = entry.get('original_question', '')
            similarity = self._calculate_similarity(question, cached_question)
            
            if similarity > threshold and similarity > best_similarity:
                best_similarity = similarity
                best_match = cache_key
        
        if best_match:
            logger.info(f"Found similar cached question (similarity: {best_similarity:.2f})")
        
        return best_match
    
    def get_cached_response(self, question: str, provider: str, model: str) -> Optional[Dict[str, Any]]:
        """Get cached response if available"""
        cache_key = self._generate_cache_key(question, provider, model)
        
        # Select appropriate cache
        cache = self.openai_cache if provider == "openai" else self.claude_cache
        
        # Check exact match first
        if cache_key in cache:
            self.stats["hits"] += 1
            estimated_cost = self._estimate_cost(question, provider)
            self.stats["cost_saved"] += estimated_cost
            logger.info(f"✅ Cache HIT (exact): {question[:50]}... (saved ~${estimated_cost:.4f})")
            return cache[cache_key]['response']
        
        # Check for similar questions
        similar_key = self._find_similar_cached_question(question, cache)
        if similar_key:
            self.stats["hits"] += 1
            estimated_cost = self._estimate_cost(question, provider)
            self.stats["cost_saved"] += estimated_cost
            logger.info(f"✅ Cache HIT (similar): {question[:50]}... (saved ~${estimated_cost:.4f})")
            return cache[similar_key]['response']
        
        # No cache hit
        self.stats["misses"] += 1
        logger.info(f"❌ Cache MISS: {question[:50]}...")
        return None
    
    def store_response(self, question: str, provider: str, model: str, response: Dict[str, Any], tokens_used: int = 0):
        """Store response in cache"""
        cache_key = self._generate_cache_key(question, provider, model)
        
        cache_entry = {
            'original_question': question,
            'provider': provider,
            'model': model,
            'response': response,
            'timestamp': datetime.now().isoformat(),
            'tokens_used': tokens_used
        }
        
        # Store in appropriate cache
        if provider == "openai":
            self.openai_cache[cache_key] = cache_entry
            self._save_cache(self.openai_cache, self.openai_cache_file)
        else:
            self.claude_cache[cache_key] = cache_entry
            self._save_cache(self.claude_cache, self.claude_cache_file)
        
        logger.info(f"💾 Cached response: {question[:50]}...")
    
    def _estimate_cost(self, question: str, provider: str) -> float:
        """Estimate API cost for the question"""
        # Rough token estimation (4 chars = 1 token)
        input_tokens = len(question) // 4 + 500  # +500 for prompt template
        output_tokens = 1000  # Estimated output for our JSON structure
        
        if provider == "openai":
            # GPT-4o-mini pricing (as of 2024)
            input_cost = (input_tokens / 1000) * 0.00015  # $0.15 per 1K input tokens
            output_cost = (output_tokens / 1000) * 0.0006  # $0.60 per 1K output tokens
            return input_cost + output_cost
        else:  # Claude
            # Claude-3.5-haiku pricing (as of 2024)
            input_cost = (input_tokens / 1000) * 0.00025  # $0.25 per 1K input tokens
            output_cost = (output_tokens / 1000) * 0.00125  # $1.25 per 1K output tokens
            return input_cost + output_cost
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "total_requests": total_requests,
            "cache_hits": self.stats["hits"],
            "cache_misses": self.stats["misses"],
            "hit_rate_percent": round(hit_rate, 2),
            "estimated_cost_saved": round(self.stats["cost_saved"], 4),
            "openai_cache_size": len(self.openai_cache),
            "claude_cache_size": len(self.claude_cache)
        }
    
    def clear_cache(self, provider: str = None):
        """Clear cache for specific provider or all"""
        if provider == "openai" or provider is None:
            self.openai_cache = {}
            self._save_cache(self.openai_cache, self.openai_cache_file)
        
        if provider == "claude" or provider is None:
            self.claude_cache = {}
            self._save_cache(self.claude_cache, self.claude_cache_file)
        
        logger.info(f"Cache cleared for: {provider or 'all providers'}")
    
    def optimize_cache(self):
        """Remove least recently used entries if cache gets too large"""
        max_entries = 1000  # Maximum entries per provider
        
        for cache, cache_file in [(self.openai_cache, self.openai_cache_file), 
                                  (self.claude_cache, self.claude_cache_file)]:
            if len(cache) > max_entries:
                # Sort by timestamp and keep most recent
                sorted_entries = sorted(
                    cache.items(), 
                    key=lambda x: x[1]['timestamp'], 
                    reverse=True
                )
                
                # Keep only the most recent entries
                cache.clear()
                for key, value in sorted_entries[:max_entries]:
                    cache[key] = value
                
                self._save_cache(cache, cache_file)
                logger.info(f"Cache optimized: kept {max_entries} most recent entries")

# Global cache instance
_cache_instance = None

def get_cache() -> AICache:
    """Get global cache instance"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = AICache()
    return _cache_instance