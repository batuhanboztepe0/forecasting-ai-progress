# Working Reference List

All citations verified by fetching primary source (abstract page or full text). No memory-only citations. Last updated: 2026-07-15.

---

## Core Closest Works (Phase-0 novelty check)

**[Halawi2024]** Halawi D., Zhang F., Yueh-Han C., Steinhardt J. "Approaching Human-Level Forecasting with Language Models." NeurIPS 2024. arXiv: 2402.18563. https://arxiv.org/abs/2402.18563 — Retrieval-augmented LLM system near crowd-level accuracy on general forecasting questions; uses post-cutoff (R > C) contamination filter; no domain restriction, no encompassing test.

**[Schoenegger2024]** Schoenegger P., Tuminauskaite I., Park P.S., Tetlock P.E. "Wisdom of the Silicon Crowd: LLM Ensemble Prediction Capabilities Rival Human Crowd Accuracy." Science Advances 10(45), eadp1528, 2024. arXiv: 2402.19379. https://arxiv.org/abs/2402.19379 — 12-LLM ensemble vs. 925 human forecasters in a 3-month Metaculus tournament; finds parity; no contamination control, no domain restriction, no encompassing.

**[Karger2025]** Karger E., Bastani H., Yueh-Han C., Jacobs Z., Halawi D., Zhang F., Tetlock P.E. "ForecastBench: A Dynamic Benchmark of AI Forecasting Capabilities." ICLR 2025. arXiv: 2409.19839. https://arxiv.org/abs/2409.19839 — Continuously updated, prospective (unresolved-at-submission) benchmark; expert forecasters outperform LLMs; no domain stratification, no encompassing test, no market vs. LLM information content analysis.

**[Alur2025]** Alur R., Stadie B.C., Kang D., Chen R., et al. "AIA Forecaster: Technical Report." arXiv: 2511.07678, November 2025. https://arxiv.org/abs/2511.07678 — Agentic LLM forecaster; runs bivariate simplex-constrained regression (market price + LLM forecast) on binary outcomes; closest existing work to RQ3 but uses forecast-combination framing (not encompassing), aggregates across all domains, no C ≤ T rule.

**[Zou2022]** Zou A., Xiao T., Bhatt R., Toy A., Weller O., Liang R., Emmons S., Hendrycks D. "Forecasting Future World Events with Neural Networks." NeurIPS 2022. arXiv: 2206.15474. https://arxiv.org/abs/2206.15474 — Introduces Autocast benchmark; LMs far below human experts on general forecasting questions; foundational benchmark work.

---

## Methodologically Relevant (cited in novelty memo or design notes)

**[Li2025]** Li Z., Wang Y., El Lahib A., Xia Y., Pi X. "Simulated Ignorance Fails: A Systematic Study of LLM Behaviors on Forecasting Problems Before Model Knowledge Cutoff." arXiv: 2601.13717, January 2025. https://arxiv.org/abs/2601.13717 — 52% performance gap between truly-ignorant and prompted-ignorant LLMs on 477 questions; shows instruction-based cutoff enforcement is unreliable; validates structural sample-filtering approach (C ≤ T rule).

**[Zhang2026]** Zhang Z., Chen R., Stadie B.C. "All Leaks Count, Some Count More: Interpretable Temporal Contamination Detection and Mitigation in LLM Backtesting." arXiv: 2602.17234, February 2026. https://arxiv.org/abs/2602.17234 — Introduces Shapley-DCLR metric to quantify contaminated reasoning and TimeSPEC architecture; relevant to contamination detection methodology.

**[Cheng2026]** Cheng P., Liu J., Long Y. "PolyBench: Benchmarking LLM Forecasting and Trading Capabilities on Live Prediction Market Data." arXiv: 2604.14199, April 2026. https://arxiv.org/abs/2604.14199 — 38,666 Polymarket binary markets; 7 LLMs evaluated on forecasting + trading (CWR, APY, Sharpe) via order-book simulation; only 2 of 7 achieve positive returns; no domain restriction, no encompassing test.

**[Arora2025]** Arora A., Malpani R. "PredictionMarketBench: A SWE-bench-Style Framework for Backtesting Trading Agents on Prediction Markets." arXiv: 2602.00133, February 2025. https://arxiv.org/abs/2602.00133 — Deterministic limit-order-book replay framework for trading agent evaluation on Kalshi; fee-aware strategies outperform naive agents; relevant to RQ4 friction modeling.

**[Paleka2025]** Paleka D., Goel S., Geiping J., Tramèr F. "Pitfalls in Evaluating Language Model Forecasters." arXiv: 2506.00723, May 2025. https://arxiv.org/abs/2506.00723 — Catalogs temporal leakage forms and extrapolation pitfalls in LLM forecasting evaluation; relevant to methodology review.

**[Ma2026]** Ma Y., Ruan C., Huang K., Yang Z., Zhou L. "OracleProto: A Reproducible Framework for Benchmarking LLM Native Forecasting via Knowledge Cutoff and Temporal Masking." arXiv: 2605.03762, May 2026. https://arxiv.org/abs/2605.03762 — Framework with model-cutoff-aligned sample admission and tool-level temporal masking; reduces information leakage to ~1%; relevant to contamination methodology comparison.

**[Tian2026]** Tian Q., Yin H., Xia Y., Kong Y., Liu Z. "ForeSci: Evaluating LLM Agents for Forward-Looking AI Research Judgment." arXiv: 2606.00644, May 2026. https://arxiv.org/abs/2606.00644 — 500-task benchmark for LLM agents on AI-research-domain forward-looking judgment; no crowd/market comparison, no encompassing test; demonstrates AI-domain forecasting is a recognized research direction.

**[EpochAI2026]** Epoch AI. "How Well Did Forecasters Predict 2025 AI Progress?" Blog post, 2026. https://epoch.ai/gradient-updates/how-well-did-forecasters-predict-2025-ai-progress — Retrospective calibration analysis of 421 human forecasters on AI-progress questions; descriptive, no LLM comparison, no formal statistical tests; shows systematic underestimation of AI progress.
