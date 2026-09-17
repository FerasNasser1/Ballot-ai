/*
 * The browser table: seats, cards, bidding, doubling and the score sheet.
 * All the rules and the AI are in baloot.js; this file only draws them and
 * collects clicks. You are seat 0, your partner is seat 2.
 */
(function () {
  "use strict";
  const B = window.Baloot;

  const SEAT_NAMES = { 0: "You", 1: "Right", 2: "Partner", 3: "Left" };
  const SEAT_NAMES_AR = { 0: "أنت", 1: "اليمين", 2: "الشريك", 3: "اليسار" };
  const SEAT_INITIALS = { 0: "أ", 1: "ي", 2: "ش", 3: "س" };
  const CALL_LABELS = {
    [B.PASS]: "No raise  بدون",
    [B.CALL_DOUBLE]: "Double  دبل",
    [B.CALL_DOUBLE_CLOSED]: "Double, closed  دبل مقفل",
    [B.CALL_THREE]: "Three  ثري",
    [B.CALL_FOUR]: "Four  فور",
    [B.CALL_FOUR_CLOSED]: "Four, closed  فور مقفل",
    [B.CALL_QAHWA]: "Qahwa  قهوة",
  };
  const DELAY = { bid: 750, think: 650, trick: 1400, deal: 900 };

  const $ = (sel) => document.querySelector(sel);
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  function contractText(mode, trump, level, locked, ashkal) {
    let text = mode === B.HOKOM ? `Hokom ${B.SUIT_SYMBOLS[trump]}`
      : (ashkal ? "Sun (Ashkal)" : "Sun");
    if (level && level !== B.NORMAL) text += ` · ${B.LEVEL_NAMES[level]}`;
    if (locked) text += " · closed";
    return text;
  }

  function cardElement(card, options) {
    options = options || {};
    const el = document.createElement("div");
    el.className = "card" + (B.isRed(card) ? " red" : "");
    const rank = B.rankOf(card), symbol = B.SUIT_SYMBOLS[B.suitOf(card)];
    if (["J", "Q", "K"].includes(rank)) el.classList.add("face");
    el.innerHTML = `<div class="corner">${rank}<span class="suit">${symbol}</span></div>` +
      `<div class="pip">${["J", "Q", "K"].includes(rank) ? rank : symbol}</div>`;
    if (options.trumpMarker) {
      const dot = document.createElement("div");
      dot.className = "trump-dot";
      el.appendChild(dot);
    }
    return el;
  }

  class UI {
    constructor() {
      this.rng = Math.random;
      this.agents = {};
      for (const pid of [1, 2, 3]) {
        this.agents[pid] = new B.BalootAgent(pid, {
          samples: 14, timeBudget: 0.7, escalationSamples: 16, rng: this.rng,
        });
      }
      this.engine = new B.GameEngine(Object.values(this.agents), this.rng);
      this.sheetRows = [];
      this.pending = null;          // resolver waiting for a human click
      $("#new-match").addEventListener("click", () => this.newMatch());
      $("#rules-btn").addEventListener("click", () => this.showRules());
    }

    // ------------------------------------------------------------ drawing
    render() {
      const e = this.engine;
      const active = e.phase === B.Phase.BIDDING ? e.currentBidder
        : e.phase === B.Phase.DOUBLING ? e.escalationTurn
        : e.phase === B.Phase.PLAYING ? e.turn : null;

      for (const pid of [0, 1, 2, 3]) {
        const seat = $(`#seat-${pid}`);
        let badge = "";
        if (e.phase !== B.Phase.BIDDING && e.buyer === pid) {
          badge = "Bought " + contractText(e.mode, e.trump, B.NORMAL, false, e.ashkal);
        } else if (e.doubler === pid && e.level !== B.NORMAL) {
          badge = B.LEVEL_NAMES[e.level];
        } else if (pid === e.dealer) badge = "Dealer";
        const thinking = active === pid && pid !== 0 && e.phase !== B.Phase.ROUND_OVER;
        const backs = pid === 0 ? "" :
          `<div class="backs">${"<div class='back'></div>".repeat(e.hands[pid].length)}</div>`;
        seat.className = "seat" + (pid % 2 === 0 ? " ours" : "") +
          (active === pid ? " active" : "") + (pid === 1 || pid === 3 ? " side" : "");
        seat.innerHTML =
          `<div class="avatar">${SEAT_INITIALS[pid]}</div>` +
          `<div><div class="name">${SEAT_NAMES[pid]}</div>` +
          `<div class="sub ar">${thinking ? "…يفكر" : SEAT_NAMES_AR[pid]}</div>` +
          (badge ? `<div class="badge">${badge}</div>` : "") + backs + `</div>`;
      }

      if (e.phase === B.Phase.BIDDING) {
        $("#contract").textContent =
          `Ground card ${B.rankOf(e.publicCard)}${B.SUIT_SYMBOLS[B.suitOf(e.publicCard)]}` +
          ` · round ${e.bidRound} of bidding`;
      } else if (e.mode) {
        $("#contract").textContent =
          `${contractText(e.mode, e.trump, e.level, e.locked, e.ashkal)}, bought by ${SEAT_NAMES[e.buyer]}`;
      }
      this.renderHand();
      this.renderDeductions();
    }

    renderHand(legal) {
      const e = this.engine;
      const hand = $("#hand");
      hand.innerHTML = "";
      const myTurn = e.phase === B.Phase.PLAYING && e.turn === 0;
      const playable = myTurn ? (legal || e.legalMoves(0)) : null;
      for (const card of B.sortHand(e.hands[0], e.trump)) {
        const el = cardElement(card, { trumpMarker: e.trump && B.suitOf(card) === e.trump });
        if (playable) {
          if (playable.includes(card)) {
            el.classList.add("playable");
            el.addEventListener("click", () => this.resolvePending(card));
          } else {
            el.classList.add("dimmed");
            el.title = "Cannot be played now";
          }
        }
        hand.appendChild(el);
      }
    }

    renderTable(highlightWinner) {
      const e = this.engine;
      const onTable = new Map(e.table);
      for (const pid of [0, 1, 2, 3]) {
        const slot = document.querySelector(`.slot[data-slot="${pid}"]`);
        slot.classList.toggle("won", highlightWinner === pid);
        if (this.bubbles && this.bubbles[pid]) {
          slot.className = `slot filled${highlightWinner === pid ? " won" : ""}`;
          const call = this.bubbles[pid];
          slot.innerHTML = `<div class="bubble${call.startsWith("Pass") || call.startsWith("No ")
            ? "" : " bought"}">${call}</div>`;
          continue;
        }
        slot.innerHTML = "";
        slot.classList.toggle("filled", onTable.has(pid));
        if (onTable.has(pid)) slot.appendChild(cardElement(onTable.get(pid)));
      }
      const ground = $("#ground");
      ground.innerHTML = "";
      if (this.showGround) ground.appendChild(cardElement(e.publicCard));
    }

    renderDeductions() {
      const log = this.agents[2].kb.log.slice(-6);
      const box = $("#deductions");
      if (!log.length) {
        box.textContent = "Nothing yet. Deductions appear as players fail to follow suit, " +
          "show declarations, or lead a trump in a closed game.";
        return;
      }
      const pretty = (line) => line
        .replace(/^R\d: /, "")
        .replace(/P(\d)/g, (m, d) => SEAT_NAMES[Number(d)])
        .replace(/\b(10|[789JQKA])([SHDC])\b/g, (m, rank, suit) => rank + B.SUIT_SYMBOLS[suit])
        .replace("You is", "You are").replace("You holds", "You hold");
      box.textContent = log.map(pretty).join("\n");
    }

    renderSheet() {
      const rows = $("#sheet-rows");
      rows.innerHTML = "";
      for (const row of this.sheetRows) {
        const el = document.createElement("div");
        el.className = "row";
        el.innerHTML = (row.note ? `<div class="note">${row.note}</div>` : "") +
          `<div>${row.us}</div><div>${row.them}</div>`;
        rows.appendChild(el);
      }
      rows.scrollTop = rows.scrollHeight;
      $("#total-us").textContent = this.engine.totals[0];
      $("#total-them").textContent = this.engine.totals[1];
    }

    status(text) { $("#status").textContent = text; }

    // ------------------------------------------------------- human input
    buttons(options, labeller) {
      const box = $("#actions");
      box.innerHTML = "";
      return new Promise((resolve) => {
        this.pending = resolve;
        for (const option of options) {
          const btn = document.createElement("button");
          const label = labeller(option);
          btn.textContent = label.text;
          if (label.primary) btn.className = "buy";
          if (label.tip) btn.title = label.tip;
          btn.addEventListener("click", () => {
            box.innerHTML = "";
            this.resolvePending(option);
          });
          box.appendChild(btn);
        }
      });
    }

    resolvePending(value) {
      if (!this.pending) return;
      const resolve = this.pending;
      this.pending = null;
      resolve(value);
    }

    waitForCard(legal) {
      this.renderHand(legal);
      return new Promise((resolve) => { this.pending = resolve; });
    }

    dialog(html, buttons) {
      $("#dialog").innerHTML = html +
        `<div class="buttons">${buttons.map((b, i) =>
          `<button data-index="${i}" class="${b.primary ? "buy" : "quiet"}">${b.text}</button>`).join("")}</div>`;
      $("#modal").classList.remove("hidden");
      return new Promise((resolve) => {
        $("#dialog").querySelectorAll("button").forEach((btn) => {
          btn.addEventListener("click", () => {
            $("#modal").classList.add("hidden");
            resolve(Number(btn.dataset.index));
          });
        });
      });
    }

    // ------------------------------------------------------------- rounds
    async newMatch() {
      this.resolvePending(null);
      this.engine.newMatch();
      this.sheetRows = [];
      this.renderSheet();
      await this.playRound();
    }

    async playRound() {
      const e = this.engine;
      if (e.phase === B.Phase.MATCH_OVER) return;
      e.startRound();
      this.bubbles = {};
      this.showGround = true;
      this.render();
      this.renderTable();
      this.status("Bidding. Buy Sun or Hokom, or pass.");
      await wait(DELAY.deal);
      const bought = await this.runBidding();
      if (!bought) { await this.playRound(); return; }
      await this.runDoubling();
      await this.runPlay();
    }

    async runBidding() {
      const e = this.engine;
      while (e.phase === B.Phase.BIDDING) {
        const pid = e.currentBidder;
        this.render();
        let action, trump = null;
        if (pid === 0) {
          this.status(this.bidPrompt());
          action = await this.buttons(e.bidOptions(), (option) => this.bidLabel(option));
          if (action === null) return false;
          if (action === B.BUY_HOKOM_THANI) {
            trump = await this.buttons(e.thaniSuits(), (suit) => ({
              text: `${B.SUIT_SYMBOLS[suit]}  ${B.SUIT_NAMES[suit]}`, primary: true }));
            if (trump === null) return false;
          } else if (action === B.BUY_HOKOM) trump = B.suitOf(e.publicCard);
        } else {
          this.status(`${SEAT_NAMES[pid]} is deciding…`);
          await wait(DELAY.bid);
          [action, trump] = this.agents[pid].chooseBid(e.hands[pid], e.publicCard, e.bidRound, e.bidOptions());
        }
        const outcome = e.applyBid(pid, action, trump);
        this.bubbles[pid] = this.bidBubble(action, trump);
        this.renderTable();
        this.render();

        if (outcome === "redeal") {
          this.status("Everyone passed twice. Dealing again.");
          await wait(1500);
          return false;
        }
        if (outcome === "second_round") {
          this.status("Nobody bought. Second round of bidding.");
          await wait(1100);
          this.bubbles = {};
          this.renderTable();
        } else if (outcome === "hokom") {
          this.status(`${SEAT_NAMES[pid]} bought Hokom. The others may still take Sun.`);
          await wait(900);
        } else if (outcome === "bought") {
          const extra = e.ashkal ? `, ${SEAT_NAMES[e.taker]} takes the ground card` : "";
          this.status(`${SEAT_NAMES[e.buyer]} bought ${contractText(e.mode, e.trump, B.NORMAL, false, e.ashkal)}${extra}.`);
          await wait(1300);
          this.bubbles = {};
          this.showGround = false;
          this.renderTable();
          this.render();
        }
      }
      return true;
    }

    bidPrompt() {
      const e = this.engine;
      if (e.hokomBid !== null) {
        return `${SEAT_NAMES[e.hokomBid[0]]} bought Hokom ${B.SUIT_SYMBOLS[e.hokomBid[1]]}.` +
          " Take it with Sun, or pass.";
      }
      if (e.bidOptions().includes(B.BUY_ASHKAL)) {
        return "Your bid. Sun, Ashkal (the ground card goes to your partner), Hokom, or pass.";
      }
      return "Your bid. Buy Sun, buy Hokom, or pass.";
    }

    bidLabel(option) {
      const e = this.engine;
      switch (option) {
        case B.PASS: return { text: e.bidRound === 1 ? "Pass  بس" : "Pass  ولا" };
        case B.BUY_SUN: return { text: "Buy Sun  صن", primary: true };
        case B.BUY_ASHKAL: return { text: "Ashkal  أشكل", primary: true,
          tip: "Sun, but the ground card goes to your partner" };
        case B.BUY_HOKOM: return {
          text: `Buy Hokom ${B.SUIT_SYMBOLS[B.suitOf(e.publicCard)]}  حكم`, primary: true };
        case B.BUY_HOKOM_THANI: return { text: "Hokom in another suit  حكم ثاني", primary: true };
        default: return { text: option };
      }
    }

    bidBubble(action, trump) {
      if (action === B.PASS) return "Pass  بس";
      if (action === B.BUY_SUN) return "Sun  صن";
      if (action === B.BUY_ASHKAL) return "Ashkal  أشكل";
      return `Hokom ${B.SUIT_SYMBOLS[trump]}  حكم`;
    }

    async runDoubling() {
      const e = this.engine;
      while (e.phase === B.Phase.DOUBLING) {
        const pid = e.escalationTurn;
        this.render();
        let action;
        if (pid === 0) {
          this.status(e.level === B.NORMAL
            ? "Double the stake? In a closed game nobody may lead a trump."
            : "Raise it further?");
          action = await this.buttons(e.escalationOptions(), (option) => ({
            text: CALL_LABELS[option], primary: option !== B.PASS }));
          if (action === null) return;
        } else {
          this.status(`${SEAT_NAMES[pid]} is thinking about doubling…`);
          await wait(DELAY.bid);
          action = this.agents[pid].chooseEscalation(e.escalationView(pid));
        }
        const outcome = e.applyEscalation(pid, action);
        this.bubbles[pid] = CALL_LABELS[action];
        this.renderTable();
        this.render();
        await wait(outcome === "done" ? 1100 : 900);
      }
      this.bubbles = {};
      this.renderTable();
      if (e.locked) this.status("Closed game: nobody may lead a trump.");
    }

    async runPlay() {
      const e = this.engine;
      while (e.phase === B.Phase.PLAYING || e.phase === B.Phase.TRICK_COMPLETE) {
        if (e.phase === B.Phase.TRICK_COMPLETE) {
          const winner = e.currentWinner();
          const points = B.trickPoints(e.table, e.mode, e.trump) + (e.tricksPlayed === 7 ? 10 : 0);
          this.renderTable(winner);
          this.status(`${winner === 0 ? "You take" : SEAT_NAMES[winner] + " takes"} the trick, ${points} points.`);
          await wait(DELAY.trick);
          const result = e.resolveTrick();
          this.renderTable();
          this.render();
          if (result.declarations && result.declarations.winningTeam !== null
              && Object.keys(result.declarations.shown).length) {
            await this.showDeclarations(result.declarations);
          }
          if (result.roundResult) { await this.finishRound(result.roundResult); return; }
          continue;
        }
        const pid = e.turn;
        this.render();
        if (pid === 0) {
          this.status("Your turn. Playable cards lift when you point at them.");
          const card = await this.waitForCard(e.legalMoves(0));
          if (card === null) return;
          e.play(0, card);
        } else {
          this.status(`${SEAT_NAMES[pid]} is thinking…`);
          const started = Date.now();
          const card = await this.agents[pid].chooseCard(e.viewFor(pid),
            (resume) => setTimeout(resume, 0));       // keep the page responsive
          await wait(Math.max(0, DELAY.think - (Date.now() - started)));
          e.play(pid, card);
        }
        this.renderTable();
        this.render();
      }
    }

    async showDeclarations(decl) {
      const team = decl.winningTeam;
      let html = `<h2>Declarations <span class="ar">مشاريع</span></h2>` +
        `<p class="muted">${team === 0 ? "Your team" : "The other team"} holds the best project, ` +
        `so only their projects score (${decl.teamPoints[team]} points this round).</p>`;
      for (const [pid, projects] of Object.entries(decl.shown)) {
        html += `<div class="${Number(pid) % 2 === 0 ? "us-col" : "them-col"}"><strong>${SEAT_NAMES[pid]}</strong></div>`;
        for (const project of projects) {
          const cards = project.cards.map((c) => cardElement(c).outerHTML).join("");
          html += `<div class="project"><span style="min-width:90px">${project.name} ` +
            `(${B.projectPoints(project.raw, this.engine.mode)})</span>${cards}</div>`;
        }
      }
      await this.dialog(html, [{ text: "Continue", primary: true }]);
    }

    async finishRound(r) {
      const note = r.qahwa ? "قهوة" : r.level !== B.NORMAL ? `×${r.level}` : r.buyerFailed ? "✗" : "";
      this.sheetRows.push({ us: r.final[0], them: r.final[1], note });
      this.renderSheet();
      this.render();

      const rows = [
        ["Card points", r.cardPoints],
        ["Converted", r.base],
        ["Projects", r.projectPoints],
        ["This round", r.final],
        ["Match total", r.totalsAfter],
      ];
      let html = `<h2>Round result <span class="ar">النتيجة</span></h2>` +
        `<p class="muted">${contractText(r.mode, r.trump, r.level, r.locked, r.ashkal)}, ` +
        `bought by ${SEAT_NAMES[r.buyer]}</p><table><tr><th></th>` +
        `<th class="us-col">Us لنا</th><th class="them-col">Them لهم</th></tr>`;
      for (const [label, values] of rows) {
        const strong = label === "This round" || label === "Match total";
        html += `<tr class="${strong ? "strong" : ""}"><td>${label}</td>` +
          `<td>${values[0]}</td><td>${values[1]}</td></tr>`;
      }
      html += "</table>";
      const winners = r.winner === 0 ? "Your team" : "The other team";
      if (r.qahwa) {
        html += `<div class="banner">Qahwa! ${winners} won the hand, and with it the whole match.</div>`;
      } else if (r.level !== B.NORMAL) {
        html += `<div class="banner">${B.LEVEL_NAMES[r.level]} hand. ${winners} won it and takes ` +
          `all ${r.final[0] + r.final[1]} points.</div>`;
      } else if (r.buyerFailed) {
        html += `<div class="banner">${SEAT_NAMES[r.buyer]}'s team did not win the hand, so all ` +
          `${r.final[0] + r.final[1]} points go to the other team.</div>`;
      }

      const over = this.engine.phase === B.Phase.MATCH_OVER;
      await this.dialog(html, [{ text: over ? "See final result" : "Deal next round", primary: true }]);
      if (!over) { await this.playRound(); return; }

      const won = this.engine.matchWinner === 0;
      await this.dialog(
        `<h2>${won ? "Your team wins" : "The other team wins"} ` +
        `<span class="ar">${won ? "مبروك" : "حظ أوفر"}</span></h2>` +
        `<p>Final score: us ${this.engine.totals[0]}, them ${this.engine.totals[1]}.</p>`,
        [{ text: "Start a new match", primary: true }]);
      await this.newMatch();
    }

    showRules() {
      this.dialog(
        `<h2>Baloot in brief <span class="ar">قوانين</span></h2>
         <ul>
           <li><strong>Bidding.</strong> Everyone gets five cards and one is turned face up. Buy
               <em>Hokom</em> (that suit is trump) or <em>Sun</em> (no trump), or pass. Sun beats a
               Hokom bid, so a Hokom can still be taken away. If all four pass, a second round
               allows Hokom in another suit.</li>
           <li><strong>Ashkal (أشكل).</strong> Only the dealer and the player on the dealer's left
               may call it. It is a Sun bid, but the ground card goes to the caller's partner.</li>
           <li><strong>Double, Three, Four, Qahwa.</strong> In Hokom a defender may say
               <em>Double</em> (×2), open or closed. The buyer may answer <em>Three</em> (×3), the
               doubler <em>Four</em> (×4), and the buyer <em>Qahwa</em> — whoever wins that hand
               wins the whole match. In a <em>closed</em> (مقفل) hand nobody may lead a trump
               unless their hand is all trumps. In Sun only Double exists, and only when the
               defenders have 100 points or fewer and the buyers more than 100.</li>
           <li><strong>Scoring.</strong> Hokom is worth 16 round points, Sun 26, plus projects.
               The buying team must win the hand or the other team takes everything. In a raised
               hand the winner takes it all: cards ×2, ×3 or ×4, projects ×2 at most, and Baloot
               always 2.</li>
           <li><strong>Match.</strong> First team to 152 points.</li>
         </ul>
         <p class="muted">The AI partner and opponents use a knowledge base, constraint-based deal
            sampling, alpha-beta search and Monte Carlo rollouts. See the repository README.</p>`,
        [{ text: "Close", primary: true }]);
    }
  }

  const ui = new UI();
  window.balootUI = ui;                  // handy for debugging and for the browser test
  ui.renderSheet();
  ui.playRound();
})();
