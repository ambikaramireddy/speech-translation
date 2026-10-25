"""Evaluate a configured translator against samples/evaluation.json."""
import asyncio, json
from pathlib import Path
from sacrebleu.metrics import BLEU, CHRF
from .cache import Cache
from .config import get_settings
from .pipeline import Pipeline
from .audiclabs import AudicLabsClient
from .translator import GeminiTranslator, StubTranslator

async def main():
    settings=get_settings(); translator=StubTranslator() if settings.translator_backend.lower()=="stub" else GeminiTranslator(settings)
    pipeline=Pipeline(settings,AudicLabsClient(settings),translator,Cache(settings.cache_db))
    records=json.loads((Path(__file__).parent.parent/"samples"/"evaluation.json").read_text(encoding="utf-8"))
    by_pair={}
    for record in records:
        hypothesis,_=await pipeline.translate_text(record["source"],record["source_lang"],record["target_lang"],{})
        pair=f"{record['source_lang']}-{record['target_lang']}"
        by_pair.setdefault(pair,[[],[]]); by_pair[pair][0].append(hypothesis); by_pair[pair][1].append(record["target"])
    for pair,(hyp,refs) in by_pair.items():
        print(f"{pair}: samples={len(hyp)} BLEU={BLEU().corpus_score(hyp,[refs]).score:.2f} chrF={CHRF().corpus_score(hyp,[refs]).score:.2f}")
        for src,out,ref in zip([x["source"] for x in records if f"{x['source_lang']}-{x['target_lang']}"==pair],hyp,refs): print(f"  source={src}\n  output={out}\n  reference={ref}")
if __name__=="__main__": asyncio.run(main())
