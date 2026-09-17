# Intelligent Baloot: an AI player for the Saudi card game

**CSC 361 — Artificial Intelligence, King Saud University**

| Team members |
|---|
| Feras Nasser AlNasser |
| Mohammed Abdulrahman Alrabiah |
| Naif Mohammed Alanazi |

---

## 1. Overview

Baloot (بلوت) is the most widely played card game in Saudi Arabia: four players in two fixed
partnerships, 32 cards, eight tricks a hand, and a match to 152 points. It is a game of
*imperfect information* — each player sees only their own eight cards — which makes it a natural
setting for the techniques of this course.

We built a complete Baloot player. A human sits at one seat; the other three seats, including the
human's partner, are played by an agent that combines four techniques from the course: constraint
satisfaction, a logical knowledge base, adversarial search with alpha-beta pruning, and Monte
Carlo sampling for decisions under uncertainty. The game runs as a desktop application
(Python + PyQt6) and as a browser version (JavaScript) that needs no installation.

Objectives:

1. Implement the rules of Saudi Baloot faithfully, including the bidding calls **Ashkal** and the
   doubling ladder **Double, Three, Four and Qahwa**, which change both the scoring and the legal
   moves.
2. Build an agent that plays legally, reasons about hidden cards using only public information,
   and chooses cards by search rather than by rules of thumb.
3. Measure the agent honestly against baselines rather than asserting that it "plays well".

## 2. Rules implemented, and where they come from

Baloot has no single canonical rule book, and majlis rules differ. We used the **Saudi Mind Sports
Federation regulations** as the primary source, with the detailed description on **pagat.com** for
the procedures the regulations state only as outcomes. Where sources conflict we chose one,
documented the choice, and where it was cheap we made it configurable.

### 2.1 Bidding and Ashkal (أشكل)

Bidding starts to the dealer's right. In the first round a player may pass, buy **Hokom** (the
ground card's suit becomes trump), buy **Sun** (no trump), or call **Ashkal**. Sun outranks Hokom,
so after a Hokom bid every other player gets one chance to take the hand with Sun, with priority to
the seat nearest the dealer's right. If all four pass, a second round allows Hokom in another suit
(حكم ثاني). If everyone passes again, the deal is void.

**Ashkal** is a Sun bid with a twist: the ground card goes to the *caller's partner* rather than to
the caller, though the caller remains the buyer for scoring. Only the dealer and the player on the
dealer's left may call it.

The sources disagree on one condition. Federation article 8-1 permits Ashkal only after the
*opposing* team has bid Hokom; pagat and most popular guides allow it whenever it is that seat's
turn. We made the permissive reading the default and the federation reading an option
(`ashkal_requires_hokom=True`), because the two behave identically in the common case and a
tournament setting may need the stricter rule.

### 2.2 Doubling: Double, Three, Four, Qahwa

Once the remaining cards are dealt and before the first card is led, a Hokom hand can be raised:

| Call | Arabic | Who calls it | Effect |
|---|---|---|---|
| Double | دبل | either defender | hand is worth ×2 |
| Three | ثري | the buyer | ×3 |
| Four | فور | the doubler | ×4 |
| Qahwa | قهوة | the buyer | the team that wins the hand wins the whole match |

After the first Double only the buyer and the doubler speak (art. 7-5). A Double or a Four may be
declared **closed** (مقفل), which changes the legal moves: no player may *lead* a trump unless
their hand is nothing but trumps. Three and Qahwa are always open.

In Sun only Double exists, and only when the defending team has 100 points or fewer while the
buying team has more than 100 (arts. 7-1, 7-2).

### 2.3 Scoring

The scoring procedure has a subtlety that is easy to get wrong. Only one team — the *counting
team* — converts its card points to game points; the other team receives the remainder of 16
(Hokom) or 26 (Sun). This keeps the total fixed despite rounding. The counting team is normally the
buyer's opponents, but after a raise it is the opponents of whichever team raised last (art. 4-10).
A trailing 5 rounds **down** in Hokom and is **not rounded** in Sun (art. 4-11).

The team with more game points wins the hand. On a tie, the team that lost more card points in the
rounding wins; if that is equal too, the buyer's team wins, which is the same as saying that a tie
loses for the doubler (art. 7-6). When a hand is raised, the winner takes everything: card points
×2, ×3 or ×4, projects doubled at most, and Baloot always exactly 2 (arts. 5-4, 5-5).

**A bug this uncovered.** While implementing the doubling rules we found that the existing rounding
code rounded a trailing 5 *upwards*. The consequence was visible: the federation states that the
buyer loses in Hokom when the defenders reach 82, and in Sun at 66, but the old code let the buyer
survive both. Because doubling multiplies whatever the base scorer produces, this had to be fixed
first. The corrected procedure now reproduces **all nine** buyer-failure thresholds in articles 4-2
to 4-9 and all eight worked examples published on pagat, which are encoded as unit tests
(`tests/test_scoring.py`).

## 3. Architecture

```
                 ┌──────────────┐        ┌──────────────┐
   PyQt6 GUI ───►│              │◄────── │  simulate.py │
   (desktop)     │  GameEngine  │        │  (headless)  │
   browser UI ──►│  bidding →   │        └──────────────┘
   (JavaScript)  │  doubling →  │
                 │  play → score│◄────── BalootAgent ×3
                 └──────────────┘             │
                                   ┌──────────┼───────────┬─────────────┐
                              knowledge.py  sampler.py  search.py   escalation.py
                              (logic)       (CSP)       (alpha-beta)  (Monte Carlo)
```

The engine contains no interface code, so the same rules and scoring drive the desktop game, the
browser game, the simulations and the tests. `autoplay.py` drives a complete hand for the headless
users.

## 4. The AI

### 4.1 Legal moves and deal sampling as constraint satisfaction (AIMA ch. 6)

Legal moves are the cards satisfying the follow-suit, trump, over-trump and closed-play
constraints. Sampling the hidden cards is a genuine CSP: the **variables** are the cards whose
location the agent does not know, the **domains** are the three other players, and the
**constraints** are the void suits, the excluded trumps, the cards known to be held, and each
player's exact hand size. It is solved by randomized backtracking with the minimum-remaining-values
heuristic and forward checking, giving a different consistent deal on each call.

### 4.2 A knowledge base of proven facts (AIMA ch. 7–8)

Rather than guess, the agent records only what follows logically from the play rules, which every
seat must obey:

| Rule | Trigger | Conclusion |
|---|---|---|
| R1 | A player does not follow the lead suit | Void in that suit |
| R2 | Hokom, non-trump lead, partner not winning, a non-trump discarded | Also void in trump |
| R3 | A trump played that fails to beat the table when over-trumping was compulsory | Holds no higher trump |
| R4 | A declaration is revealed | Those cards are in that hand |
| R5 | A card is played | It is in nobody's hand |
| R6 | The contract is settled | The ground card is held by whoever took it |
| R7 | Closed game, a player *leads* a trump | That player holds nothing but trumps |

R6 and R7 were added with the new rules. R7 is a good example of the rules and the reasoning
interacting: because closed play forbids leading a trump unless the hand is all trumps, a trump
lead *proves* the leader is void in the other three suits — a strong deduction that only exists
because of the Double.

Soundness is tested, not assumed: over complete games (including doubled and closed ones) every
knowledge base must agree with the real deal at every point, and every sampled deal must satisfy
it.

### 4.3 Alpha-beta search and PIMC (AIMA ch. 5)

Each sampled deal is a perfect-information game, solved exactly with alpha-beta pruning across
trick boundaries. Maximising and minimising are decided by *team*, not by alternating plies,
because the winner of a trick leads the next one. The agent then averages each card's value over
many sampled deals — Perfect Information Monte Carlo, as used by GIB for bridge. Its known
weakness, *strategy fusion*, is discussed in the README.

### 4.4 Deciding a Double, Three, Four or Qahwa

A raise is a decision under uncertainty with a large payoff swing, so we evaluate it rather than
use a rule of thumb. The advisor samples consistent deals, plays each out with a greedy policy,
scores it at every level the call could lead to, and picks the call with the best average point
difference, requiring a margin of 4 points over passing.

One detail matters: naive sampling ignores what the bidding revealed. We therefore
**rejection-sample against a model of the other players' calls** — the buyer's hand must be strong
enough for the contract it bought, and a doubler's hand must show trump strength. This is a simple
form of opponent modelling.

## 5. Two implementations, kept honest by parity tests

The browser version is a second implementation of the same rules, so it could drift from the
Python one. To prevent that, the Python engine records complete hands — the deal, every call, every
card, the knowledge base after each trick and the final score — and the JavaScript engine replays
them. It must offer the same bidding options, allow exactly the same cards, reach the same
knowledge-base state and produce the same score. The recording covers all five levels from an
undoubled hand to Qahwa.

## 6. Testing and results

| Suite | What it covers |
|---|---|
| 83 Python tests | trick rules, legal moves incl. closed play, projects, all federation thresholds and pagat examples, bidding and Ashkal eligibility, the doubling ladder, knowledge soundness, full matches |
| 7 JavaScript tests | 400 legal-move cases, 150 project cases, 600 scoring cases, 30 replayed hands, plus AI self-play |

`simulate.py` plays each deal twice with the teams swapped, so both sides get identical cards and
most of the luck cancels.

| AI team vs | Rounds | Mean round-point difference | 95% CI | Rounds won |
|---|---|---|---|---|
| Random legal moves | 80 | +4.70 | +2.47 to +6.93 | 57.5% |
| Greedy baseline | 120 | +1.38 | +0.12 to +2.64 | 50.8% |
| Greedy, doubling disabled | 120 | +1.22 | −0.08 to +2.52 | 50.0% |

The agent beats random play clearly and greedy play by a small but positive margin. We do not
claim more than that: greedy is a strong baseline in a game where following suit is compulsory most
of the time, and a diagnostic run in which the agent was allowed to see all four hands scored only
about +2.6 against greedy. That tells us the **search horizon, not the hidden information, is the
binding constraint** on playing strength.

**Does the doubling advisor work?** In whole-match simulations it almost never doubles, which looks
like a broken feature until it is measured. `calibrate_doubling.py` compares the advisor's estimate
with what actually happens:

Over 69 Hokom hands (300 deals):

| Decision | Advisor's estimated gain | Actual gain if always taken | Advisor took it |
|---|---|---|---|
| Defender doubles instead of passing | −24.4 points | −27.1 points | 0% of hands |
| Buyer answers a Double with Three | +12.5 points | +15.5 points | 93% of hands |

The estimates track reality closely. A defender's Double really is a losing call against a hand
bought on a sound bidding rule, and answering Three when doubled really is worth about fifteen
points. The refusal to double is therefore the correct output of a well-calibrated evaluator, not a
missing feature. The one caveat is that roll-outs use a greedy policy that favours the buying team,
so the advisor is likely a little too pessimistic about defending.

## 7. Limitations and future work

- **Search horizon.** Two tricks of lookahead is the main limit on strength. A transposition table,
  a learned evaluation function, or Information Set MCTS would all help.
- **Bidding** still looks only at hand strength and ignores what other players have said, even
  though the doubling advisor shows how to use that information.
- **Roll-out bias** in the doubling advisor, as above.
- **Regional variations** — Kaboot's special 25/44 score, the "Ekka" declaration, taking back a Sun
  bid (سحب), and declaration ties — are simplified and documented.

## 8. How to run

```bash
pip install -r requirements.txt
python main.py                               # desktop game
python simulate.py --rounds 60               # evaluation
python calibrate_doubling.py --hands 200     # doubling calibration
python -m unittest discover -s tests -t .    # Python tests
node --test                                  # JavaScript parity tests
```

The browser version is the `docs/` folder: open `docs/index.html`, or publish it with GitHub Pages
(*Settings → Pages → Deploy from a branch → main → /docs*).

## 9. References

1. Russell, S. & Norvig, P. *Artificial Intelligence: A Modern Approach*, 4th ed. Pearson, 2021.
2. Saudi Mind Sports Federation. *General regulations for Baloot* (اللائحة العامة للعبة البلوت).
3. McLeod, J. *Baloot*. pagat.com, 2021. https://www.pagat.com/jass/baloot.html
4. Ginsberg, M. L. (2001). GIB: Imperfect information in a computationally challenging game.
   *Journal of Artificial Intelligence Research*, 14, 303–358.
5. Frank, I. & Basin, D. (1998). Search in games with incomplete information: a case study using
   Bridge card play. *Artificial Intelligence*, 100, 87–123.
6. Long, J., Sturtevant, N., Buro, M. & Furtak, T. (2010). Understanding the success of perfect
   information Monte Carlo sampling in game tree search. *AAAI*.
7. Cowling, P., Powley, E. & Whitehouse, D. (2012). Information Set Monte Carlo Tree Search.
   *IEEE Transactions on Computational Intelligence and AI in Games*, 4(2), 120–143.
