/* "Try it live" block. Plain JavaScript, no dependencies.
 *
 * The page works without this file: everything else on it is static HTML.
 * With it, a visitor can send one pair of passages, or a repository name, to the live service
 * (see live/ in the repository). When the service cannot be reached, or its trial budget is
 * used up, the three prefilled examples fall back to their recorded answers and the block says so.
 */
(function () {
  "use strict";
  var root = document.getElementById("live");
  if (!root) return;
  var API = (root.getAttribute("data-api") || "").replace(/\/+$/, "");
  var examples = [];
  var state = { mode: API ? "checking" : "replay", status: null };

  function el(tag, attrs, children) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "text") e.textContent = attrs[k];
      else if (k === "class") e.className = attrs[k];
      else e.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { if (c) e.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return e;
  }

  function request(method, path, body, timeoutMs) {
    var ctl = new AbortController();
    var timer = setTimeout(function () { ctl.abort(); }, timeoutMs || 60000);
    return fetch(API + path, {
      method: method, signal: ctl.signal,
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined
    }).then(function (r) {
      clearTimeout(timer);
      return r.json().then(function (j) { j._http = r.status; return j; });
    }, function (err) { clearTimeout(timer); throw err; });
  }

  // ------------------------------------------------------------------ layout
  var statusLine = el("p", { class: "live-status", role: "status" });
  var exampleRow = el("div", { class: "live-examples" });
  var ta = el("textarea", { id: "live-a", rows: "7", spellcheck: "false", "aria-label": "First passage" });
  var tb = el("textarea", { id: "live-b", rows: "7", spellcheck: "false", "aria-label": "Second passage" });
  var pairBtn = el("button", { type: "button", class: "live-btn", text: API ? "Check this pair" : "Show the recorded answer" });
  var pairOut = el("div", { class: "live-out", "aria-live": "polite" });
  var repoIn = el("input", { id: "live-repo", type: "text", placeholder: "owner/name, for example fastify/fastify",
                              autocomplete: "off", spellcheck: "false", "aria-label": "GitHub repository" });
  var repoBtn = el("button", { type: "button", class: "live-btn", text: "Scan this repository" });
  var repoOut = el("div", { class: "live-out", "aria-live": "polite" });

  root.appendChild(statusLine);
  root.appendChild(el("h3", { text: "One pair of passages" }));
  root.appendChild(el("p", { class: "live-hint", text: API
    ? "Paste two passages of documentation, or fill in one of three real pairs. The tool asks Clocked /compare in both orders, then /grounding."
    : "Pick one of the three real pairs and press the button to see the recorded answers." }));
  root.appendChild(exampleRow);
  root.appendChild(el("div", { class: "live-pair" }, [
    el("label", { for: "live-a" }, [el("span", { text: "First passage" }), ta]),
    el("label", { for: "live-b" }, [el("span", { text: "Second passage" }), tb])
  ]));
  root.appendChild(el("p", { class: "live-actions" }, [pairBtn]));
  root.appendChild(pairOut);
  if (API) {   // a repository can only be scanned by the live service; there is nothing to replay for an arbitrary one
    root.appendChild(el("h3", { text: "A public GitHub repository" }));
    root.appendChild(el("p", { class: "live-hint", text: "Only Markdown documentation is read (a root README and docs folders). The trial reads up to 24 pairs and stops after 150 seconds; the full tool reads 150 pairs." }));
    root.appendChild(el("p", { class: "live-actions" }, [repoIn, repoBtn]));
    root.appendChild(repoOut);
  }

  // ------------------------------------------------------------------ status
  function showStatus() {
    statusLine.className = "live-status live-" + state.mode;
    if (state.mode === "checking") {
      statusLine.textContent = "Checking whether the live service is up…";
    } else if (state.mode === "live") {
      var b = state.status.budget;
      statusLine.textContent = "Live. " + Math.round(b.remaining).toLocaleString() + " of " +
        Math.round(b.total).toLocaleString() + " trial credits left. Each request is capped and rate-limited.";
    } else if (state.mode === "exhausted") {
      statusLine.textContent = "The live trial budget is used up. The three examples below show their recorded answers; everything else on this page is a replay too.";
    } else {
      statusLine.textContent = API
        ? "The live service cannot be reached right now. The three examples below show their recorded answers; everything else on this page is a replay too."
        : "Recorded answers. The live service is not running, so only the three examples below can be shown.";
    }
    var live = state.mode === "live";
    repoIn.disabled = !live;
    repoBtn.disabled = !live;
  }

  function refreshStatus() {
    if (!API) { showStatus(); return Promise.resolve(); }
    return request("GET", "/api/status", null, 6000).then(function (s) {
      state.status = s;
      state.mode = s.exhausted ? "exhausted" : "live";
      showStatus();
    }, function () { state.mode = "unreachable"; showStatus(); });
  }

  // ----------------------------------------------------------------- results
  function pct(x) { return x == null ? "n/a" : (Math.round(x * 1000) / 10) + "%"; }

  function renderPair(r, note) {
    pairOut.textContent = "";
    if (note) pairOut.appendChild(el("p", { class: "live-note", text: note }));
    var head = r.listed
      ? "Listed for review: " + r.tier_words + "."
      : "Not listed: " + (r.tier_words || "no conflict found") + ".";
    pairOut.appendChild(el("p", { class: "live-verdict " + (r.listed ? "is-listed" : "is-clear"), text: head }));
    if (r.kind) {
      var kinds = { value: "a value", date_or_version: "a version", rule_or_condition: "a rule", whole_passage: "the passage as a whole", scope: "scope", name: "a name" };
      pairOut.appendChild(el("p", { text: "The passages disagree on " + (kinds[r.kind] || r.kind) + ". Confidence " + pct(r.confidence) + "." }));
    }
    if (r.note) pairOut.appendChild(el("p", { class: "live-note", text: r.note }));
    ["a", "b"].forEach(function (side) {
      var s = r[side];
      if (!s) return;
      var text = s.statement || (s.quote || "").slice(0, 320);
      pairOut.appendChild(el("p", { class: "live-quote" }, [el("b", { text: (side === "a" ? "First" : "Second") + " passage, line " + s.line + ": " }), text]));
    });
    var rows = [];
    Object.keys(r.compare || {}).forEach(function (k) {
      var o = r.compare[k];
      var found = o.conflicts.length ? o.conflicts.map(function (c) { return c.kind + " " + pct(c.confidence); }).join(", ") : "no conflict span";
      rows.push(["/compare, " + (k === "a_then_b" ? "first then second" : "second then first"),
                 o.relation + " (conflicting " + pct(o.conflicting) + "); " + found]);
    });
    Object.keys(r.grounding || {}).forEach(function (k) {
      var g = r.grounding[k];
      rows.push(["/grounding, " + (k.indexOf("first") === 0 ? "first passage against the second" : "second passage against the first"),
                 g ? g.verdict + " (contradicted " + pct(g.contradicted) + ")" : "not asked: no single sentence to check"]);
    });
    var c = r.credits || {};
    rows.push(["Credits", (c.spent_now != null ? c.spent_now + " spent now, " : "") + c.list_price + " at list price" +
      (c.answers_replayed ? "; " + c.answers_replayed + " answers came from the cache" : "")]);
    var dl = el("dl", { class: "live-raw" });
    rows.forEach(function (row) { dl.appendChild(el("dt", { text: row[0] })); dl.appendChild(el("dd", { text: row[1] })); });
    pairOut.appendChild(dl);
  }

  function recordedFor(a, b) {
    for (var i = 0; i < examples.length; i++) {
      if (examples[i].a.text.trim() === a.trim() && examples[i].b.text.trim() === b.trim()) return examples[i];
    }
    return null;
  }

  function checkPair() {
    var a = ta.value, b = tb.value;
    var ex = recordedFor(a, b);
    function fallback(why) {
      if (ex) renderPair(ex.recorded, why + " This is the recorded answer for this example.");
      else { pairOut.textContent = ""; pairOut.appendChild(el("p", { class: "live-note", text: why + " Only the three examples can be shown as recordings." })); }
    }
    if (state.mode !== "live") { fallback(statusLine.textContent.split(".")[0] + "."); return; }
    pairBtn.disabled = true;
    pairOut.textContent = "Asking Clocked…";
    request("POST", "/api/pair", { a: a, b: b }, 70000).then(function (r) {
      pairBtn.disabled = false;
      if (r.ok) { renderPair(r); if (r.budget) { state.status.budget = r.budget; showStatus(); } return; }
      if (r.error === "trial_budget_exhausted") { state.mode = "exhausted"; showStatus(); fallback("The live trial budget is used up."); return; }
      pairOut.textContent = "";
      pairOut.appendChild(el("p", { class: "live-note", text: r.message || "The request was refused." }));
    }, function () {
      pairBtn.disabled = false;
      state.mode = "unreachable"; showStatus();
      fallback("The live service did not answer.");
    });
  }

  function renderScan(job) {
    repoOut.textContent = "";
    if (job.message) repoOut.appendChild(el("p", { class: "live-note", text: job.message }));
    var r = job.result;
    if (!r) return;
    var s = r.stats;
    var unread = s.candidate_pairs_found > s.pairs_read;
    repoOut.appendChild(el("p", { class: "live-verdict " + (s.listed ? "is-listed" : "is-clear"),
      text: r.repo + " at " + r.commit.slice(0, 10) + ": " + s.passages + " passages in " + s.files + " files, " + s.pairs_read +
            " pairs read" + (unread ? " (of " + s.candidate_pairs_found + " candidates)" : "") + ", " + s.flagged +
            " flagged by /compare, " + s.listed + " listed for review." }));
    r.items.forEach(function (it) {
      var card = el("div", { class: "live-item" });
      card.appendChild(el("p", { text: "Disagree on " + it.kind.replace(/_/g, " ") + " (" + it.tier_words + ")" }));
      ["a", "b"].forEach(function (side) {
        var x = it[side];
        card.appendChild(el("p", { class: "live-quote" }, [
          el("a", { href: x.url, text: x.path + ":" + x.line_start }), " ", x.statement || "(a long passage; open the link)"]));
      });
      if (it.probably_stale) card.appendChild(el("p", { text: "The " + (it.probably_stale === "a" ? "first" : "second") + " passage is probably the stale one." }));
      repoOut.appendChild(card);
    });
    if (!s.listed) repoOut.appendChild(el("p", { text: "Nothing listed. That means no pair among those read passed the checks, not that the docs are free of contradictions." +
      (unread ? " This trial read only part of the candidates; the command line tool reads more." : "") }));
    repoOut.appendChild(el("p", { class: "live-note", text: r.note + " Credits: " + r.credits.spent_now + " spent now, " + r.credits.list_price + " at list price." }));
    if (r.budget) { state.status.budget = r.budget; showStatus(); }
  }

  function scanRepo() {
    var repo = repoIn.value.trim();
    if (state.mode !== "live") return;
    repoBtn.disabled = true;
    repoOut.textContent = "Starting…";
    var started = Date.now();
    function fail(msg) { repoBtn.disabled = false; repoOut.textContent = ""; repoOut.appendChild(el("p", { class: "live-note", text: msg })); }
    function poll(id) {
      request("GET", "/api/scan/" + encodeURIComponent(id), null, 15000).then(function (job) {
        if (job.status === "queued" || job.status === "running") {
          var p = job.progress || {};
          repoOut.textContent = job.stage + (p.total ? " (" + p.done + " of " + p.total + ")" : "") + ", " + Math.round((Date.now() - started) / 1000) + " s";
          if (Date.now() - started > 240000) return fail("No result after four minutes. The scan may still finish; the recorded scans on this page do not depend on it.");
          return setTimeout(function () { poll(id); }, 1500);
        }
        repoBtn.disabled = false;
        renderScan(job);
      }, function () { fail("The live service stopped answering while the scan was running. The recorded scans on this page do not depend on it."); });
    }
    request("POST", "/api/scan", { repo: repo }, 20000).then(function (job) {
      if (!job.job) {
        if (job.error === "trial_budget_exhausted") { state.mode = "exhausted"; showStatus(); }
        return fail(job.message || "The request was refused.");
      }
      if (job.status === "queued" || job.status === "running") poll(job.job); else { repoBtn.disabled = false; renderScan(job); }
    }, function () { state.mode = "unreachable"; showStatus(); fail("The live service did not answer."); });
  }

  pairBtn.addEventListener("click", checkPair);
  repoBtn.addEventListener("click", scanRepo);
  repoIn.addEventListener("keydown", function (e) { if (e.key === "Enter") scanRepo(); });

  try {
    examples = JSON.parse(document.getElementById("live-examples").textContent);
  } catch (e) { examples = []; }
  examples.forEach(function (ex) {
    var b = el("button", { type: "button", class: "live-example", text: ex.label });
    b.addEventListener("click", function () { ta.value = ex.a.text; tb.value = ex.b.text; pairOut.textContent = ""; });
    exampleRow.appendChild(b);
  });
  if (examples.length) { ta.value = examples[0].a.text; tb.value = examples[0].b.text; }

  showStatus();
  refreshStatus();
})();
