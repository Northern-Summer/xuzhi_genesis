# AI for Linguistics — AI4S Weekly Research
**Generated:** 2026-03-29 | **Agent:** Φ Phi

## Top 3 Open Source Reproducible Projects

### 1. Transformers / HuggingFace (NLP backbone)
- **URL:** https://github.com/huggingface/transformers
- **What:** Pre-trained multilingual models (BERT, mBERT, XLM-R); syntactic parsing, semantic analysis, NER, translation
- **How to replicate:** `pip install transformers`; model hub has 500k+ models for 100+ languages
- **Status:** Open Source | ⭐70k+ | Apache 2.0

### 2. spaCy (industrial NLP)
- **URL:** https://github.com/explosion/spaCy
- **What:** Production-grade linguistic annotation; POS tagging, dependency parsing, named entity recognition, lemmatization
- **How to replicate:** `pip install spacy`; download language models: `python -m spacy download en_core_web_sm`
- **Status:** Open Source | ⭐30k+ | MIT

### 3. Whisper (OpenAI)
- **URL:** https://github.com/openai/whisper
- **What:** Multilingual speech-to-text; low-resource language transcription; enables linguistic fieldwork
- **How to replicate:** `pip install openai-whisper`; `whisper audio.mp3 --model medium`; supports 99 languages
- **Status:** Open Source | MIT | Robust against accents/dialects

## Cross-Linguistic AI Best Practices
1. XLM-RoBERTa > mBERT for most cross-lingual tasks
2. Whisper enables low-resource language preservation
3. spaCy for structured linguistic analysis at scale
4. Use model hub for domain-specific fine-tunes (legal, medical, ancient languages)

## Next Update
2026-04-05 (weekly)
