# Broker feasibility for trading CME FG/CG football event contracts (and Kalshi) as US retail

Web research 2026-10-04 (about 07:05 to 07:12 ET), no accounts opened. "Verified" = read on a first-party page in
this session; "reported" = press coverage only, not confirmed first-party. Fees and order rules change; recheck
before any live use (paper trading only, CLAUDE.md rule 6).

| broker / app | CME football event contracts for US retail? | Kalshi? | order types | commission | API | source |
|---|---|---|---|---|---|---|
| FanDuel Predicts | Yes: CME Group's own retail channel for its sports event contracts, launched Dec 2025 in 5 states (AL, AK, SC, ND, SD), phased national rollout through early 2026 (reported) | No | not found first-party | not found first-party | none known | CME press release 2025-11-12 (cmegroup.com media room, "FanDuel and CME Group unveil new prediction markets platform"); crowdfundinsider, investmentexecutive |
| Interactive Brokers | Reported: IBKR is adding Kalshi and CME event contracts to its ForecastEx interface "on a rolling basis"; reported CME event-contract fee 10 c per contract; IBKR said initial focus is non-sports, sports for retail undecided | Reported (rolling) | IBKR standard (limit, DAY/GTC/IOC on most products); not confirmed for CME sports contracts | reported $0.10 per CME event contract | TWS API has an event-trading section (interactivebrokers.com docs "CME Event Contracts") | defirate, forklog (press); IBKR TWS API docs page exists |
| Webull | Not found: Webull's prediction markets route to Kalshi; no evidence of CME FG/CG access | Yes (Kalshi partnership) | App: event contracts Limit and Market, Day limit orders (reported); OpenAPI: event contracts use LIMIT, time_in_force DAY, GTC, IOC, GTD, FOK (verified on developer.webull.com trade-api/event-contract); the repo's sandbox note says IOC for EVENT orders is not shown in the SDK sample (docs/webull_risk_controls.md line 48) | exchange fee $0.01 + firm fee $0.01 per contract per side (reported), $0 commission promos | Webull OpenAPI (verified page) | developer.webull.com/apis/docs/trade-api/event-contract; barchart/finder (press) |
| Robinhood | No CME football; Robinhood's football prediction markets are Kalshi-routed (Aug 2025) | Yes | not checked first-party | not checked | no public trading API for event contracts known | theblock, sbcamericas (press) |
| Coinbase | No CME; Kalshi-powered prediction markets in all 50 states | Yes | not checked | not checked | not checked | theblock, decrypt (press) |
| NinjaTrader / Tradovate | Offers CME "event contracts" since 2022, but those found are the $20-payout financial daily event contracts (index, metals, FX); no evidence found of FG/CG football access | No | Tradovate mobile event-contract UI | not checked | Tradovate API exists for futures | ninjatrader.com and tradovate.com press releases (first-party, 2022) |
| DraftKings Predictions | No CME: uses its own Railbird exchange (DCM), football contracts filed Aug 10 | No | not checked | not checked | not checked | legalsportsreport, igamingbusiness (press) |

## Answers to Divi's questions

- **Can US retail trade CME FG/CG football contracts?** Through FanDuel Predicts (CME's partner, state-limited)
  and, reportedly, IBKR as it rolls in CME event contracts. Not through Webull, Robinhood or Coinbase, which route
  to Kalshi. NinjaTrader/Tradovate's CME event contracts found are the financial ones, not football.
- **Order types and fast cancels on CME football:** not established first-party for any retail channel. FanDuel
  Predicts is a mobile app with no known API, so second-level cancels and a resting queue strategy are not
  realistic there. IBKR's TWS API would allow programmatic limit orders and cancels if CME sports contracts are
  enabled for the account, which is unconfirmed.
- **Commissions:** CME's own exchange fee is $0.01 per contract per trade (CME 25-466 Appendix D). IBKR reportedly
  charges $0.10 per CME event contract, which alone exceeds the +0.5 to +1.0 c real-minus-placebo informational
  edge found in Stage 1 and dwarfs any maker profit in the audit's bounds.
- **Contract size and tick:** $1 contract, $0.01 tick (CME 25-466 Appendix A).
- **Latency app/API to exchange:** no first-party figure found for any of these retail channels. Retail app routing
  typically adds tens to hundreds of ms plus the user's own reaction; CME follows Kalshi within about 0.5 to 6.5 s,
  so latency is not the binding constraint; the spread and fees are.
- **Kalshi via Webull:** the OpenAPI lists DAY, GTC, IOC, GTD and FOK for event contracts (verified page); whether
  IOC works for Kalshi EVENT orders in practice is unconfirmed (repo sandbox note). The app reportedly allows Day
  limit orders.

Not verified first-party here (blocked or not found): FanDuel Predicts fee schedule and order types; IBKR CME sports
availability; Robinhood/Coinbase event order types.
