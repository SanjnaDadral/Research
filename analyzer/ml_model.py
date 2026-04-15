import re
import logging
import os
from typing import Dict, List, Any
from collections import Counter

logger = logging.getLogger(__name__)

# ====================== Lazy NLTK Setup ======================
_nltk_available = None
_word_tokenize = None
_stopwords = None


def _load_nltk():
    """Lazy load NLTK only when actually needed - prevents OOM during gunicorn boot"""
    global _nltk_available, _word_tokenize, _stopwords

    if _nltk_available is not None:
        return _nltk_available

    try:
        import nltk
        # Download required data quietly
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt', quiet=True, halt_on_error=False)

        try:
            nltk.data.find('corpora/stopwords')
        except LookupError:
            nltk.download('stopwords', quiet=True, halt_on_error=False)

        from nltk.tokenize import word_tokenize
        from nltk.corpus import stopwords

        _word_tokenize = word_tokenize
        _stopwords = set(stopwords.words('english'))
        _nltk_available = True
        logger.info("✓ NLTK loaded successfully (lazy loading)")

    except Exception as e:
        logger.warning(f"NLTK loading failed: {e}. Using regex fallback.")
        _nltk_available = False
        _word_tokenize = None
        _stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
                      'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did'}

    return _nltk_available


# ====================== sklearn Setup ======================
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError as e:
    logger.warning(f"sklearn not available: {e}")
    SKLEARN_AVAILABLE = False
    TfidfVectorizer = None
    np = None


class MLProcessor:
    def __init__(self):
        self._models_loaded = False
        self._stop_words = None

    def _load_models(self):
        if self._models_loaded:
            return
        self._models_loaded = True
        _load_nltk()  # Lazy load only when needed
        logger.info("✓ MLProcessor initialized with lazy NLTK + TF-IDF")

    def _get_stop_words(self):
        if self._stop_words is None:
            if _load_nltk() and _stopwords is not None:
                self._stop_words = _stopwords.copy()
            else:
                self._stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
                                    'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had'}
        return self._stop_words

    # ====================== Your Original Methods (Unchanged) ======================

    def extract_authors(self, text: str) -> List[str]:
        """Extract author names from text."""
        authors = set()
        first_15k = text[:15000]
       
        patterns = [
            r'(?:author|authors|by)[:\s]+([^\n]+)',
        ]
       
        for pat in patterns:
            matches = re.findall(pat, first_15k, re.IGNORECASE)
            for m in matches:
                name_parts = re.split(r'[,;]|\s+and\s+|\s+&\s+', m)
                for name in name_parts:
                    name = name.strip()
                    if self._is_valid_name(name):
                        authors.add(name)
       
        title_area = text[:5000]
        lines = title_area.split('\n')
        for line in lines[:10]:
            line = line.strip()
            if len(line) > 80 or len(line) < 5:
                continue
            skip_words = ['abstract', 'introduction', 'background', 'keywords', 'doi', 'http', 'email', 'university', 'department', 'school', 'institute', 'received', 'revised', 'accepted', 'published']
            if any(skip in line.lower() for skip in skip_words):
                continue
            name_matches = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b', line)
            for name in name_matches:
                if self._is_valid_name(name) and len(name) > 4:
                    authors.add(name)
       
        false_positives = {
            'Abstract', 'Introduction', 'References', 'Conclusion', 'Figure', 'Table',
            'Email', 'https', 'http', 'University', 'Department', 'School', 'Institute',
            'Received', 'Revised', 'Accepted', 'Published', 'Copyright', 'Journal',
            'Volume', 'Issue', 'Pages', 'doi', 'DOI', 'Academic', 'Editor', 'Editors',
            'Keywords', 'Background', 'Methodology', 'Results', 'Discussion'
        }
        authors = {a for a in authors if a not in false_positives and len(a) > 3 and len(a) < 60}
       
        final_authors = []
        for a in authors:
            if re.match(r'^[A-Za-z\s\.\-]+$', a) and not any(c.isdigit() for c in a):
                final_authors.append(a)
       
        return sorted(final_authors)[:10]

    def _is_valid_name(self, name: str) -> bool:
        """Check if text looks like a person name."""
        name = name.strip()
        if not name or len(name) < 4 or len(name) > 40:
            return False
        if not re.match(r'^[A-Za-z\s\.\-]+$', name):
            return False
        parts = name.split()
        if len(parts) < 2:
            return False
        for p in parts:
            if not (p[0].isupper() or (len(p) == 2 and p[1] == '.')):
                return False
        return True

    def extract_publication_year(self, text: str) -> str:
        """Extract publication year with improved patterns."""
        patterns = [
            r'(?:published|accepted|presented|submitted|revised)[\s:]+(?:in\s+)?(\d{4})',
            r'(?:published|published online)[\s:]+(?:[\w\s]+)?(\d{4})',
            r'©\s*(\d{4})',
            r'Copyright\s+(\d{4})',
            r'©\s*20\d{2}',
            r'arXiv:\d+\.\d+\s+\[.*?\]\s+(\d{4})',
            r'arXiv:\d+\.\d+\s+\((\d{4})\)',
            r'doi:10\.\d+/.+?(\d{4})',
            r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+(\d{4})',
            r'(\d{1,2})\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
            r'(?:received|revised)[\s:]+(?:[\w\s]+)?(\d{4})',
            r'\[\d{4}\]|\(\d{4}\)|(?:19|20)\d{2}',
        ]
       
        best_year = None
       
        for pat in patterns:
            matches = re.findall(pat, text[:20000], re.IGNORECASE)
            if matches:
                for match in matches:
                    if isinstance(match, tuple):
                        for m in match:
                            if m and m.isdigit() and len(m) == 4:
                                year = int(m)
                                if 1990 <= year <= 2030:
                                    if best_year is None or year > best_year:
                                        best_year = year
                    elif match.isdigit() and len(match) == 4:
                        year = int(match)
                        if 1990 <= year <= 2030:
                            if best_year is None or year > best_year:
                                best_year = year
       
        return str(best_year) if best_year else ""

    def extract_abstract(self, text: str) -> str:
        """Extract abstract section - improved detection with fallback."""
        labeled = self._extract_labeled_abstract(text)
        if labeled and len(labeled) > 100:
            return labeled
       
        first_8k = text[:8000]
        paragraphs = re.split(r'\n\s*\n', first_8k)
       
        for i, para in enumerate(paragraphs):
            para = para.strip()
            para_lower = para.lower()
           
            if len(para) > 150 and len(para) < 3000:
                if not re.search(r'^(introduction|background|related work|methodology|experiments|results|discussion)', para_lower):
                    if not para_lower.startswith(('1.', '2.', '3.', 'figure', 'table', 'http', '-', '*')):
                        return para[:3000]
       
        sentences = re.split(r'(?<=[.!?])\s+', first_8k)
        abstract_candidates = []
        for sent in sentences:
            sent = sent.strip()
            if 40 < len(sent) < 400:
                if not re.search(r'(?i)(introduction|background|methodology|results|conclusion|reference)', sent):
                    abstract_candidates.append(sent)
       
        if len(abstract_candidates) >= 2:
            return ' '.join(abstract_candidates[:5])[:3000]
       
        return self._infer_abstract(text)

    def _infer_abstract(self, text: str) -> str:
        """Generate an abstract-like summary from paper content when none exists."""
        text_sample = text[:15000]
        title = self.extract_title(text_sample)
        goal = self.extract_goal(text_sample)
        keywords = self.extract_keywords(text_sample, top_n=8)
        methodology = self.detect_methodology(text_sample)
       
        intro_paragraphs = []
        lines = text_sample.split('\n\n')
        found_intro = False
       
        for para in lines:
            para_lower = para.lower().strip()
            if 'introduction' in para_lower and len(para_lower) < 50:
                found_intro = True
                continue
            if found_intro and len(para) > 100 and len(para) < 1500:
                if not para_lower.startswith(('1.', '2.', 'figure', 'table', 'http')):
                    intro_paragraphs.append(para.strip())
                    if len(intro_paragraphs) >= 2:
                        break
       
        if intro_paragraphs:
            abstract = ' '.join(intro_paragraphs[:2])
            if len(abstract) > 100:
                return abstract[:3000]
       
        abstract_parts = []
        if title:
            abstract_parts.append(f"This paper presents research on {title[:100]}.")
        if goal:
            abstract_parts.append(f"The primary goal of this study is to {goal[:150]}.")
        if methodology:
            methods = ', '.join(methodology[:4])
            abstract_parts.append(f"The approach employs {methods} methodologies to address the research objectives.")
        if keywords:
            kw_str = ', '.join(keywords[:6])
            abstract_parts.append(f"Key topics include {kw_str}.")
       
        text_lower = text_sample.lower()
        if any(w in text_lower for w in ['problem', 'challenge', 'issue']):
            abstract_parts.append("This research addresses significant challenges in the domain.")
        if any(w in text_lower for w in ['propose', 'present', 'introduce', 'develop']):
            abstract_parts.append("The proposed methods aim to advance current understanding and capabilities.")
        if any(w in text_lower for w in ['result', 'finding', 'show', 'demonstrate']):
            abstract_parts.append("The findings contribute valuable insights to the field.")
       
        return ' '.join(abstract_parts) if abstract_parts else ""

    def _extract_labeled_abstract(self, text: str) -> str:
        patterns = [
            r'(?i)(?:^|\n)\s*abstract\s*[:.-]*\s*\n+([\s\S]{100,4000}?)(?=\n\s*\n|\n\s*(?:keywords?|1\.|introduction))',
            r'(?i)(?:^|\n)\s*abstract\s*\n-+\n([\s\S]{100,4000}?)(?=\n\s*\n)',
            r'(?i)<abstract>([\s\S]{100,4000}?)</abstract>',
            r'(?i)(?:^|\n)\s*summary\s*[:.-]*\s*\n+([\s\S]{100,4000}?)(?=\n\s*\n|\n\s*(?:keywords?|1\.|introduction))',
            r'(?i)^abstract[:.\s]+([\s\S]{100,4000}?)(?=\n\s*(?:introduction|keywords|1\.)|\n\n|$)',
            r'(?i)^\s*abstract[:.\s]+([\s\S]{50,3000})(?:(?=\n\s*\n)|(?=\n\s*(?:introduction|keywords|1\.))|$)',
        ]
       
        for pat in patterns:
            m = re.search(pat, text, re.DOTALL)
            if m:
                abstract = m.group(1).strip()
                abstract = re.sub(r'\s+', ' ', abstract)
                if 100 < len(abstract) < 4000:
                    return abstract
        return ""

    def extract_conclusion(self, text: str) -> str:
        """Extract conclusion section - improved detection."""
        text_lower = text.lower()
       
        patterns = [
            r'(?i)(?:^|\n)\s*(?:conclusion|conclusions?|final remarks|summary and conclusions?)\s*[:.-]*\s*\n+([\s\S]{100,5000}?)(?=\n\s*\n|\n\s*(?:references|bibliography|acknowledgments?|appendix))',
            r'(?i)(?:^|\n)\s*conclusion\s*\n-+\n([\s\S]{100,5000}?)(?=\n\s*\n)',
            r'(?i)(?:^|\n)\s*(?:conclusion|conclusions?)\s*\n([\s\S]{100,4000}?)(?=\n\s*(?:references|bibliography))',
            r'(?i)(?:^|\n)\s*(?:5\.|V\.|5\s)\s*(?:conclusion|conclusions?)\s*\n([\s\S]{100,5000}?)(?=\n\s*\n)',
            r'(?i)(?:^|\n)\s*(?:conclusion)\s*[:.\-]*\n([\s\S]{80,3000})',
        ]
       
        for pat in patterns:
            m = re.search(pat, text, re.DOTALL)
            if m:
                conclusion = m.group(1).strip()
                conclusion = re.sub(r'\s+', ' ', conclusion)
                if 80 < len(conclusion) < 5000:
                    return conclusion[:4000]
       
        sections = re.split(r'\n\s*\n', text)
        for i in range(len(sections)-1, max(0, len(sections)-8), -1):
            section = sections[i].strip()
            section_lower = section.lower()
            if 'conclusion' in section_lower or '5' in section_lower[:20]:
                if len(section) > 80 and len(section) < 5000:
                    cleaned = re.sub(r'^(conclusion|conclusions?)\s*[:.\-]*\s*', '', section, flags=re.IGNORECASE)
                    if len(cleaned) > 50:
                        return cleaned[:4000]
       
        last_para = text.split('\n\n')[-1]
        if last_para:
            last_para = last_para.strip()
            if len(last_para) > 50 and len(last_para) < 2000:
                if re.search(r'(?i)(conclude|future work|final|summary)', last_para):
                    return last_para
       
        return ""

    def extract_native_summary(self, text: str) -> str:
        patterns = [
            r'(?i)(?:^|\n)\s*(?:summary|executive summary)\s*[:.-]*\s*\n+([\s\S]{200,4000}?)(?=\n\s*\n|\n(?=[A-Z]))',
            r'(?i)(?:^|\n)\s*summary\s*\n-+\n([\s\S]{200,4000}?)(?=\n\s*\n)',
        ]
       
        for pat in patterns:
            m = re.search(pat, text, re.DOTALL)
            if m:
                summary = m.group(1).strip()
                summary = re.sub(r'\s+', ' ', summary)
                if len(summary) > 100:
                    return summary[:3500]
       
        return self.extract_conclusion(text)

    def _extract_keyword_section(self, text: str) -> List[str]:
        patterns = [
            r'(?i)(?:keywords?|key ?terms?|index ?terms?)\s*[:.-]*\s*\n+([^\n]+(?:\n[^\n]+)*?)(?=\n\s*\n|\n\s*(?:1\.|introduction|abstract))',
            r'(?i)(?:CCS\s+CONCEPTS?\s*:\s*)([^\n]+)',
        ]
       
        for pat in patterns:
            m = re.search(pat, text, re.DOTALL)
            if m:
                keyword_text = m.group(1).strip()
                keywords = re.split(r'[,;•·\n]', keyword_text)
                cleaned = []
                for kw in keywords:
                    kw = kw.strip().lower()
                    kw = re.sub(r'^\d+\.\s*', '', kw)
                    kw = re.sub(r'^\*\s*', '', kw)
                    if 2 < len(kw) < 50 and not kw.startswith('http'):
                        cleaned.append(kw.title())
                if cleaned:
                    return cleaned
        return []

    def extract_keywords(self, text: str, top_n: int = 15) -> List[str]:
        self._load_models()
        keyword_section = self._extract_keyword_section(text)
        if keyword_section:
            return keyword_section[:top_n]
        return self._tfidf_keyword_extraction(text, top_n)

    def _tfidf_keyword_extraction(self, text: str, top_n: int = 15) -> List[str]:
        if not text or len(text) < 100:
            return self._basic_keyword_extraction(text, top_n)
       
        text_sample = text[:30000]
       
        if SKLEARN_AVAILABLE and TfidfVectorizer is not None:
            try:
                sentences = re.split(r'(?<=[.!?])\s+', text_sample)
                sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
               
                if len(sentences) < 3:
                    sentences = text_sample.split('\n')
               
                sentences = [s for s in sentences if len(s) > 20]
                if not sentences:
                    return self._basic_keyword_extraction(text, top_n)
               
                vectorizer = TfidfVectorizer(
                    max_features=100,
                    stop_words='english',
                    ngram_range=(1, 2),
                    min_df=1,
                    max_df=0.8
                )
               
                matrix = vectorizer.fit_transform(sentences)
                if np is not None:
                    scores = matrix.sum(axis=0).A1
                    terms = vectorizer.get_feature_names_out()
                    top_indices = np.argsort(scores)[-top_n * 2:][::-1]
                    keywords = [terms[i] for i in top_indices if scores[i] > 0]
                    if keywords:
                        return keywords[:top_n]
            except Exception as e:
                logger.warning(f"TF-IDF extraction failed: {e}")
       
        return self._basic_keyword_extraction(text, top_n)

    def _basic_keyword_extraction(self, text: str, top_n: int = 15) -> List[str]:
        if len(text) > 15000:
            text = text[:15000]
       
        stop_words = self._get_stop_words()
       
        if _load_nltk() and _word_tokenize is not None:
            try:
                words = _word_tokenize(text.lower())
            except:
                words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
        else:
            words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
       
        filtered_words = [w for w in words if w not in stop_words]
        word_freq = Counter(filtered_words)
       
        return [word.title() for word, count in word_freq.most_common(top_n)]

    def detect_methodology(self, text: str) -> List[str]:
        method_section = self._extract_methodology_section(text)
        if not method_section:
            method_section = text[:20000]
       
        method_keywords = {
            'Experimental': ['experiment', 'experimental setup', 'case study', 'benchmark', 'evaluation metrics', 'performance evaluation', 'we collected', 'we used', 'data were collected', 'samples were'],
            'Statistical Analysis': ['statistical analysis', 'hypothesis test', 'anova', 'regression analysis', 'p-value', 'bayesian', 'correlation', 'chi-square', 'multivariate', 'statistically significant'],
            'Machine Learning': ['machine learning', 'supervised', 'unsupervised', 'random forest', 'svm', 'support vector machine', 'decision tree', 'knn', 'k-nearest', 'xgboost', 'logistic regression', 'naive bayes', 'gradient boosting', 'classification', 'regression model'],
            'Deep Learning': ['deep learning', 'neural network', 'neural networks', 'cnn', 'rnn', 'lstm', 'gru', 'transformer', 'attention mechanism', 'gan', 'autoencoder', 'encoder-decoder', 'bert', 'gpt', 'convolutional'],
            'NLP': ['nlp', 'natural language processing', 'language model', 'text classification', 'ner', 'named entity recognition', 'sentiment analysis', 'text mining', 'word embedding', 'tokenization', 'corpus', 'corpora'],
            'Computer Vision': ['computer vision', 'object detection', 'image segmentation', 'resnet', 'yolo', 'opencv', 'image classification', 'feature extraction', 'image processing', 'image analysis'],
            'Reinforcement Learning': ['reinforcement learning', 'rl', 'q-learning', 'policy gradient', 'dqn', 'actor-critic', 'reward function', 'agent', 'environment'],
            'Data Mining': ['data mining', 'association rule', 'clustering', 'k-means', 'hierarchical clustering', 'outlier detection', 'data preprocessing'],
            'Survey': ['survey', 'literature review', 'systematic review', 'meta-analysis', 'qualitative analysis', 'questionnaire', 'interview'],
            'Epidemiological': ['epidemiological', 'cohort study', 'case-control', 'cross-sectional', 'longitudinal', 'population', 'health survey', 'exposure assessment'],
            'Chemical Analysis': ['chemical analysis', 'chromatography', 'spectroscopy', 'mass spectrometry', 'gc-ms', 'hplc', 'ppm', 'µg/m³', 'pm2.5', 'pm10'],
            'Geospatial Analysis': ['gis', 'geographic information system', 'spatial analysis', 'geospatial', 'remote sensing', 'satellite'],
            'Time Series Analysis': ['time series', 'arima', 'forecasting', 'temporal', 'seasonal', 'trend analysis'],
        }
       
        detected = []
        text_lower = method_section.lower()
       
        for method, kw_list in method_keywords.items():
            matches = sum(1 for kw in kw_list if kw in text_lower)
            if matches >= 1:
                detected.append(method)
       
        if not detected:
            detected.append('Research Study')
       
        return detected[:8]

    def _extract_methodology_section(self, text: str) -> str:
        section_match = re.search(
            r'(?i)(?:^|\n)(?:methodology|methods|approach|experimental setup|proposed method|materials?)\s*[:.-]*\s*\n+([\s\S]{500,8000}?)(?=\n\s*(?:results?|experiments?|evaluation|conclusion|discussion))',
            text, re.DOTALL
        )
        if section_match:
            return section_match.group(1)
        return text[:20000]

    def detect_technologies(self, text: str) -> List[str]:
        main_text = re.split(r'(?i)(?:references|bibliography)', text)[0][:40000]
       
        tech_keywords = {
            'Python': ['python', 'pytorch', 'tensorflow', 'keras', 'scikit-learn', 'sklearn', 'pandas', 'numpy', 'scipy', 'matplotlib', 'seaborn', 'opencv', 'pillow', 'nltk', 'spacy', 'gensim', 'networkx', 'plotly', 'torch'],
            'R': ['r language', 'rstudio', 'tidyverse', 'ggplot', 'caret', 'tidymodels', 'mlr', 'rstan', 'brms'],
            'JavaScript': ['javascript', 'node.js', 'react', 'vue', 'angular', 'typescript', 'next.js', 'nuxt', 'express', 'd3.js'],
            'Java': ['java', 'spring', 'maven', 'gradle', 'hibernate', 'junit', 'spark', 'hadoop'],
            'C++': ['c++', 'c programming', 'opencv', 'std::'],
            'MATLAB': ['matlab', 'simulink', 'octave'],
            'Go': ['golang', ' go '],
            'Rust': ['rust', 'cargo'],
            'Swift': ['swift', 'ios', 'xcode'],
            'Kotlin': ['kotlin', 'android'],
            'Cloud AWS': ['aws', 'amazon web services', 's3', 'ec2', 'lambda', 'dynamodb', 'rds'],
            'Cloud Azure': ['azure', 'microsoft azure', 'azure ml'],
            'Cloud GCP': ['google cloud', 'gcp', 'google cloud platform', 'bigquery', 'cloud run'],
            'Databases': ['mysql', 'postgresql', 'mongodb', 'redis', 'sqlite', 'oracle', 'sql server', 'cassandra', 'elasticsearch'],
            'MLOps': ['docker', 'kubernetes', 'kubeflow', 'mlflow', 'wandb', 'weights & biases', 'ray', 'apache spark', 'hadoop', 'airflow', 'dagshub'],
            'Web Frameworks': ['flask', 'django', 'fastapi', 'streamlit', 'gradio', 'express', 'rails', '.net', 'asp.net'],
            'APIs': ['rest api', 'restful', 'graphql', 'grpc', 'api', 'openapi', 'swagger'],
            'Deep Learning': ['deep learning', 'neural network', 'cnn', 'rnn', 'lstm', 'gru', 'transformer', 'bert', 'gpt', 'attention', 'encoder', 'decoder'],
            'NLP': ['nlp', 'natural language processing', 'text mining', 'sentiment analysis', 'ner', 'pos tagging', 'word embedding', 'bert', 'gpt'],
            'Computer Vision': ['computer vision', 'object detection', 'yolo', 'faster rcnn', 'semantic segmentation', 'instance segmentation', 'image classification'],
            'IoT': ['iot', 'internet of things', 'arduino', 'raspberry pi', 'esp32', 'sensor'],
            'Blockchain': ['blockchain', 'ethereum', 'bitcoin', 'solidity', 'web3', 'smart contract'],
            'DevOps': ['devops', 'ci/cd', 'jenkins', 'github actions', 'gitlab ci', 'terraform', 'ansible'],
            'Visualization': ['tableau', 'power bi', 'looker', 'plotly', 'd3', 'matplotlib', 'seaborn'],
        }
       
        detected = []
        text_lower = main_text.lower()
       
        for tech, kw_list in tech_keywords.items():
            for kw in kw_list:
                if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
                    detected.append(tech)
                    break
       
        return list(set(detected))[:15]

    def extract_title(self, text: str) -> str:
        if not text:
            return "Untitled"
       
        lines = text.split('\n')
        skip_patterns = ['http', 'doi:', 'email', 'phone', 'abstract', 'introduction', 'figure', 'table']
       
        for line in lines[:20]:
            line = line.strip()
            if not line or len(line) < 10:
                continue
            if any(pattern in line.lower() for pattern in skip_patterns):
                continue
            if line[0].isupper() and len(line) < 250:
                words = line.split()
                if len(words) >= 2:
                    return line
       
        return lines[0].strip() if lines else "Untitled"

    def extract_goal(self, text: str) -> str:
        patterns = [
            r'(?i)(?:goal|objective|aim|purpose)[:\s]+([^\n.]{20,500}\.?)',
            r'(?i)(?:this paper|this study|we) (?:aims?|proposes?|presents?|describes?|intend|focuses?|seek to|attempt to) (?:to )?([^\n.]{20,500}\.?)',
            r'(?i)(?:research question|hypothesis)[:\s]+([^\n.]{20,500}\.?)',
            r'(?i)(?:in this paper|this work|this research) (?:we )?(?:propose|present|develop|introduce|suggest) (?:a|an|the)?\s*([^\n.]{20,400}\.?)',
            r'(?i)(?:the goal|our goal|the aim|our aim) (?:of this|of our)? (?:paper|study|research)? (?:is|was)?\s*to\s+([^\n.]{20,400})',
        ]
       
        for pat in patterns:
            m = re.search(pat, text[:15000])
            if m:
                goal = m.group(1).strip()
                if 20 < len(goal) < 500:
                    goal = re.sub(r'^[\'"]|[\'"]$', '', goal)
                    goal = re.sub(r'^\s*[-–—]+\s*', '', goal)
                    if len(goal) > 20:
                        return goal
       
        sections = text.split('\n\n')
        for i, section in enumerate(sections):
            if re.search(r'(?i)introduction', section[:100]):
                if i + 1 < len(sections):
                    first_sent = re.split(r'[.!?]', sections[i+1])[0]
                    if len(first_sent) > 30:
                        return first_sent.strip()
       
        return ""

    def extract_impact(self, text: str) -> str:
        text_sample = text[:30000]
       
        patterns = [
            r'(?i)(?:contribution|impact|novelty|main result)s?[:\s]+([^\n.]{20,500}\.?)',
            r'(?i)(?:we (?:demonstrate|show)|our results (?:show|demonstrate)|the key contribution|our main finding|our findings (?:demonstrate|show))[:\s]*([^\n.]{20,500}\.?)',
            r'(?i)(?:this (?:paper|work) (?:makes|provides|offers|presents|introduces) (?:a|an|the) (?:novel|new|significant|substantial) (?:contribution|approach|method))([^\n.]{20,500}\.?)',
            r'(?i)(?:the (?:main|primary|key) contribution (?:of this paper|is|includes))[:\s]+([^\n.]{20,500})',
            r'(?i)(?:key contributions include)[:\s]+([^\n.]{20,500})',
            r'(?i)(?:outperform[sd]?|achieve[sd]?|reach(?:es|ed)?|obtain[sd]?) (?:state-of-the-art|a new|sota|new (?:record|best)|(?:an? )?(?:accuracy|performance|f1|score|precision|recall) (?:of|up to))[:\s]+([^\n.]{20,400})',
            r'(?i)(?:improved|enhanced|advances|breakthrough)[:\s]+(?:by |in |with )?([^\n.]{20,300})',
            r'(?i)(?:significantly|remarkably|substantially) (?:improve[ds]|enhance[sd]|outperform[sd])[:\s]+([^\n.]{20,300})',
            r'(?i)(?:experimental results (?:show|demonstrate|indicate)|our findings (?:show|demonstrate|indicate))[:\s]+([^\n.]{20,400})',
            r'(?i)(?:achieves? (?:an? )?(?:accuracy|performance|f1|score) (?:of|up to|over))[:\s]+([^\n.]{20,300})',
            r'(?i)(?:compared to (?:the )?(?:state-of-the-art|baseline|existing|previous|sota))[:\s]+([^\n.]{20,300})',
        ]
       
        for pat in patterns:
            m = re.search(pat, text_sample)
            if m:
                impact = m.group(1).strip()
                if 20 < len(impact) < 600:
                    impact = re.sub(r'^[\'"]|[\'"]$', '', impact)
                    impact = re.sub(r'^\s*[-–—]+\s*', '', impact)
                    impact = re.sub(r'\s+', ' ', impact)
                    if len(impact) > 30:
                        return impact[:500]
       
        conclusion_area = text_sample.lower()
        if 'conclusion' in conclusion_area or 'results' in conclusion_area:
            for section_start in ['conclusion', 'results and discussion', 'findings']:
                pos = conclusion_area.find(section_start)
                if pos >= 0:
                    section_text = text_sample[pos:pos+3000]
                    sentences = re.split(r'(?<=[.!?])\s+', section_text)
                    impact_keywords = ['improve', 'advance', 'enhance', 'outperform', 'achieve', 'significant', 'novel', 'breakthrough', 'state-of-the-art', 'sota', 'accuracy', 'performance', 'demonstrate', 'contribution', 'result', 'finding', 'effective', 'efficient']
                    impact_phrases = []
                    for sent in sentences:
                        sent_lower = sent.lower()
                        if any(kw in sent_lower for kw in impact_keywords):
                            if 30 < len(sent.strip()) < 400:
                                impact_phrases.append(sent.strip())
                    if impact_phrases:
                        return ' '.join(impact_phrases[:3])[:500]
       
        sentences = re.split(r'(?<=[.!?])\s+', text_sample[:20000])
        impact_keywords = ['improve', 'advance', 'enhance', 'outperform', 'achieve', 'significant', 'novel', 'breakthrough', 'state-of-the-art', 'sota', 'accuracy', 'performance', 'demonstrate', 'contribution', 'effective', 'efficient', 'first to', 'best', 'highest', 'lowest', 'reduce', 'increase']
       
        impact_phrases = []
        for sent in sentences:
            sent_lower = sent.lower()
            if any(kw in sent_lower for kw in impact_keywords):
                if 40 < len(sent.strip()) < 350:
                    impact_phrases.append(sent.strip())
       
        if impact_phrases:
            return ' '.join(impact_phrases[:2])[:450]
       
        return self._infer_impact(text)

    def _infer_impact(self, text: str) -> str:
        text_lower = text.lower()[:30000]
        keywords = self.extract_keywords(text, top_n=8)
        methodology = self.detect_methodology(text)
        title = self.extract_title(text)
       
        impacts = []
        if title:
            impacts.append(f"This research presents a novel approach in the field of {title[:50]}...")
        if keywords:
            kw_list = ', '.join(keywords[:5])
            impacts.append(f"Potential impact on advancing research in {kw_list} through innovative methodologies")
        if methodology:
            methods = ', '.join(methodology[:3])
            impacts.append(f"Development of {methods} techniques that could influence future research directions")
       
        if any(w in text_lower for w in ['pre-trained', 'pretrained', 'foundation', 'llm', 'gpt', 'bert', 'transformer']):
            impacts.append("Contribution to advancing pre-trained model capabilities and fine-tuning strategies")
       
        if not impacts:
            impacts.append("Contribution to advancing knowledge in the specified research domain")
       
        return ' '.join(impact[:2])[:450] if impacts else "Contribution to advancing knowledge in the specified research domain"

    def extract_methodology_summary(self, text: str) -> str:
        patterns = [
            r'(?i)(?:^|\n)\s*(?:methodology|methods|approach)\s*[:.-]*\s*\n+([\s\S]{100,2000}?)(?=\n\s*\n|\n(?=results|experiments|evaluation))',
            r'(?i)(?:^|\n)\s*methods\s*\n-+\n([\s\S]{100,2000}?)(?=\n\s*\n)',
        ]
       
        for pat in patterns:
            m = re.search(pat, text, re.DOTALL)
            if m:
                summary = m.group(1).strip()
                summary = re.sub(r'\s+', ' ', summary)
                if len(summary) > 50:
                    return summary[:2000]
        return ""

    def detect_research_gaps(self, text: str) -> List[str]:
        gaps = []
        patterns = [
            r'(?i)(?:research\s+)?gap[s]?\s*(?:in|of|found|identified)?\s*(?:in|is|are|remain)?\s*:?\s*([^\n.]{20,200})',
            r'(?i)(?:major\s+)?limitations?\s*(?:of|include|are|found|identified)?\s*:?\s*([^\n.]{20,200})',
            r'(?i)future\s+work\s*(?:include|recommend|suggest)?\s*:?\s*([^\n.]{20,200})',
            r'(?i)(?:we|this\s+paper)\s+(?:plan|intend|propose)\s+to\s+([^\n.]{20,150})',
            r'(?i)limitations?\s+(?:remain|still|include)\s+([^\n.]{20,150})',
            r'(?i)one\s+(?:limitation|challenge|drawback|issue)\s+(?:is|of)\s+([^\n.]{20,150})',
            r'(?i)despite\s+(?:our|this|the)\s+([^\n.]{20,150})',
            r'(?i)however\s*,?\s*(?:this|there|the|our|we)\s+([^\n.]{20,150})',
            r'(?i)although\s+(?:this|there|the|our|we)\s+([^\n.]{20,150})',
            r'(?i)challenge[s]?\s+(?:is|remain|include)\s+([^\n.]{20,150})',
            r'(?i)need[s]?\s+(?:more|further|additional)\s+([^\n.]{20,150})',
            r'(?i)should\s+be\s+(?:investigated|explored|addressed)\s+([^\n.]{20,150})',
            r'(?i)remains?\s+(?:an\s+)?(?:open|unsolved|unresolved)\s+([^\n.]{20,150})',
            r'(?i)not\s+yet\s+(?:explored|investigated|addressed|studied)\s+([^\n.]{20,150})',
            r'(?i)future\s+research\s+direction[s]?\s*:?\s*([^\n.]{20,200})',
            r'(?i)potential\s+(?:future\s+)?research\s+:?\s*([^\n.]{20,150})',
            r'(?i)opportunities?\s+for\s+further\s+([^\n.]{20,150})',
            r'(?i)more\s+work\s+is\s+needed\s+([^\n.]{20,150})',
            r'(?i)additional\s+research\s+is\s+required\s+([^\n.]{20,150})',
            r'(?i)leaves?\s+room\s+for\s+([^\n.]{20,150})',
            r'(?i)open\s+problem[s]?\s+:?\s*([^\n.]{20,200})',
            r'(?i)unaddressed\s+issue[s]?\s+:?\s*([^\n.]{20,150})',
            r'(?i)future\s+direction[s]?\s+:?\s*([^\n.]{20,200})',
        ]
       
        for pat in patterns:
            try:
                matches = re.findall(pat, text[:40000])
                for m in matches:
                    gap = m.strip()
                    gap = re.sub(r'^(by|through|with|and|or|to|for|in|on)\s+', '', gap, flags=re.IGNORECASE)
                    if len(gap) > 15 and len(gap) < 250:
                        gaps.append(gap)
            except:
                pass
       
        gaps = list(set(gaps))[:10]
        if not gaps:
            gaps = self._infer_research_gaps(text)
        return gaps[:8]

    def _infer_research_gaps(self, text: str) -> List[str]:
        inferred_gaps = []
        text_lower = text.lower()
        keywords = self.extract_keywords(text, top_n=10)
        methodology = self.detect_methodology(text)
       
        has_performance = any(w in text_lower for w in ['accuracy', 'performance', 'result', 'evaluation', 'benchmark', 'score', 'f1'])
        has_scalability = any(w in text_lower for w in ['scalability', 'large-scale', 'compute', 'resource'])
        has_realworld = any(w in text_lower for w in ['real-world', 'practical', 'application', 'deployment'])
       
        if not has_performance:
            inferred_gaps.append("Performance evaluation on benchmark datasets needs further investigation")
        if not has_scalability:
            inferred_gaps.append("Scalability to larger datasets or real-world applications remains unexplored")
        if not has_realworld:
            inferred_gaps.append("Deployment in real-world scenarios and practical applications needs validation")
       
        if keywords:
            keyword_str = ', '.join(keywords[:5])
            inferred_gaps.append(f"Application of {keyword_str} to new domains and problems")
       
        if len(inferred_gaps) < 3:
            additional_gaps = [
                "Cross-domain generalization and transfer learning potential",
                "Resource efficiency and computational cost optimization",
                "Integration with existing systems and frameworks"
            ]
            inferred_gaps.extend(additional_gaps[:3])
       
        return inferred_gaps[:6]

    def extract_datasets(self, text: str) -> Dict[str, Any]:
        text_sample = text[:60000]
        dataset_names = set()
        dataset_links = set()
        dataset_descriptions = []
       
        known_datasets = {'imagenet', 'coco', 'mnist', 'cifar', 'squad', 'glue', 'pubmed', 'arxiv', 'wikipedia'}
       
        for name in known_datasets:
            if re.search(r'\b' + re.escape(name) + r'\b', text_sample, re.IGNORECASE):
                dataset_names.add(name.title())
       
        name_patterns = [
            r'(?i)(?:dataset|data set|corpus|benchmark)[:\s]+["\']?([A-Z][A-Za-z0-9\-\s]{2,60}?)["\']?',
            r'(?i)(?:we use|we used|using|trained on|evaluated on|tested on)\s+(?:the\s+)?([A-Z][A-Za-z0-9\-\s]+(?:dataset|corpus|benchmark|data))',
        ]
       
        for pat in name_patterns:
            matches = re.findall(pat, text_sample)
            for m in matches:
                clean = str(m).strip()
                if 3 < len(clean) < 80:
                    dataset_names.add(clean)
       
        url_pattern = r'https?://[^\s<>"\'\)]+'
        all_urls = re.findall(url_pattern, text_sample)
        dataset_keywords = ['dataset', 'kaggle', 'zenodo', 'figshare', 'huggingface.co/datasets']
        for url in all_urls:
            if any(kw in url.lower() for kw in dataset_keywords):
                dataset_links.add(url.rstrip('.,;:'))
       
        return {
            'names': sorted(list(dataset_names))[:15],
            'links': sorted(list(dataset_links))[:15],
            'descriptions': dataset_descriptions[:5]
        }

    def extract_links(self, text: str) -> List[str]:
        url_pattern = r'https?://[^\s<>"\'\)\]]+'
        urls = re.findall(url_pattern, text)
        cleaned_urls = []
        seen = set()
       
        for url in urls:
            url = url.rstrip('.,;:)')
            if len(url) < 15 or url in seen:
                continue
            seen.add(url)
            if 'doi.org/10.' in url.lower():
                doi = url.replace('https://doi.org/', '').replace('http://doi.org/', '')
                cleaned_urls.append(f"DOI: {doi}")
            elif 'arxiv.org/abs' in url.lower():
                arxiv_id = url.replace('https://arxiv.org/abs/', '').replace('http://arxiv.org/abs/', '')
                cleaned_urls.append(f"arXiv: {arxiv_id}")
            elif 'github.com' in url.lower():
                gh_url = url.replace('https://github.com/', '').replace('http://github.com/', '').rstrip('/')
                cleaned_urls.append(f"GitHub: {gh_url}")
            else:
                cleaned_urls.append(url)
       
        return cleaned_urls[:50]

    def extract_references(self, text: str) -> List[str]:
        references = []
        ref_section = ""
       
        ref_patterns = [
            r'(?i)(?:^|\n)\s*(?:references|bibliography|literature\s+cited|works\s+cited)\s*[:.\-–—]*\s*\n+([\s\S]{500,40000}?)(?=\n\s*\n\s*(?:appendix|acknowledg|author|bio|\Z)|\Z)',
        ]
       
        for pat in ref_patterns:
            m = re.search(pat, text, re.DOTALL | re.MULTILINE)
            if m:
                ref_section = m.group(1).strip()
                if len(ref_section) > 100:
                    break
       
        if ref_section:
            ref_lines = ref_section.split('\n')
            for line in ref_lines:
                line = line.strip()
                if len(line) < 10:
                    continue
                line = re.sub(r'^[\[\(\d\.\)\-\s]+', '', line).strip()
                if len(line) > 15:
                    references.append(line[:180])
       
        return references[:50]

    def extract_visuals(self, text: str) -> Dict[str, Any]:
        visuals = {'tables': [], 'figures': [], 'counts': {'figures': 0, 'tables': 0, 'charts': 0}}
        fig_pattern = r'(?i)\b(?:figure|fig\.?)\s+(\d+[a-zA-Z]?(?:\.\d+)?)'
        table_pattern = r'(?i)\b(?:table)\s+(\d+[a-zA-Z]?(?:\.\d+)?)'
       
        fig_matches = re.findall(fig_pattern, text)
        table_matches = re.findall(table_pattern, text)
       
        visuals['counts']['figures'] = len(set(fig_matches))
        visuals['counts']['tables'] = len(set(table_matches))
        visuals['counts']['charts'] = len(re.findall(r'(?i)\b(?:graph|chart|plot|diagram)\s+\d+', text))
       
        for num in set(fig_matches):
            visuals['figures'].append({'number': num, 'caption': f'Figure {num}'})
        for num in set(table_matches):
            visuals['tables'].append({'number': num, 'caption': f'Table {num}', 'data': None})
       
        return visuals

    def calculate_statistics(self, text: str) -> Dict[str, Any]:
        word_count = len(text.split())
        unique_words = len(set(w.lower() for w in re.findall(r'\b\w+\b', text)))
        sentence_count = len(re.split(r'[.!?]+', text))
       
        return {
            'word_count': word_count,
            'unique_words': unique_words,
            'sentence_count': max(1, sentence_count - 1),
            'avg_words_per_sentence': round(word_count / max(1, sentence_count - 1), 2),
            'characters': len(text),
            'paragraphs': len(re.split(r'\n\s*\n', text))
        }

    def generate_summary(self, text: str, max_length: int = 500, min_length: int = 150) -> str:
        self._load_models()
        if not text or len(text.strip()) < 100:
            return text
        return self._extractive_summary(text, max_length)

    def _extractive_summary(self, text: str, max_length: int = 500) -> str:
        if len(text) > 15000:
            text = text[:15000]
       
        sentences = re.split(r'(?<=[.!?])\s+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 30]
       
        if len(sentences) <= 2:
            return text[:500] if len(text) > 500 else text
       
        stop_words = self._get_stop_words()
       
        if _load_nltk() and _word_tokenize is not None and SKLEARN_AVAILABLE:
            try:
                words = _word_tokenize(text.lower())
                words = [w for w in words if w.isalnum() and w not in stop_words]
                word_freq = Counter(words)
               
                sentence_scores = {}
                for i, sent in enumerate(sentences):
                    sent_words = _word_tokenize(sent.lower())
                    score = sum(word_freq.get(w, 0) for w in sent_words)
                    if i < 3:
                        score += 4
                    elif i < 6:
                        score += 2
                    sentence_scores[i] = score
               
                top_n = min(6, len(sentences))
                top_sentences = sorted(sentence_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
                top_sentences = sorted(top_sentences, key=lambda x: x[0])
                summary = ' '.join(sentences[i] for i, _ in top_sentences)
                return summary[:max_length].rsplit(' ', 1)[0] + '.' if summary else text[:max_length]
            except Exception as e:
                logger.warning(f"Extractive summary failed: {e}")
       
        return self._basic_summary(text, max_length)

    def _basic_summary(self, text: str, max_length: int = 150) -> str:
        if len(text) > 15000:
            text = text[:15000]
       
        sentences = re.split(r'(?<=[.!?])\s+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 30]
       
        if len(sentences) <= 2:
            return text[:500] if len(text) > 500 else text
       
        scored = []
        for i, sent in enumerate(sentences):
            score = 0
            if i < 3:
                score += 3
            important_words = ['propose', 'present', 'demonstrate', 'show', 'result', 'method', 'approach', 'novel', 'new', 'significant', 'achieve', 'performance', 'accuracy']
            sent_lower = sent.lower()
            for word in important_words:
                if word in sent_lower:
                    score += 1
            if len(sent) > 80:
                score += 1
            scored.append((score, sent))
       
        scored.sort(key=lambda x: x[0], reverse=True)
        top_sentences = [s[1] for s in scored[:4]]
        top_sentences.sort(key=lambda x: sentences.index(x))
        return ' '.join(top_sentences[:3])[:max_length]

    def full_analysis(self, text: str) -> Dict:
        self._load_models()
        max_chars = int(os.getenv("ANALYSIS_TEXT_MAX", "52000"))
        if text and len(text) > max_chars:
            text = text[:max_chars]
       
        # Safe extraction with fallback for 'impact'
        impact_value = ""
        try:
            impact_value = self.extract_impact(text)
        except Exception as e:
            logger.warning(f"extract_impact failed: {e}")
            impact_value = "Impact analysis could not be generated."

        return {
            'title': self.extract_title(text),
            'authors': self.extract_authors(text),
            'publication_year': self.extract_publication_year(text),
            'abstract': self.extract_abstract(text),
            'summary': self.generate_summary(text[:5000]),
            'native_summary': self.extract_native_summary(text),
            'conclusion': self.extract_conclusion(text),
            'keywords': self.extract_keywords(text),
            'methodology': self.detect_methodology(text),
            'methodology_summary': self.extract_methodology_summary(text),
            'technologies': self.detect_technologies(text),
            'goal': self.extract_goal(text),
            'impact': impact_value,                    # ← Fixed here
            'research_gaps': self.detect_research_gaps(text),
            'dataset_names': self.extract_datasets(text).get('names', []),
            'dataset_links': self.extract_datasets(text).get('links', []),
            'visual_assets': self.extract_visuals(text),
            'extracted_links': self.extract_links(text),
            'references': self.extract_references(text),
            'statistics': self.calculate_statistics(text),
        }
# Global instance
ml_processor = MLProcessor()