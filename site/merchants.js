// The /merchants page. Every number is read from data/merchants.json, which scripts/build_site_data.py builds from the run files
// and from clearwake/fees.py. No figure is typed in the page. The form opens the visitor's own mail app; nothing is sent to or stored on this site.
(function () {
  var doc = document, $ = function (id) { return doc.getElementById(id); };
  function el(tag, cls, text) { var e = doc.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }
  function link(href, text) { var a = el("a", "", text); a.href = href; a.rel = "noreferrer"; a.target = "_blank"; return a; }
  function stat(host, value, label) { var d = el("div"), v = el("dd", "tnum", String(value)), t = el("dt", "", label); d.append(v, t); host.append(d); }

  fetch("data/merchants.json", { credentials: "omit" }).then(function (r) { return r.json(); }).then(function (m) {
    var c = m.counts, nums = $("m-nums");
    stat(nums, c.resolved + " of " + c.cases, "resolved inside PayPal");
    stat(nums, c.settled, "settled at INQUIRY, before a claim");
    stat(nums, c.answered_with_proof, "answered with proof, under PayPal review");
    stat(nums, c.waiting_for_owner, "waiting for the owner");
    nums.hidden = false;
    $("m-cases-note").textContent = c.resolved_at_chargeback + " resolved at CHARGEBACK by the owner's voice. " + c.refused + " claim was refused by the buyer agent's mandate before it was filed with PayPal, so PayPal has no record of it.";
    $("m-cases-src").textContent = m.batch_source + " and " + m.voice_source;

    var v = m.voice, host = $("m-voice"), a = v.case4, b = v.case9;
    var one = el("article", "m-case");
    one.append(el("p", "m-tag", "Real PayPal sandbox run"), el("h3", "", "“" + a.command + "”"),
      el("p", "", "PayPal's record reads " + a.status + " at " + a.stage + ", " + a.outcome + ". One refund of USD " + a.refund_amount + ", written " + a.writes + " time, refund id " + a.refund_id + "."),
      el("p", "mono", a.dispute));
    var two = el("article", "m-case");
    two.append(el("p", "m-tag", "Real PayPal sandbox run"), el("h3", "", "“" + b.command + "”"),
      el("p", "", "Tracking and proof sent " + b.writes + " time. Read back right after: " + b.status + " at " + b.stage + ", money moved: " + (b.money_moved ? "yes" : "no") + "."),
      el("p", "mono", b.dispute));
    host.append(one, two); host.hidden = false;
    $("m-voice-src").textContent = v.stt + " heard the owner, " + v.owner_voice + " spoke for the owner, " + v.reply_voice + " spoke for Clearwake. " + m.voice_source;

    var k = m.cost, cost = $("m-cost"), esc = k.escalated_example, set = k.settled_example;
    $("m-cost-lede").textContent = "The sale is the same either way. What changes is the fee leg: PayPal's dispute fee on an escalated claim, against the settlement fee PayPal's record shows on a case settled at INQUIRY.";
    var left = el("div", "col base");
    left.append(el("h3", "", "Escalated to a claim"), el("p", "big tnum", "USD " + k.standard_fee),
      el("p", "", "Standard dispute fee, USD " + k.high_volume_fee + " at high volume, plus the sale: the refunded amount."),
      el("p", "", "Our case " + esc.case + " went to CHARGEBACK: claim USD " + esc.claim + " on a USD " + esc.paid + " order, refund USD " + esc.refund + "."));
    var right = el("div", "col good");
    right.append(el("h3", "", "Settled at INQUIRY"), el("p", "big tnum", "USD " + k.settlement_fee),
      el("p", "", "Settlement fee in PayPal's record, instead of the USD " + k.standard_fee + " dispute fee, plus the same sale."),
      el("p", "", "Our case " + set.case + ": claim USD " + set.claim + " on a USD " + set.paid + " order, settled before a claim. The same USD " + k.settlement_fee + " shows on cases " + k.settled_cases.join(", ") + "."));
    cost.append(left, right); cost.hidden = false;
    $("m-cost-note").textContent = "PayPal's own words: “" + k.waiver + ".” The Standard fee is " + k.fee_below_twice_standard + ". No High Volume waiver line was read on the pages cited, so none is claimed.";
    var src = $("m-cost-src");
    src.append("Sources: ", link(k.fee_page, "PayPal merchant fees"), ", ", link(k.fee_help, "PayPal Help Center help349"), ", ", link(k.rule_source[1], "help350"), ". Our figures: " + m.batch_source + ".");
  }).catch(function () { $("m-cases-note").textContent = "The run figures could not be loaded. They are in the run files named on the Control Room page."; });

  var form = $("m-form");
  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    var name = $("f-name").value.trim(), sell = $("f-sell").value.trim(), count = $("f-count").value.trim();
    var quote = form.elements.quote.value === "yes" ? "yes" : "no";
    if (!name || !sell || count === "" || isNaN(Number(count)) || Number(count) < 0) { $("m-status").textContent = "Please fill in all four answers."; return; }
    fetch("data/contact.json", { credentials: "omit" }).then(function (r) { return r.json(); }).then(function (cfg) {
      var body = "Name: " + name + "\nWhat I sell: " + sell + "\nNot received cases a month: " + count + "\nMay you quote me: " + quote + "\n";
      location.href = "mailto:" + cfg.to + "?subject=" + encodeURIComponent(cfg.subject) + "&body=" + encodeURIComponent(body);
      $("m-status").textContent = "Your mail app should open with the answers filled in. Press send there.";
    }).catch(function () { $("m-status").textContent = "The address could not be loaded. Try again."; });
  });
})();
