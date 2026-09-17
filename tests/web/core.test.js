/*
 * Checks that docs/baloot.js behaves exactly like the Python engine.
 *
 *   python tests/web/make_fixture.py      # refresh the recording
 *   node --test tests/web/                # run these tests
 *
 * The fixture holds unit cases (legal moves, projects, scoring) and complete
 * recorded hands. Each hand is replayed move by move: at every decision the
 * JavaScript engine must offer the same options, allow the same cards, reach
 * the same knowledge-base state, and score the hand identically.
 */
const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const path = require("path");

const B = require("../../docs/baloot.js");
const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, "fixture.json"), "utf8"));

test("legal moves match the Python rules", () => {
  for (const c of fixture.rules) {
    const moves = B.legalMoves(c.hand, c.table, c.mode, c.trump, c.locked).slice().sort();
    assert.deepStrictEqual(moves, c.legal.slice().sort(),
      `hand ${c.hand} table ${JSON.stringify(c.table)} ${c.mode} ${c.trump} locked=${c.locked}`);
  }
});

test("projects and declarations match", () => {
  for (const c of fixture.projects) {
    const projectsByPid = {};
    for (let p = 0; p < 4; p++) {
      projectsByPid[p] = B.detectProjects(c.hands[String(p)], c.mode, c.trump);
      assert.deepStrictEqual(projectsByPid[p].map((x) => x.name).sort(), c.projects[String(p)]);
    }
    const decl = B.resolveDeclarations(projectsByPid, c.mode);
    assert.strictEqual(decl.winningTeam, c.winningTeam);
    assert.deepStrictEqual(decl.teamPoints, c.teamPoints);
    assert.deepStrictEqual(decl.projectPoints, c.projectPoints);
    assert.deepStrictEqual(decl.balootPoints, c.balootPoints);
  }
});

test("scoring matches at every level", () => {
  for (const c of fixture.scoring) {
    const hs = B.scoreHand(c.mode, c.declarerTeam, c.cardPoints, c.projects, c.baloots, c.level);
    const label = JSON.stringify(c);
    assert.deepStrictEqual(hs.gamePoints, c.gamePoints, label);
    assert.deepStrictEqual(hs.totals, c.totals, label);
    assert.strictEqual(hs.countingTeam, c.countingTeam, label);
    assert.strictEqual(hs.winner, c.winner, label);
    assert.strictEqual(hs.declarerWon, c.declarerWon, label);
    assert.deepStrictEqual(hs.final, c.final, label);
    assert.strictEqual(hs.qahwa, c.qahwa, label);
  }
});

test("the federation rounding rule", () => {
  assert.strictEqual(B.convertCountingPoints(55, B.HOKOM), 5);   // a trailing 5 rounds down
  assert.strictEqual(B.convertCountingPoints(65, B.SUN), 13);    // a trailing 5 is not rounded
  // Art. 4-3: the buyer loses at 82 in Hokom but survives at 81.
  assert.strictEqual(B.scoreHand(B.HOKOM, 0, [80, 82]).declarerWon, false);
  assert.strictEqual(B.scoreHand(B.HOKOM, 0, [81, 81]).declarerWon, true);
  // Art. 4-2: the same at 66 and 65 in Sun.
  assert.strictEqual(B.scoreHand(B.SUN, 0, [64, 66]).declarerWon, false);
  assert.strictEqual(B.scoreHand(B.SUN, 0, [65, 65]).declarerWon, true);
});

function kbState(kb) {
  const sorted = (set) => [...set].sort();
  return {
    voids: [0, 1, 2, 3].map((p) => sorted(kb.voids[p])),
    known: [0, 1, 2, 3].map((p) => sorted(kb.known[p])),
    excluded: [0, 1, 2, 3].map((p) => sorted(kb.excluded[p])),
    playedBy: kb.playedBy.slice(),
    locked: kb.locked,
  };
}

test("recorded hands replay identically", () => {
  let levels = new Set();
  for (const hand of fixture.hands) {
    const kbs = [0, 1, 2, 3].map((p) => new B.KnowledgeBase(p));
    const mirror = {
      newRound: () => kbs.forEach((kb) => kb.reset()),
      observeContract: (...a) => kbs.forEach((kb) => kb.observeContract(...a)),
      observePlay: (...a) => kbs.forEach((kb) => kb.observePlay(...a)),
      observeDeclaration: (...a) => kbs.forEach((kb) => kb.observeDeclaration(...a)),
    };
    const engine = new B.GameEngine([mirror], B.mulberry32(1));
    engine.dealer = (hand.dealer + 3) % 4;
    engine.startRound(hand.deck);
    assert.strictEqual(engine.dealer, hand.dealer);

    for (const step of hand.steps) {
      if (step.type === "bid") {
        assert.strictEqual(engine.currentBidder, step.pid);
        assert.deepStrictEqual(engine.bidOptions().slice().sort(), step.options.slice().sort());
        engine.applyBid(step.pid, step.action, step.trump);
      } else if (step.type === "call") {
        assert.strictEqual(engine.escalationTurn, step.pid);
        assert.deepStrictEqual(engine.escalationOptions(), step.options);
        engine.applyEscalation(step.pid, step.action);
      } else if (step.type === "play") {
        assert.strictEqual(engine.turn, step.pid);
        assert.deepStrictEqual(engine.legalMoves(step.pid).slice().sort(), step.legal.slice().sort(),
          `hand dealer ${hand.dealer}, player ${step.pid}`);
        engine.play(step.pid, step.card);
      } else if (step.type === "trick") {
        const result = engine.resolveTrick();
        assert.strictEqual(result.winner, step.winner);
        assert.strictEqual(result.points, step.points);
        assert.deepStrictEqual(kbState(kbs[1]), step.kb1, "knowledge base after a trick");
      }
    }
    const r = engine.history[engine.history.length - 1];
    const expected = hand.result;
    levels.add(r.level);
    for (const key of ["mode", "trump", "buyer", "ashkal", "level", "locked", "winner",
                       "buyerFailed", "qahwa"]) {
      assert.strictEqual(r[key], expected[key], `${key} of hand dealt by ${hand.dealer}`);
    }
    for (const key of ["cardPoints", "base", "projectPoints", "final", "totalsAfter"]) {
      assert.deepStrictEqual(r[key], expected[key], `${key} of hand dealt by ${hand.dealer}`);
    }
  }
  assert.deepStrictEqual([...levels].sort(), [1, 2, 3, 4, 5], "hands should cover every level");
});

test("the AI plays legal cards and finishes matches", async () => {
  const rng = B.mulberry32(7);
  const agents = {};
  for (let p = 0; p < 4; p++) {
    agents[p] = new B.BalootAgent(p, { samples: 4, timeBudget: 0.05, escalationSamples: 4, rng });
  }
  const engine = new B.GameEngine(Object.values(agents), rng);
  let hands = 0;
  while (engine.phase !== B.Phase.MATCH_OVER && hands < 40) {
    engine.startRound();
    while (engine.phase === B.Phase.BIDDING) {
      const pid = engine.currentBidder;
      const [action, trump] = agents[pid].chooseBid(engine.hands[pid], engine.publicCard,
                                                    engine.bidRound, engine.bidOptions());
      engine.applyBid(pid, action, trump);
    }
    if (engine.phase === B.Phase.ROUND_OVER) continue;     // redeal
    while (engine.phase === B.Phase.DOUBLING) {
      const pid = engine.escalationTurn;
      engine.applyEscalation(pid, agents[pid].chooseEscalation(engine.escalationView(pid)));
    }
    while (engine.phase === B.Phase.PLAYING || engine.phase === B.Phase.TRICK_COMPLETE) {
      if (engine.phase === B.Phase.TRICK_COMPLETE) { engine.resolveTrick(); continue; }
      const pid = engine.turn;
      const card = await agents[pid].chooseCard(engine.viewFor(pid));
      assert.ok(engine.legalMoves(pid).includes(card), "AI picked an illegal card");
      engine.play(pid, card);
    }
    hands += 1;
    // Every hand: card points add up and only the winner scores when raised.
    const r = engine.history[engine.history.length - 1];
    assert.strictEqual(r.cardPoints[0] + r.cardPoints[1], r.mode === B.HOKOM ? 162 : 130);
    if (r.level > 1 || r.buyerFailed) assert.strictEqual(r.final[1 - r.winner], 0);
  }
  assert.strictEqual(engine.phase, B.Phase.MATCH_OVER);
  assert.ok(engine.matchWinner === 0 || engine.matchWinner === 1);
});

test("the knowledge base only states things that are true", () => {
  // Replay every recorded hand and check each sample the CSP produces.
  const rng = B.mulberry32(3);
  for (const hand of fixture.hands.slice(0, 10)) {
    const kbs = [0, 1, 2, 3].map((p) => new B.KnowledgeBase(p));
    const mirror = {
      newRound: () => kbs.forEach((kb) => kb.reset()),
      observeContract: (...a) => kbs.forEach((kb) => kb.observeContract(...a)),
      observePlay: (...a) => kbs.forEach((kb) => kb.observePlay(...a)),
      observeDeclaration: (...a) => kbs.forEach((kb) => kb.observeDeclaration(...a)),
    };
    const engine = new B.GameEngine([mirror], B.mulberry32(1));
    engine.dealer = (hand.dealer + 3) % 4;
    engine.startRound(hand.deck);
    for (const step of hand.steps) {
      if (step.type === "bid") engine.applyBid(step.pid, step.action, step.trump);
      else if (step.type === "call") engine.applyEscalation(step.pid, step.action);
      else if (step.type === "trick") engine.resolveTrick();
      else if (step.type === "play") {
        for (let p = 0; p < 4; p++) {
          assert.ok(kbs[p].consistentWith(engine.hands), "knowledge contradicts the real deal");
          const sample = new B.DealSampler(kbs[p], engine.hands[p], rng).sample();
          assert.ok(kbs[p].consistentWith(sample), "sampled deal breaks the knowledge base");
        }
        engine.play(step.pid, step.card);
      }
    }
  }
});
