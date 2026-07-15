# Phase-0 Novelty Memo

**Date:** 2026-07-15
**Reviewer:** Researcher agent (claude-fable-5)
**Verdict:** INCREMENTAL — novel in combination; well-trodden in parts

---

## 1. Search Strategy

Queries executed (all via live web search, 2026-07-15):

1. "Halawi LLMs approaching human-level forecasting 2024"
2. "Schoenegger LLM forecasting wisdom of silicon crowds 2024"
3. "ForecastBench Karger continuously updated contamination-free LLM forecasting benchmark 2024"
4. "Zou Autocast forecasting world events language models 2022"
5. "forecast encompassing information content LLM prediction market comparison test"
6. "AI progress domain forecasting benchmark evaluation calibration 2024 2025"
7. "knowledge cutoff contamination LLM evaluation forecasting leakage temporal 2024"
8. "PolyBench LLM prediction market trading transaction cost backtest 2025 2026"
9. "LLM forecast prediction market information content complementary combination 2024 2025"
10. "forecasting scientific progress AI capabilities Metaculus questions LLM evaluation 2024 2025"
11. "LLM forecasting knowledge cutoff post-cutoff Brier score skill contamination evaluation 2024 2025"
12. "forecast encompassing prediction market LLM 2024 2025 2026"
13. "LLM forecast incremental information prediction market combination regression 2024 2025"
14. "Metaculus Manifold AI progress questions dataset curated released public 2024 2025 research paper"

Each candidate paper was fetched directly (abstract page) to verify authors, venue, and methodology before being cited. No citation is memory-only.

---

## 2. The Five Closest Works

### W-1. Halawi et al. 2024 — "Approaching Human-Level Forecasting with Language Models"
- **Citation:** Danny Halawi, Fred Zhang, Chen Yueh-Han, Jacob Steinhardt. NeurIPS 2024. arXiv: 2402.18563. https://arxiv.org/abs/2402.18563
- **What they did:** Built a retrieval-augmented LLM pipeline; compared its calibrated aggregate against the human crowd on general forecasting tournament questions (Metaculus, Polymarket, etc.); used questions resolved after model cutoffs to avoid outcome memorization.
- **How we differ:** (a) Domain: they use general multi-topic questions; we restrict to AI-progress questions, which is both decision-relevant and under-studied. (b) Framing: they run an accuracy horse-race (Brier scores); we run forecast-encompassing regressions to test directional information content. (c) Contamination rule: they apply R > C (outcome not in training data); we apply C ≤ T (snapshot date also after cutoff), which closes an information-recency leak Halawi et al. do not address. (d) We release a curated AI-progress dataset with time-stamped crowd snapshots; they do not. (e) No friction backtest.

### W-2. Schoenegger et al. 2024 — "Wisdom of the Silicon Crowd"
- **Citation:** Philipp Schoenegger, Indre Tuminauskaite, Peter S. Park, Philip E. Tetlock. Science Advances 10(45), eadp1528, 2024. arXiv: 2402.19379. https://arxiv.org/abs/2402.19379
- **What they did:** Aggregated 12 LLMs on 31 binary questions; compared against 925 human forecasters in a 3-month Metaculus tournament; found the LLM crowd statistically indistinguishable from the human crowd. Also exposed GPT-4/Claude-2 to median human prediction and measured accuracy change.
- **How we differ:** (a) No contamination handling: they do not split by model cutoff or apply any temporal cleanliness rule. (b) General domain: their questions cover all of Metaculus, not AI-progress. (c) No information-content or encompassing test: Study 2 shows LLMs improve when given human predictions, but does not test whether the market (or crowd) carries information the model lacks independent of the model's own signal. (d) Small question set (31 questions), single tournament. (e) No dataset release; no friction analysis.

### W-3. Karger et al. 2025 — "ForecastBench: A Dynamic Benchmark of AI Forecasting Capabilities"
- **Citation:** Ezra Karger, Houtan Bastani, Chen Yueh-Han, Zachary Jacobs, Danny Halawi, Fred Zhang, Philip E. Tetlock. ICLR 2025. arXiv: 2409.19839. https://arxiv.org/abs/2409.19839
- **What they did:** Built a continuously updated, prospective benchmark (questions submitted before resolution) sourcing from nine platforms including Manifold, Polymarket, and Metaculus; compared expert forecasters, general public, and LLMs; found expert forecasters significantly outperform LLMs.
- **How we differ:** (a) Their contamination solution is prospective (only unresolved questions at submission time); ours is retrospective with C ≤ T, enabling use of a richer historical corpus of already-resolved AI-progress questions. These are complementary approaches. (b) No domain-level stratification: they do not report AI-progress-specific results. (c) No forecast-encompassing test between LLM and crowd/market forecasts — they measure absolute LLM accuracy vs. human baselines. (d) No friction backtest. (e) No released curated AI-progress dataset with per-question crowd snapshots.

### W-4. Alur et al. 2025 — "AIA Forecaster: Technical Report"
- **Citation:** Rohan Alur, Bradly C. Stadie, Daniel Kang, Ryan Chen, et al. arXiv: 2511.07678, November 2025. https://arxiv.org/abs/2511.07678
- **What they did:** Built an agentic LLM forecaster and evaluated it on ForecastBench and a liquid-market benchmark. Critically, they run a bivariate simplex-constrained regression of the binary resolution indicator on market price and LLM forecast, with bootstrap CIs, to quantify LLM weight in the combination. Found that on ForecastBench-style questions, the LLM receives 87% weight (markets add nothing); on liquid market questions, both sources carry weight.
- **How we differ:** This is the closest existing work to RQ3. Differences: (a) Their regression is a Bates-Granger forecast-combination, finding optimal mixture weights; ours is a Harvey-Leybourne-Newbold forecast-encompassing test, which tests the null that one source's coefficient equals zero — a stronger, directional claim about information redundancy. (b) They aggregate across all domains; we focus on AI-progress only. (c) They do not apply a C ≤ T rule. (d) They do not release a curated domain-specific dataset. (e) No pre-registration. The distinction between "optimal forecast combination weights" and "forecast encompassing" is non-trivial: encompassing directly answers "does the market contain information the model lacks (and vice versa)?"; the AIA paper answers "what is the optimal mixture?". Both are useful but the encompassing framing is more informative for our RQ3.

### W-5. Zou et al. 2022 — "Forecasting Future World Events with Neural Networks" (Autocast)
- **Citation:** Andy Zou, Trung Xiao, Ryan Bhatt, Arber Toy, Orion Weller, Ruixing Liang, Scott Emmons, Dan Hendrycks. NeurIPS 2022. arXiv: 2206.15474. https://arxiv.org/abs/2206.15474
- **What they did:** Introduced the Autocast dataset (thousands of forecasting questions with a news corpus, questions from forecasting tournaments); showed LM performance far below human experts; the news corpus allowed temporal simulation of conditions under which humans forecasted.
- **How we differ:** Foundational benchmark work. They do not compare LLM to prediction markets (information content), focus on general domains, do not apply cutoff-based contamination splitting, and do not test encompassing. Our study is conceptually downstream of this work but distinct in domain, framing, and methodology.

---

## 3. Verdict: INCREMENTAL

### Justification

The LLM-vs-crowd calibration comparison (RQ1) is a saturated question: Halawi et al. 2024, Schoenegger et al. 2024, ForecastBench, and the Metaculus AI Forecasting Benchmark tournament series all measure this horse-race in increasingly rigorous settings. Anyone who claims "novel calibration findings" in 2026 without a strong domain or methodological differentiator is overclaiming. Our RQ1 is replication and extension in a specific, decision-relevant domain.

What is not yet done: No existing paper applies the specific combination of (a) restriction to AI-progress questions, (b) a formal forecast-encompassing test between market and LLM forecasts, (c) the C ≤ T snapshot-aware contamination rule that closes the information-recency leak, and (d) a released, versioned, curated dataset of AI-progress binary questions with time-stamped crowd snapshots. The AIA Forecaster (W-4) comes closest on (b) — they run a simplex regression that is directionally similar to RQ3 — but does not do (a), (c), or (d), and uses a different statistical framing (forecast combination rather than encompassing). The project is correctly positioned in D-001: RQ1 as replication+extension, the information-content and encompassing framing (RQ3) as the contribution.

**One clear risk:** The field is moving fast. Several 2026 preprints appeared during this search. A domain-specific encompassing paper could emerge before publication. The team should monitor the arXiv forecasting stream continuously and check again at Phase 2.

---

## 4. Methodological Lessons from Closest Works

- **Instruction-based cutoff enforcement reliably fails.** Li et al. 2025 ("Simulated Ignorance Fails", arXiv 2601.13717) tested 9 LLMs on 477 questions and found a 52% performance gap between truly-ignorant and prompted-ignorant conditions, with chain-of-thought reasoning unable to suppress prior knowledge. This validates D-002/D-006: our C ≤ T rule must be structural (sample filtering), not reliant on the elicitation prompt saying "ignore post-cutoff information". The prompt instruction is useful for intent signaling but cannot be the cleanliness mechanism.

- **The simplex-combination vs. encompassing distinction matters for positioning.** The AIA Forecaster (W-4) uses simplex regression and reports mixture weights. Forecast encompassing (our RQ3 design) is a stronger test: it directly asks whether the coefficient on one source is statistically distinguishable from zero after conditioning on the other. When presenting RQ3 results, the write-up must be explicit that we test encompassing (null: coefficient = 0) rather than reporting optimal weights — this differentiates us from AIA Forecaster. Concretely, the encompassing regression is outcome ~ logit(market) + logit(model) in a logistic framework, with separate Wald tests on each coefficient.

- **Domain stratification is absent from all extant work and that is the gap.** ForecastBench, Halawi et al., Schoenegger et al., and the Metaculus tournament benchmarks all report aggregate Brier scores across mixed domains. None stratify by AI-progress, technology, or capability questions. The claim that calibration or information content behaves differently in this domain is empirically untested — which is precisely the contribution. If our results replicate aggregate findings, the contribution is still the domain-specific evidence base; if AI-progress questions are anomalous (e.g., systematically over-optimistic, or where markets and LLMs diverge more than average), that is a stronger finding.

- **Small N is a known risk in domain-specific forecasting work.** Even ForecastBench, with continuous question generation from nine sources, found only ~1,000 questions across all domains. AI-progress-specific questions are a small fraction of any platform. The C ≤ T filter shrinks N further. The Phase-0 data recon must be done before committing to confirmatory RQ3 framing (per D-008): power is the central feasibility risk, not novelty.
