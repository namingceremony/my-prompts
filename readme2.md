# Claim Validator Pilot (Aug-Sep 2026): Recovery Action Plan

Date: 19 Nov 2026
Prepared by: GenAI validator team
Covers: the two-stage pipeline (primary model "Model A" -> SOP-RAG GenAI validator, policy v3.6)

Ground rule: the primary model belongs to another team, and we do not change its model,
threshold (0.8384), inputs or training. Every action below changes only the GenAI validator, the
way we measure, or the data we accept. Anything that needs the primary model to change is a
recommendation to its owners (section 5F).

---

## 1. Summary

### What happened
- 5,034 requests (ORS) opened in Aug-Sep 2026 went through the pipeline.
- The pipeline auto-closed 40 as "no action needed" (NAN), and 9 of those were right: 22.5%
  precision, 95% range 12-38%. Closing nothing at all would have scored slightly higher accuracy:
  90.4% vs 89.9%.
- It failed safe. There were 31 wrong closures in 5,034 requests (0.6%), and 99.3% of the
  requests that needed rework stayed with a processor.
- August, whose outcomes are mostly final, failed the same way (3 of 12 right). So this is not
  only a labelling delay.

### Why
1. **The primary model lost its confident NAN scores on the new data.**
   - AUC fell from 0.92 to 0.77-0.79.
   - The share of requests in the release band fell from 7.8% to 0.7-1.4%.
   - Precision inside that band fell from 89% to 21-25%.
   - Re-scoring from a clean (non-Excel) file gave the same result.
2. **The model's inputs include history from after the request opened.** It learned from
   records showing what happened after opening (rework adjustments, later statuses).
   - In the new extract, 99% of requests show such activity, against 75-92% in the training
     data. The "nothing has happened yet" pattern behind its confident NAN scores has gone.
   - In production, requests will be scored before anything has happened. That is a third,
     different situation.
3. **The request mix moved towards groups that are almost never NAN.**
   - Internal requests (letters in the ID suffix): 2.8% NAN, now 41-46% of volume (22-33% before).
   - ABA providers: 2.9% NAN, now 33% of volume (10-23% before).
4. **Part of the measurement is unreliable.** September outcomes are not final yet, the pilot
   files were not a full sample of each month, and the input files went through Excel.

**The GenAI layer did not cause the drop.** The release rule stopped 1,320 of the primary
model's 1,360 NAN calls before the LLM was called. The LLM saw only the other 40.

### What we will do
1. **Safety first (this week).** Nothing is auto-closed, through any path, until a rule passes
   an agreed bar. This means a shadow mode, an automatic switch-off, honest reason text and
   clean inputs only.
2. **Correct the measurement (this week).** Final outcomes only, full monthly populations,
   clean files.
3. **Run the decisive test (next two weeks, no LLM cost).** Replay historical requests exactly as
   they looked on the day they opened. Score them with the unchanged primary model, and
   calibrate our release rule on that. This tells us whether safe auto-close is possible in
   production at all.
4. **If the test passes:** a stricter, scoped release rule, confirmed once on later months, then
   a monitored shadow run on the daily feed before any live closure.
5. **If it fails:** stop auto-close. Offer a fast-check lane instead: likely-NAN requests are
   ranked and explained, and a processor decides. Pass the retrain recommendation to the primary
   model's owners.

### What we need from you
1. Agree that the current release rule (release when P(Rework) <= 0.30) is retired, and that the
   system runs in shadow mode until a new rule passes.
2. Agree the pass mark (based on the cost of a wrong closure, section 6) and the stop rule before
   any new result is seen.
3. Help us get answers:
   - from Claims Ops: the cost of a wrong closure, and their interest in a fast-check lane;
   - from the data owner: how the new table and the pilot files were selected, and what the
     daily feed will contain for provider comments and request reason when a request opens.

### What to expect
- **Certain within a week:** zero wrong auto-closures while we test, and numbers we can trust.
- **Not yet known:** whether any safe auto-close is possible with the current primary model. A
  "no" is a real possibility, because the bar is high and the model has already lost its
  confident band on new data. The plan covers both outcomes.
- **If the answer is yes,** the auto-close lane will be small (a few percent of requests at most).
  A production decision is realistic around Feb-Mar 2027, because outcomes take about two
  months to become final.

---

## 2. Where the numbers stand

| | Aug | Sep 1-23 | Sep 23-30 | Total |
|---|---|---|---|---|
| Requests | 831 | 2,101 | 2,102 | 5,034 |
| NAN share (outcomes as of the extract) | 25.8% | 8.3% | 4.6% | 9.6% |
| Auto-closed (released as NAN) | 12 | 13 | 15 | 40 |
| ... of which correct | 3 | 5 | 1 | 9 (22.5%) |
| Pipeline accuracy | 73.5% | 91.6% | 94.8% | 89.9% |
| Accuracy if nothing is closed | 74.2% | 91.7% | 95.4% | 90.4% |

Primary model alone: 1,360 NAN calls. 24.6% of those were correct, and they covered 69.2% of all
NAN requests.

How to read these numbers:
- **Accuracy is the wrong headline.** About 90% of requests need rework, so closing nothing
  already scores about 90%. Accuracy only rises above that when release precision is above 50%.
  The numbers that matter are release precision (with its range), release volume and wrong
  closures.
- **The 87% we quoted in October was measured on a different basis:**
  - one request per claim, for claims opened 16 May-30 Jun;
  - claim-level outcomes;
  - model inputs that included later history.

  It was an upper bound, not a production estimate.
- **The counts are small.** With 40 releases the 95% range is 12-38%. For August's 12 releases
  it is 9-53%. Comparisons between periods are mostly noise.

---

## 3. Why the numbers dropped: evidence

| Cause | Evidence | Verdict | Who can act |
|---|---|---|---|
| Primary model lost its confident NAN band | AUC 0.918 (holdout) -> 0.767 (Aug) / 0.785 (Sep). Release band 7.8% -> 1.4% / 0.7% of requests. Precision in the band 89% -> 25% / 21% | Confirmed, including in mature August | Model A team. We can only adapt our rule |
| Model inputs depend on when the data is pulled | Activity after opening in 99% of Jun-Sep requests in the new extract, vs 75-92% in the training data. Latest processing date 28 Oct vs 2 Oct | Likely main mechanism; the decisive test (5C) checks it | Model A team; we test it |
| Mix shift to low-NAN groups | Internal requests 2.8% NAN, 41-46% of volume (was 22-33%). ABA 2.9% NAN, 33% (was 10-23%). No request reason 45-47% (was 25-36%) | Confirmed | Us: scope rules |
| Outcomes not final yet | NAN share by opening week: 20-29% in August, 4-6% in late September. 119 of 819 requests labelled rework in an earlier extract are now NAN (3 moved the other way) | Confirmed for Sep/Oct | Us: grade final outcomes only |
| Pilot sample | August file has 831 requests vs roughly 14,000 in-scope requests a month historically. September looks like one list cut in half | Unexplained | Data owner and us |
| Excel files | Dates in the input files had become Excel numbers | Real, but not the cause for the model: a clean re-score gave the same result | Us: refuse Excel |
| GenAI layer | The rule stopped 1,320 of 1,360 NAN calls before the LLM. The LLM ran on 40 and vetoed none | Not the cause | - |

---

## 4. What we can and cannot change

The GenAI validator only sees requests the primary model calls NAN, and decides which of them to
release. So:
- It cannot release a request the primary model calls Rework. Final NAN recall can never exceed
  the primary model's 69%.
- It cannot improve the primary model's ranking.
- It can decide:
  - the release rule and its threshold;
  - vetoes and scope;
  - which inputs it accepts;
  - when it stops releasing;
  - how results are measured;
  - what it outputs: a closure, a fast-check tier or an explanation.

The validator's own signals have added no precision on top of the primary model's score so far:
- **Similar historical claims** have never improved on the model's score.
- **The LLM** may only allow NAN through SME-approved rules, and its SOP checks were no better
  than chance in the side test.

The validator's value is explanation and blocking clear rule breaks, not raising precision.

---

## 5. Action plan

### A. Safety and honesty: week 1 (19-25 Nov), validator code

| # | Action | Why | Effect |
|---|---|---|---|
| A1 | A release switch with three modes (off / shadow / live) that covers every release path | Today, switching the rule off silently falls back to an older vote-based release, and the standalone check can release without the model's score | No unintended closures |
| A2 | One final gate that every NAN passes: scope, drift pause, per-run release cap | Releases through SME rules currently skip the score check | No unintended closures |
| A3 | Automatic switch-off: a rule is live only while the lower end of its 95% range is above the agreed pass mark | Stops any rule whose evidence is too weak. With a cost ratio of 5 or more, today's rule switches itself off | Wrong closures -> 0 until a rule earns it |
| A4 | Honest reason text | Processors were told "correct 87% of the time"; the pilot measured 22.5%. Remove that line. The similar-claims count overstates NAN odds about 4x, because our reference set is half NAN: show it against the real base rate, or drop it | Processors are not misled |
| A5 | Input gate: accept only the CSV from our data-prep script; refuse Excel files and Excel-style dates. It refuses bad files and never alters the model's inputs | Excel turned dates into numbers in the pilot files | Clean inputs |
| A6 | Every output row records the mode, rule version, model version and data version | Audit and comparison | - |

Owner: GenAI validator team. Effort: about 3 days, including tests. Cost: none.

### B. Measurement we can trust: week 1, no cost

| # | Action | Detail |
|---|---|---|
| B1 | Define when an outcome is final | Use the label changes between the earlier and later extracts to fix the age at which outcomes stop changing. Current estimate: 60-70 days |
| B2 | Corrected pilot readout | Final outcomes only; the full monthly population from our data-prep export, not hand-selected files; clean CSV; 95% ranges; the "close nothing" baseline. Re-grade September when a refreshed extract is available |
| B3 | Explain the pilot population | Confirm with the data owner how the new table and the three pilot files were selected |
| B4 | One standard one-page report per run | The same KPIs every time (section 6) |
| B5 | Start the daily shadow as soon as daily data arrives | Scores and evidence are logged and nothing is closed. Within days it shows how the release band behaves on fresh requests, and its outcomes start maturing now for the final check |

What to expect: September precision should rise somewhat as outcomes become final, but not to the
bar. Even if half of the 22 wrong September closures later turn out to be NAN, overall precision
would be about 50%.

### C. Decisive test: can auto-close work in production? Weeks 2-3 (26 Nov - 9 Dec), no LLM cost

| # | Action | Detail |
|---|---|---|
| C1 | Pre-registration: one page, approved by you before anything runs | Data windows; candidate rules (release thresholds 0.05-0.20, with and without scope exclusions); pass mark; minimum number of releases; stop rule |
| C2 | As-of-opening replay | Requests from Jan-Jun 2026 that the primary model never trained on, rebuilt from only the processing records dated before each request opened, then scored by the unchanged primary model. The rule is chosen on Jan-Apr and confirmed once on May-Jun. We run it in every version of what the daily feed may contain (provider comments and request reason present or blank), and the rule must pass in each |
| C3 | Out-of-period confirmation, only if C2 passes | The frozen rule, run once, on all in-scope requests from August onwards, rebuilt the same way. Pilot requests are reported separately |
| C4 | Side check on the same rows | Does the similar-claims evidence add anything beyond the model's score? |

Data access is read-only. The primary model is used exactly as delivered; the replay only
imitates what production will send it.

**Gate 1 (9 Dec):** if it passes, go to workstream D. If it fails, stop auto-close and go to E2
and F.

### D. Release rule v4: only if Gate 1 passes, weeks 4-6

| # | Action | Detail |
|---|---|---|
| D1 | New release threshold from C2 | Expected to be much stricter than 0.30 |
| D2 | Scope | Exclude groups that are almost never NAN (internal requests, ABA) if C2 confirms it |
| D3 | Drift breaker on every daily run | Compare release share, score distribution and request mix with the calibration. Outside the limits, releases pause automatically and the report says why |
| D4 | Quality sample | A processor checks a fixed share of releases before closure, so a failing rule is caught in 1-2 weeks instead of 2 months |
| D5 | Shadow on the daily feed | No closures until about 200 shadow releases have final outcomes; then Gate 3 |

### E. GenAI layer improvements: in parallel, weeks 2-6

| # | Action | Effect |
|---|---|---|
| E1 | LLM reliability. 15.5% of calls failed in the side test. Log the exact error type, then fix each cause: output budget, safety filter, or retries with a shorter timeout | Fewer failures and lower cost; precision does not change |
| E2 | Fast-check lane. Requests the primary model calls NAN are ranked into tiers with an SOP-cited explanation, and a processor decides | The value is processor time saved: the primary model's NAN calls held 69% of all NAN requests in 27% of volume. Needs Claims Ops' agreement and a timed trial against a control queue (same order, no GenAI text) |
| E3 | Rebuild the similar-claims reference set as of opening | Only if C4 shows that it adds information |
| E4 | SME-reviewed rules that settle specific cases as NAN | When SME time is available. Each rule must pass the same bar |

### F. Recommendation to the primary model's owners (not our change)
- Retrain on information available when a request opens. That means no history from after
  opening (rework adjustment codes, later statuses, netted amounts), and no fields that are
  filled in later (provider comments, according to Claims Ops).
- Split training and test data by time, and report on later months with final outcomes.
- Our replay (C2) can serve as their test harness.

This is the only lever that can bring back auto-close volume. The decision and timeline are
theirs.

---

## 6. How we will judge success (fixed before any new result)

**Pass mark from cost.** If one wrong closure costs as much as r manual reviews, auto-close saves
effort only when precision is above r / (r + 1):

| Cost of one wrong closure (r) | Precision needed |
|---|---|
| 5 reviews | 83.3% |
| 10 reviews | 90.9% |
| 20 reviews | 95.2% |

**Rule:** the lower end of the 95% range, not the point estimate, must clear the pass mark, on at
least about 200 releases with final outcomes.

**KPIs in every report**, always shown next to "close nothing":
- release precision, with its 95% range;
- release volume, as a % of requests;
- wrong closures per 1,000 requests;
- net effort saved = correct closures - r x wrong closures (in review-equivalents);
- share of decisions with an SOP-cited explanation;
- LLM failure rate;
- cost per request.

**Not used on their own:** overall accuracy, Rework precision and Rework recall. All three are
high whenever about 90% of requests need rework.

---

## 7. Timeline and decision gates

| Date | Milestone | Decision |
|---|---|---|
| Wed 25 Nov | Safety changes (A) done; corrected readout (B2); cost ratio r and pre-registration agreed | Gate 0: start the test |
| Wed 9 Dec | Replay result (C2) | Gate 1: continue, or stop auto-close and move to the fast-check lane |
| Mid Dec | Out-of-period confirmation (C3), if the data owner can provide the records from before each request opened | Gate 2: start the scoped shadow on the daily feed |
| Feb-Mar 2027 | About 200 shadow releases with final outcomes | Gate 3: limited auto-close with a quality sample, or stop |

---

## 8. Expected impact on the numbers

| Lever | Number it moves | Expected change | Confidence |
|---|---|---|---|
| Shadow mode, final gate, automatic switch-off (A) | Wrong auto-closures | 31 per 5,034 -> 0 while testing | Certain |
| Correct measurement (B) | Reported precision | September rises somewhat; August stays about 25%; overall still far below the bar | High |
| Recalibrated, scoped rule (D), only if Gate 1 passes | Release precision | At or above the agreed bar, or no releases at all | Unknown until Gate 1 |
| Same | Release volume | Small: a few percent of requests at most | Medium |
| LLM reliability (E1) | Failed calls, cost | 15.5% -> low; precision unchanged | High |
| Fast-check lane (E2) | Processor time on likely-NAN requests | Unknown; needs a timed trial | Unknown |
| Primary model retrain (F, owners) | Ranking and auto-close volume | The only lever that can restore volume | Outside our control |

---

## 9. Risks and how we handle them

| Risk | Handling |
|---|---|
| The new table lacks records from before each request opened, so August cannot be rebuilt | Gate 1 uses the older table. Ask the data owner for the missing records before Gate 2 |
| The daily feed has blank provider comments or request reason at opening | Confirm with the data owner. Test every variant; the rule must pass in each |
| Small numbers give wide ranges | Minimum of about 200 releases; decide on the lower end of the range |
| Tuning on pilot rows creates a fake improvement | Pre-registration. Pilot rows are used for diagnostics only |
| Excel re-enters the pipeline | Input gate (A5) |
| Outcome definitions differ between extracts | Already checked on 941 overlapping requests: changes run almost entirely from rework to NAN (119 vs 3), which is maturing, not a rule change. Re-check on each new extract |

---

## 10. What we will not do

- Change the primary model, its threshold or its inputs.
- Choose rules or thresholds on the Aug-Sep pilot rows and then quote those rows as proof.
- Raise the release threshold to show more volume.
- Spend effort on prompts or a bigger LLM to raise precision. The LLM cannot add ranking.
- Report accuracy without the "close nothing" baseline next to it.
- Use Excel anywhere in the pipeline.
- Write anything to the Databricks tables. Access is read-only.

---

## Glossary

- **Request (ORS):** a provider's request for review of a claim.
- **NAN:** no action needed. **Rework:** any action needed; a processor handles it.
- **Release / auto-close:** the pipeline outputs NAN, so no processor review is needed.
- **Precision:** the share of releases that were truly NAN. **Recall:** the share of all NAN
  requests that were released.
- **Final (mature) outcome:** an outcome old enough that it no longer changes (about 60-70 days,
  to be confirmed in B1).
- **As-of-opening:** the request and claim exactly as they looked on the day the request opened.
- **Shadow mode:** the pipeline runs and logs its decisions, but nothing is closed.
- **r:** the cost of one wrong closure, measured in manual reviews.

