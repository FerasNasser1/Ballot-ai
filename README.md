
# Baloot بلوت
**[▶ Play Baloot in your browser | العب بلوت الآن](https://ferasnasser1.github.io/Ballot-ai/)**
Saudi **Baloot** against three AI players: you and your AI partner against two AI opponents.
The agents combine several classic AI techniques: constraint satisfaction, a logical knowledge
base, Monte Carlo sampling of the hidden cards, and alpha-beta search.

Play it two ways: a **desktop app** (Python + PyQt6) or in your **browser** with no install at all.

Built for **CSC 361 (Artificial Intelligence), King Saud University** by

| Team |
|---|
| Feras Nasser AlNasser |
| Mohammed Abdulrahman Alrabiah |
| Naif Mohammed Alanazi |

<!-- Add a screenshot after your first run: save it as docs/screenshot.png -->
<!-- ![Baloot table](docs/screenshot.png) -->

## Contents

- [Quick start](#quick-start)
- [Play in the browser](#play-in-the-browser)
- [How to play](#how-to-play)
- [Rules implemented](#rules-implemented)
- [How the AI works](#how-the-ai-works)
- [Evaluation](#evaluation)
- [Project structure](#project-structure)
- [Running the tests](#running-the-tests)
- [Limitations and future work](#limitations-and-future-work)
- [References](#references)

## Quick start

Requires Python 3.9 or newer.

```bash
git clone https://github.com/FerasNasser1/baloot-ai.git
cd baloot-ai
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Options:

```bash
python main.py --samples 50 --think-time 2   # stronger, slower AI
python main.py --seed 7                      # reproducible deals
```

## Play in the browser

The `docs/` folder is a complete browser version of the same game: the rules, the scoring and the
AI are ported to JavaScript and run entirely on your machine. There is no server, no build step
and no dependencies.

* **Locally:** open `docs/index.html` in any browser.
* **Online, free:** push this repository to GitHub, then open *Settings → Pages*, choose
  *Deploy from a branch*, branch `main` and folder `/docs`. After a minute the game is live at
  `https://FerasNasser1.github.io/baloot-ai/`.

The browser version and the Python version are kept in step by parity tests: the Python engine
records complete hands, and the JavaScript engine has to reproduce every legal-move list, every
knowledge-base state and every score (see [Running the tests](#running-the-tests)).

## How to play

You sit at the bottom. Your partner sits opposite, the opponents to your right and left. Play
passes to the right (counter-clockwise). The dealer changes every round, and the player to the
dealer's right bids first and leads the first trick.

1. **Mushtra (bidding).** Everyone gets five cards and one card is turned face up (the ground
   card). In the first round each player may buy **Sun** (no trump), **Hokom** (the ground card's
   suit is trump), call **Ashkal**, or pass. Sun outranks Hokom, so after a Hokom bid everyone
   else gets one chance to take the hand with Sun. If all four pass, a second round allows Hokom
   in another suit (حكم ثاني). If everyone passes again, the cards are redealt.
2. **Ashkal (أشكل).** Only the dealer and the player on the dealer's left may call it. The
   contract is Sun, but the ground card goes to the caller's *partner*. The caller is still the
   buyer.
3. **Doubling.** Once the rest of the cards are dealt, a Hokom hand can be raised:
   **Double (دبل)** by a defender, **Three (ثري)** by the buyer, **Four (فور)** by the doubler and
   **Qahwa (قهوة)** by the buyer. A Double or a Four may be *closed* (مقفل), which means nobody
   may lead a trump unless their whole hand is trumps.
4. **Play.** Point at a card in your hand; playable cards rise and cards you cannot play are
   dimmed. Trump cards carry a small saffron dot.
5. **Declarations (Mashari).** Sequences and four-of-a-kinds are found automatically and shown
   after the first trick.
6. **Scoring.** Each round's points go on the score sheet. The first team to 152 wins — unless
   somebody calls Qahwa, which decides the match in a single hand.

The panel under the score sheet lists what your partner has deduced, for example that a player is
out of a suit. It uses only public information, so it never reveals hidden cards.

## Rules implemented

| Rule | Implementation |
|---|---|
| Deck | 32 cards, 7 to Ace |
| Card order in Hokom, trump suit | J, 9, A, 10, K, Q, 8, 7 |
| Card order otherwise | A, 10, K, Q, J, 9, 8, 7 |
| Card points | Trump J = 20, 9 = 14; A = 11, 10 = 10, K = 4, Q = 3, J = 2 otherwise; last trick +10 |
| Bidding | Sun, Hokom, Hokom thani, Ashkal, pass. Sun overcalls a Hokom bid; priority goes to the seat closest to the dealer's right |
| Ashkal (أشكل) | Dealer and dealer's left only; contract is Sun; the ground card goes to the caller's partner; the caller is the buyer |
| Playing | Follow suit. In Hokom, over-trump when trump is led; if void and your partner isn't winning, trump and over-trump if possible |
| Closed play (مقفل) | No player may lead a trump unless holding nothing but trumps |
| Round points | Hokom: card points ÷ 10, total 16. Sun: card points ÷ 5, total 26 |
| Rounding | Only the counting team converts; a trailing 5 rounds **down** in Hokom and is **not rounded** in Sun (art. 4-11) |
| Who counts | The buyer's opponents; after a raise, the opponents of the team that raised last (art. 4-10) |
| Projects (Hokom / Sun points) | Sira (3 in a row) 2 / 4, Fifty (4) 5 / 10, Hundred (5+, or four 10s/Js/Qs/Ks) 10 / 20, four Aces 10 / 40, Baloot (K+Q of trump, Hokom only) 2 |
| Declarations | Only the team with the best project scores its projects; Baloot always counts |
| Failed purchase | If the buying team does not win the hand, the other team takes all of its points |
| Double / Three / Four | Card points ×2 / ×3 / ×4 to the winner of the hand, projects ×2 at most, Baloot never multiplied (arts. 5-4, 5-5) |
| Ties in a raised hand | Decided on rounding; an exact tie goes against the team that raised (art. 7-6) |
| Double in Sun | Allowed only when the defenders have ≤100 points and the buyers >100; no Three, Four or closed play (arts. 7-1, 7-2) |
| Qahwa (قهوة) | The team that wins the hand wins the whole match (art. 7-4) |
| Match | First team to 152 |

Article numbers refer to the Saudi Mind Sports Federation rules for Baloot; the step-by-step
scoring procedure follows the same rules as documented on [pagat.com](https://www.pagat.com/jass/baloot.html).
`tests/test_scoring.py` encodes every buyer-failure threshold in articles 4-2 to 4-9 and all eight
worked scoring examples from pagat.

**Regional variations.** Baloot differs from majlis to majlis, so some choices had to be made:

- Ashkal is allowed whenever Sun is, for the two eligible seats. The federation's stricter reading
  (art. 8-1), which allows Ashkal only after the *opposing* team has bid Hokom, is available with
  `GameEngine(ashkal_requires_hokom=True)`.
- A Double is open unless the doubler asks for closed play (art. 7-5). Some tournaments make a
  Double closed by default.
- A player who is overcalled cannot take a Sun bid back (سحب), and declaration ties score nothing.
- Kaboot (winning all eight tricks) is scored like any other hand, not with the special 25/44.
- Baloot scores when it is held rather than when the second card is played.

## How the AI works

Each AI seat is a `BalootAgent` (see `baloot/agent.py`). Every time it must play a card:

```
cards played so far ──► Knowledge base ──► CSP deal sampler ──► alpha-beta on each sampled deal ──► average ──► card
                         (what is proven)     (possible deals)       (value of each legal card)
```

| Technique | Course chapter (AIMA) | Where | What it does |
|---|---|---|---|
| Constraint satisfaction | Ch. 6 | `rules.legal_moves`, `sampler.py` | Legal moves are the cards that satisfy the follow-suit, trump, over-trump and closed-play constraints. Hidden hands are sampled by solving a CSP. |
| Logical agent / knowledge base | Ch. 7–8 | `knowledge.py` | Derives facts about hidden hands from each play using the inference rules below. |
| Adversarial search | Ch. 5 | `search.py` | Alpha-beta with team-based max/min, searching across trick boundaries. |
| Search under uncertainty | Ch. 5 | `agent.py` | Perfect Information Monte Carlo (PIMC): solve many sampled deals and average. |
| Monte Carlo evaluation | Ch. 5 | `escalation.py` | Double / Three / Four / Qahwa decisions from simulated play-outs of sampled deals. |
| Machine learning (optional) | Ch. 19 | `bidding.py` | A trained bidding model, if `models/mushtra_model.pkl` exists. Otherwise a hand-strength heuristic. |

### Knowledge base inference rules

Every rule is derived from the play rules, which all seats must obey, so every conclusion is
guaranteed to hold for the real deal. `tests/test_knowledge.py` checks this over complete games,
including doubled and closed ones.

| Rule | Trigger | Conclusion |
|---|---|---|
| R1 | Player does not follow the lead suit | Void in that suit |
| R2 | Hokom, non-trump lead, partner not winning, player discards a non-trump | Also void in trump |
| R3 | Hokom, player plays a trump that doesn't beat the highest trump on the table when over-trumping was compulsory | Holds no trump above that card |
| R4 | A declaration is revealed | Those cards are in that player's hand |
| R5 | A card is played | It is no longer in anyone's hand |
| R6 | The contract is settled | The ground card is in the hand of the player who took it (the buyer, or the partner after Ashkal) |
| R7 | Closed game, a player **leads** a trump | That player holds nothing but trumps, so is void in the other three suits |

### Deal sampling as a CSP

| Part | Definition |
|---|---|
| Variables | Each card whose location the agent doesn't know |
| Domains | The three other players |
| Constraints | Void suits (R1, R2, R7), excluded trumps (R3), cards known to be in a hand (R4, R6), exact hand sizes |
| Solver | Randomized backtracking with the minimum-remaining-values heuristic and forward checking |

Randomizing the order in which players are tried gives a different consistent deal each time. The
samples are not perfectly uniform over all consistent deals; this is an accepted approximation.

### Search

For each sampled deal, `TrickSearch` computes the exact value of every legal card with alpha-beta
pruning.

- **Horizon:** the current trick plus one more. Once four or fewer cards remain, it searches to the
  end of the hand.
- **Evaluation:** points won by the agent's team minus points won by the opponents, including the
  last-trick bonus.
- **Max or min:** decided by team, because after a trick ends the winner leads, so simply
  alternating turns would be wrong.
- **Move choice:** the card with the best average over all samples. Ties go to the cheaper card.

A known weakness of PIMC is *strategy fusion*: each sample is solved as if all cards were visible,
so the agent can assume it will "know" things it cannot know (Frank & Basin, 1998). In practice it
works well in trick-taking games (Ginsberg, 2001; Long et al., 2010).

### Deciding a Double, Three, Four or Qahwa

`escalation.py` estimates what each call is worth instead of using a rule of thumb:

1. A knowledge base holds what is public: the agent's own hand and the ground card's owner.
2. The CSP sampler draws complete deals consistent with it. Deals are **rejection-sampled against a
   model of the other calls**: the buyer's hand must be strong enough for the contract it bought
   (the same hand-strength measure the bidding heuristic uses), and a doubler's hand must show some
   trump strength. Without this the samples would ignore what the bidding revealed.
3. Each sampled deal is played out greedily, open and closed, and scored at every level the call
   could lead to.
4. The call with the best average point difference wins, but a raise must beat passing by a margin
   of 4 game points, because the estimate is noisy and ignores the opponents' chance to re-raise.

A Qahwa is valued as the points still needed to win the match, or the points the opponents still
need if it is lost.

## Evaluation

`simulate.py` plays AI teams against baselines without the GUI. Every deal is played twice with
the teams swapped between seats, so both sides get the same cards and luck largely cancels out.

```bash
python simulate.py --rounds 60  --opponent greedy --samples 10 --budget 0.15
python simulate.py --rounds 40  --opponent random --samples 10 --budget 0.15
python simulate.py --rounds 60  --opponent greedy --samples 10 --budget 0.15 --no-doubling
```

Results from development runs (10 samples, 0.15 s per decision, one CPU core):

| AI team vs | Rounds | Mean round-point difference | 95% CI | Rounds won |
|---|---|---|---|---|
| Random legal moves | 80 | +4.70 | +2.47 to +6.93 | 57.5% |
| Greedy (win cheaply, else discard cheapest) | 120 | +1.38 | +0.12 to +2.64 | 50.8% |
| Greedy, no doubling allowed | 120 | +1.22 | −0.08 to +2.52 | 50.0% |

The greedy player is a surprisingly strong baseline and the AI's margin over it is small. As a
diagnostic, an agent allowed to see every hand (no sampling) scored only about +2.6 against greedy
with the two-trick horizon and +1.1 with a one-trick horizon, so the **search horizon, not the
sampling, is the main limit on strength**. Deeper search and a better evaluation function are the
most promising improvements.

**Honest note on doubling.** In these runs the AI almost never doubled, and that is the correct
behaviour rather than a broken advisor. `calibrate_doubling.py` measures it directly over 69 Hokom
hands: a defender's Double would really have *lost* 27.1 points per hand on average (the advisor
estimated −24.4 and declined every time), because a hand bought on a sound bidding rule usually
succeeds. When the AI is the one being doubled, answering Three really gained +15.5 points per hand
(estimated +12.5), and the advisor calls Three in 93% of those positions. So the doubling machinery
shows up mostly as a well-calibrated refusal to raise, plus a confident Three when a human doubles
the AI.

```bash
python calibrate_doubling.py --hands 200     # reproduces those two numbers
```

Your numbers will vary with `--samples`, `--budget` and machine speed. Re-run before quoting them.

## Project structure

```
baloot-ai/
├── main.py                   # start the desktop game
├── simulate.py               # headless evaluation against baselines
├── calibrate_doubling.py     # are the doubling decisions any good?
├── baloot/
│   ├── cards.py              # Card, deck helpers
│   ├── rules.py              # trick winner, legal moves (CSP), points, projects
│   ├── scoring.py            # round scoring: failed buyer, Double/Three/Four/Qahwa
│   ├── knowledge.py          # knowledge base and inference rules R1–R7
│   ├── sampler.py            # CSP sampler for hidden hands
│   ├── search.py             # alpha-beta search
│   ├── agent.py              # PIMC agent and baseline players
│   ├── policies.py           # greedy policy shared by baselines and rollouts
│   ├── bidding.py            # Mushtra: ML model or heuristic, including Ashkal
│   ├── escalation.py         # the doubling ladder and its Monte Carlo advisor
│   ├── engine.py             # bidding, doubling, play and scoring (no GUI code)
│   ├── autoplay.py           # drives a hand for simulations and tests
│   └── gui/                  # PyQt6 desktop interface
├── docs/                     # the browser version (GitHub Pages serves this folder)
│   ├── index.html
│   ├── baloot.js             # the whole engine and AI, ported to JavaScript
│   ├── app.js                # the table, the score sheet and the dialogs
│   └── style.css
├── report/REPORT.md          # the project report
├── models/                   # optional mushtra_model.pkl
└── tests/                    # Python unittest suite plus the JavaScript parity tests
```

The engine has no GUI code at all, so the rules, AI and scoring can be tested and evaluated
without a window.

## Running the tests

```bash
python -m unittest discover -s tests -t .    # 83 tests: rules, scoring, bidding, doubling, knowledge
node --test                                  # JavaScript port against the Python fixture
python tests/web/make_fixture.py             # refresh the fixture after changing the rules
```

No extra packages are needed for either suite; `pytest` also works if you have it. Both run in CI
on every push.

## Limitations and future work

- The search horizon limits strength (see [Evaluation](#evaluation)). Options include deeper search
  with a transposition table, a learned evaluation function, or Information Set MCTS
  (Cowling, Powley & Whitehouse, 2012).
- Bidding still looks only at hand strength; it does not read the other players' bids the way the
  doubling advisor reads the contract.
- The doubling advisor plays its samples out greedily, which flatters the buying team; a stronger
  roll-out policy would make its estimates less biased.
- The regional variations listed above, and Kaboot in particular, are not scored specially.
- Rules for saying "Ekka" and the third player's duty to trump when the partner leads a low card
  are simplified.

## References

- Russell, S. & Norvig, P. *Artificial Intelligence: A Modern Approach*, 4th ed.
- Saudi Mind Sports Federation, *General regulations for Baloot* (اللائحة العامة للعبة البلوت).
- McLeod, J. [Baloot](https://www.pagat.com/jass/baloot.html), pagat.com, 2021.
- Ginsberg, M. L. (2001). GIB: Imperfect information in a computationally challenging game. *Journal of Artificial Intelligence Research*, 14, 303–358.
- Frank, I. & Basin, D. (1998). Search in games with incomplete information: a case study using Bridge card play. *Artificial Intelligence*, 100, 87–123.
- Long, J., Sturtevant, N., Buro, M. & Furtak, T. (2010). Understanding the success of perfect information Monte Carlo sampling in game tree search. *AAAI*.
- Cowling, P., Powley, E. & Whitehouse, D. (2012). Information Set Monte Carlo Tree Search. *IEEE Transactions on Computational Intelligence and AI in Games*, 4(2), 120–143.

## License

MIT. See [LICENSE](LICENSE).
