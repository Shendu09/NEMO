#!/usr/bin/env python
"""Test DistilBART summarizer."""

import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

print("Loading DistilBART summarizer...")
model_name = "sshleifer/distilbart-cnn-12-6"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
print("✓ DistilBART loaded successfully")

# Test with sample text
sample = """Natural language processing (NLP) is a subfield of linguistics, computer science, 
and artificial intelligence concerned with the interactions between computers and human language. 
NLP is used to apply machine learning algorithms to text and speech. Some NLP tasks include 
sentiment analysis, named-entity recognition, question answering, and machine translation. 
These tasks have widespread applications in business, scientific research, and everyday computing."""

print(f"\nInput text ({len(sample)} chars):")
print(sample)

# Tokenize and generate summary
inputs = tokenizer(sample, max_length=1024, return_tensors="pt", truncation=True)
summary_ids = model.generate(
    inputs["input_ids"],
    max_length=60,
    min_length=30,
    do_sample=False,
    num_beams=4,
    early_stopping=True
)
summary = tokenizer.batch_decode(summary_ids, skip_special_tokens=True)[0]

print(f"\nSummary ({len(summary)} chars):")
print(summary)
print("\n✓ DistilBART summarizer works!")
