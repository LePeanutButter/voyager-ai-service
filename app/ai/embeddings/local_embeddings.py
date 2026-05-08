"""Local embedding generator using transformers (no cloud APIs)."""

from __future__ import annotations

from functools import lru_cache
from typing import List

import torch
from transformers import AutoModel, AutoTokenizer

from app.core.config import settings


class LocalEmbeddingService:
    """Generates normalized embeddings from a local HuggingFace model."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.LOCAL_EMBEDDING_MODEL
        self.tokenizer = _load_tokenizer(self.model_name)
        self.model = _load_model(self.model_name)

    def embed(self, text: str) -> List[float]:
        if not text.strip():
            return [0.0] * 384

        encoded = self.tokenizer(
            text,
            truncation=True,
            padding=True,
            max_length=512,
            return_tensors="pt",
        )

        with torch.no_grad():
            model_out = self.model(**encoded)
            token_embeddings = model_out.last_hidden_state
            attention_mask = encoded["attention_mask"].unsqueeze(-1).expand(token_embeddings.size()).float()
            sum_embeddings = torch.sum(token_embeddings * attention_mask, dim=1)
            sum_mask = torch.clamp(attention_mask.sum(dim=1), min=1e-9)
            sentence_embedding = sum_embeddings / sum_mask
            normalized = torch.nn.functional.normalize(sentence_embedding, p=2, dim=1)
            return normalized[0].cpu().tolist()


@lru_cache(maxsize=1)
def _load_tokenizer(model_name: str):
    return AutoTokenizer.from_pretrained(model_name, local_files_only=False)


@lru_cache(maxsize=1)
def _load_model(model_name: str):
    model = AutoModel.from_pretrained(model_name, local_files_only=False)
    model.eval()
    return model
