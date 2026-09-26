// Customer page: mood -> picks -> reactions / set buttons -> menu -> cart -> order status.
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const CUR = document.body.dataset.currency || "₹";
const MOOD_ICON = { work: Icon.work, meet: Icon.meet, unwind: Icon.unwind };
const MOOD_LABEL = { work: "Working", meet: "Meeting", unwind: "Unwinding" };

let S = { picks: [], mood: null };
let menuMode = "full";
const cart = new Map(); // key (item + choices) -> {item, qty, choices, unit, summary}
let orderPoll = null;

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (p) => (p == null ? "" : `${CUR}${Number(p).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`);

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove("show"), 2200);
}

async function api(path, body) {
  const r = await fetch(path, {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || "Something went wrong");
  return data;
}

async function busy(el, fn) {
  el?.classList.add("busy");
  try { return await fn(); } catch (e) { toast(e.message); } finally { el?.classList.remove("busy"); }
}

function show(view) {
  $$("main > section").forEach((s) => (s.hidden = s.id !== `view-${view}`));
  $("#menuLink").hidden = view !== "picks";
  window.scrollTo({ top: 0 });
}

// ---------- picks ----------

function cardHTML(it) {
  const inCart = countInCart(it.id);
  return `
  <article class="card ${it.reaction || ""}" data-id="${it.id}">
    <div class="card-top"><span class="reason">${Icon.spark("icon-sm")}${esc(it.reason)}</span><span class="price">${money(it.price)}</span></div>
    <h3><span class="dot ${it.veg ? "" : "nonveg"}" title="${it.veg ? "Vegetarian" : "Non-vegetarian"}"></span>${esc(it.name)}</h3>
    <p class="blurb">${esc(it.blurb || it.description)}</p>
    ${it.allergens.length ? `<p class="allergens">Contains: ${esc(it.allergens.join(", "))}</p>` : ""}
    <div class="card-actions">
      <div class="react" role="group" aria-label="Your reaction">
        <button data-r="like" aria-label="Love it" aria-pressed="${it.reaction === "like"}">${Icon.heart()}</button>
        <button data-r="meh" aria-label="It's okay" aria-pressed="${it.reaction === "meh"}">${Icon.meh()}</button>
        <button data-r="nope" aria-label="Not for me" aria-pressed="false">${Icon.nope()}</button>
      </div>
      <button class="add ${inCart ? "in-cart" : ""}" data-add="${it.id}">${inCart ? `${Icon.check("icon-sm")} ${inCart} · Add` : Icon.plus("icon-sm") + " Add"}</button>
    </div>
  </article>`;
}

function renderPicks() {
  $("#picks").innerHTML = S.picks.map(cardHTML).join("");
  $("#changeMood").innerHTML = `${MOOD_LABEL[S.mood] || ""} · change`;
}

function setTheme(mood) {
  document.body.dataset.mood = mood || "home";
  window.Ambience?.setMood(mood || "home");
}

function applyState(data) {
  S = { ...S, ...data };
  setTheme(S.mood);
  renderPicks();
}

$$(".mood").forEach((b) =>
  b.addEventListener("click", () =>
    busy(b, async () => {
      setTheme(b.dataset.mood); // instant colour + music change, before the server answers
      applyState(await api("/api/mood", { mood: b.dataset.mood }));
      show("picks");
    })
  )
);

$("#changeMood").addEventListener("click", () => show("mood"));

$("#picks").addEventListener("click", (e) => {
  const r = e.target.closest("[data-r]");
  const add = e.target.closest("[data-add]");
  if (r) {
    const card = r.closest(".card");
    const reaction = r.dataset.r;
    busy(card, async () => {
      applyState(await api("/api/react", { item_id: Number(card.dataset.id), reaction }));
      if (reaction === "nope") toast("Swapped it for something else");
    });
  } else if (add) {
    startAdd(S.picks.find((p) => p.id === Number(add.dataset.add)));
  }
});

$$("[data-set]").forEach((b) =>
  b.addEventListener("click", () =>
    busy($(".set-buttons"), async () => {
      const data = await api("/api/set", { action: b.dataset.set });
      applyState(data);
      if (data.view === "ranked") {
        await openMenu("ranked");
        toast("Here's the whole menu, best matches first");
      } else {
        toast(b.dataset.set === "mixed" ? "Kept the good ones, swapped the rest" : "Fresh picks, coming up");
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    })
  )
);

// ---------- full menu ----------

function rowHTML(it, top) {
  const inCart = countInCart(it.id);
  return `
  <div class="row ${it.available ? "" : "off"}">
    <div><b><span class="dot ${it.veg ? "" : "nonveg"}"></span>${esc(it.name)}</b>${top ? '<span class="badge">Top match</span>' : ""}${it.available ? "" : '<span class="badge soldout">Sold out</span>'}</div>
    <div class="right"><span class="price">${money(it.price)}</span>
      ${it.available ? `<button class="add ${inCart ? "in-cart" : ""}" data-add="${it.id}">${inCart ? `${Icon.check("icon-sm")} ${inCart}` : Icon.plus("icon-sm") + " Add"}</button>` : ""}</div>
    <p class="blurb">${esc(it.blurb || it.description)}${it.allergens.length ? ` · <small>${esc(it.allergens.join(", "))}</small>` : ""}</p>
  </div>`;
}

let menuItems = [];
async function openMenu(mode) {
  menuMode = mode;
  const data = await api(`/api/menu?ranked=${mode === "ranked" ? 1 : 0}`);
  menuItems = data.items;
  if (mode === "ranked" && !data.ranked) menuMode = "full"; // no mood yet: nothing to rank by
  renderMenu();
  show("menu");
}

function renderMenu() {
  $$(".seg button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.mode === menuMode)));
  $(".seg").hidden = !S.mood;
  $("#backToPicks").hidden = !S.mood;
  let html = "";
  if (menuMode === "ranked") {
    html = menuItems.map((it, i) => rowHTML(it, i < 5 && it.available)).join("");
  } else {
    const cats = {};
    menuItems.forEach((it) => (cats[it.category] ||= []).push(it));
    html = Object.entries(cats).map(([c, list]) => `<div class="cat">${esc(c)}</div>${list.map((it) => rowHTML(it, false)).join("")}`).join("");
  }
  $("#menuList").innerHTML = html || '<p class="muted">The menu is empty right now.</p>';
}

$$("[data-go=menu]").forEach((b) => b.addEventListener("click", () => busy(b, () => openMenu(S.mood ? "ranked" : "full"))));
$$(".seg button").forEach((b) => b.addEventListener("click", () => busy($("#menuList"), () => openMenu(b.dataset.mode))));
$("#backToPicks").addEventListener("click", () => show(S.picks.length ? "picks" : "mood"));
$("#menuList").addEventListener("click", (e) => {
  const add = e.target.closest("[data-add]");
  if (!add) return;
  startAdd(menuItems.find((m) => m.id === Number(add.dataset.add)));
});

// ---------- customisation ----------
// The phone remembers your usual choices (e.g. oat milk, less sugar) and pre-selects them.
const USUAL_KEY = "cafe-usual";
function loadUsual() { try { return JSON.parse(localStorage.getItem(USUAL_KEY)) || {}; } catch { return {}; } }
function saveUsual(choices) {
  try { localStorage.setItem(USUAL_KEY, JSON.stringify({ ...loadUsual(), ...choices })); } catch { /* storage blocked */ }
}

let cus = null; // {item, qty, choices}

function defaultChoices(item, usual = {}) {
  const choices = {};
  let fromUsual = false;
  for (const g of item.options || []) {
    const labels = g.choices.map((c) => c.label);
    const def = g.choices.find((c) => c.default)?.label || labels[0];
    const remembered = (usual[g.name] || []).filter((l) => labels.includes(l));
    if (g.type === "multi") {
      choices[g.name] = []; // extras are never pre-added: no surprise charges
    } else if (remembered.length) {
      choices[g.name] = remembered.slice(0, 1);
      if (remembered[0] !== def) fromUsual = true;
    } else {
      choices[g.name] = [def];
    }
  }
  return { choices, fromUsual };
}

function unitPrice(item, choices) {
  if (item.price == null) return null;
  let p = item.price;
  for (const g of item.options || []) {
    for (const l of choices[g.name] || []) p += g.choices.find((c) => c.label === l)?.price || 0;
  }
  return p;
}

function summaryOf(item, choices) {
  const out = [];
  for (const g of item.options || []) {
    const def = g.choices.find((c) => c.default)?.label;
    for (const l of choices[g.name] || []) if (g.type === "multi" || l !== def) out.push(l);
  }
  return out;
}

function startAdd(item) {
  if (!item) return;
  if (!(item.options || []).length) return addToCart(item, {}, 1);
  const { choices, fromUsual } = defaultChoices(item, loadUsual());
  cus = { item, qty: 1, choices };
  $("#cusName").textContent = item.name;
  $("#cusUsual").hidden = !fromUsual;
  renderCustom();
  $("#customSheet").showModal();
}

function renderCustom() {
  const { item, choices } = cus;
  $("#cusGroups").innerHTML = item.options.map((g, gi) => `
    <fieldset class="optgroup">
      <legend>${esc(g.name)} <small>${g.type === "multi" ? "add any" : "pick one"}</small></legend>
      <div class="opt-chips">${g.choices.map((c) => {
        const on = (choices[g.name] || []).includes(c.label);
        return `<label class="opt ${on ? "on" : ""}">
          <input type="${g.type === "multi" ? "checkbox" : "radio"}" name="g${gi}" data-g="${esc(g.name)}" value="${esc(c.label)}" ${on ? "checked" : ""}>
          <span>${esc(c.label)}${c.price ? ` <small>+${money(c.price)}</small>` : ""}</span></label>`;
      }).join("")}</div>
    </fieldset>`).join("");
  $("#cusQty").textContent = cus.qty;
  const unit = unitPrice(item, choices);
  $("#cusAdd").textContent = `Add to order${unit != null ? " · " + money(unit * cus.qty) : ""}`;
}

$("#cusGroups").addEventListener("change", (e) => {
  const input = e.target.closest("input[data-g]");
  if (!input) return;
  const g = input.dataset.g;
  cus.choices[g] = input.type === "radio"
    ? [input.value]
    : $$(`input[data-g="${CSS.escape(g)}"]:checked`, $("#cusGroups")).map((i) => i.value);
  renderCustom();
});
$("#cusMinus").addEventListener("click", () => { cus.qty = Math.max(1, cus.qty - 1); renderCustom(); });
$("#cusPlus").addEventListener("click", () => { cus.qty = Math.min(20, cus.qty + 1); renderCustom(); });
$("#closeCustom").addEventListener("click", () => $("#customSheet").close());
$("#cusAdd").addEventListener("click", () => {
  const singles = Object.fromEntries(
    (cus.item.options || []).filter((g) => g.type !== "multi").map((g) => [g.name, cus.choices[g.name]])
  );
  saveUsual(singles);
  addToCart(cus.item, cus.choices, cus.qty);
  $("#customSheet").close();
});

// ---------- cart ----------

function countInCart(id) {
  let n = 0;
  cart.forEach((l) => { if (l.item.id === id) n += l.qty; });
  return n;
}

function addToCart(item, choices, qty) {
  const key = `${item.id}|${JSON.stringify(choices)}`;
  const line = cart.get(key);
  const summary = summaryOf(item, choices);
  if (line) line.qty = Math.min(20, line.qty + qty);
  else cart.set(key, { item, qty, choices, unit: unitPrice(item, choices), summary });
  toast(`${item.name}${summary.length ? ` (${summary.join(", ")})` : ""} added`);
  renderCart();
  if (!$("#view-picks").hidden) renderPicks();
  if (!$("#view-menu").hidden) renderMenu();
}

function cartTotal() {
  let t = 0;
  cart.forEach(({ unit, qty }) => (t += (unit || 0) * qty));
  return t;
}

function renderCart() {
  const n = [...cart.values()].reduce((a, c) => a + c.qty, 0);
  $("#cartbar").hidden = n === 0 || !$("#view-status").hidden;
  $("#cartCount").innerHTML = `${Icon.cart("icon-sm")} ${n} item${n === 1 ? "" : "s"} · Review order`;
  $("#cartTotal").textContent = money(cartTotal());
  $("#sheetTotal").textContent = money(cartTotal());
  $("#cartLines").innerHTML = [...cart.entries()].map(([key, { item, qty, unit, summary }]) => `
    <li><span>${esc(item.name)}${summary.length ? `<br><small class="custom">${esc(summary.join(" · "))}</small>` : ""}<br><small class="muted">${money(unit)}</small></span>
      <span class="qty"><button data-q="-1" data-key="${esc(key)}" aria-label="One less">−</button><b>${qty}</b><button data-q="1" data-key="${esc(key)}" aria-label="One more">+</button></span></li>`).join("");
}

$("#openCart").addEventListener("click", () => $("#cartSheet").showModal());
$("#closeCart").addEventListener("click", () => $("#cartSheet").close());
$("#cartLines").addEventListener("click", (e) => {
  const b = e.target.closest("[data-q]");
  if (!b) return;
  const line = cart.get(b.dataset.key);
  if (!line) return;
  line.qty = Math.min(20, line.qty + Number(b.dataset.q));
  if (line.qty <= 0) cart.delete(b.dataset.key);
  renderCart();
  if (!cart.size) $("#cartSheet").close();
  if (!$("#view-picks").hidden) renderPicks();
  if (!$("#view-menu").hidden) renderMenu();
});

$("#sendOrder").addEventListener("click", () =>
  busy($("#sendOrder"), async () => {
    const items = [...cart.values()].map(({ item, qty, choices }) => ({ id: item.id, qty, choices }));
    const order = await api("/api/order", { items, note: $("#note").value });
    cart.clear();
    $("#note").value = "";
    $("#cartSheet").close();
    showOrder(order);
    clearInterval(orderPoll);
    orderPoll = setInterval(async () => {
      try { showOrder(await api(`/api/order/${order.id}`)); } catch { /* keep polling */ }
    }, 4000);
  })
);

function showOrder(o) {
  show("status");
  renderCart();
  const ready = o.status !== "new";
  $("#statusIcon").innerHTML = ready ? Icon.unwind() : Icon.clock();
  $("#statusTitle").textContent = ready ? "Your order is ready!" : "Sent to the counter";
  $("#statusSub").textContent = ready
    ? "Pick it up at the counter, or it's on its way to your table."
    : o.ahead ? `${o.ahead} order${o.ahead === 1 ? "" : "s"} ahead of you.` : "You're next in line.";
  $("#statusItems").innerHTML = o.items.map((l) => `<li>${l.qty} × ${esc(l.name)}${(l.custom || []).length ? ` <small class="custom">(${esc(l.custom.join(", "))})</small>` : ""}</li>`).join("");
  if (ready) clearInterval(orderPoll);
}

$("#orderMore").addEventListener("click", () => {
  clearInterval(orderPoll);
  renderCart();
  show(S.picks.length ? "picks" : "mood");
});

// ---------- music ----------
// Browsers only allow sound after a tap, so music starts on the first interaction.
let soundHinted = false;
document.addEventListener("pointerdown", (e) => {
  if (e.target.closest("#soundBtn") || !window.Ambience) return;
  window.Ambience.unlock();
  if (!soundHinted) {
    soundHinted = true;
    if ($("#soundBtn").dataset.on === "true") toast(`${window.Ambience.name} · tap the speaker to mute`);
  }
}, { capture: true });
$("#soundBtn").addEventListener("click", () => {
  soundHinted = true;
  const on = window.Ambience?.toggle();
  toast(on ? window.Ambience.name : "Music off");
});

// ---------- boot ----------
$$(".mood").forEach((b) => { $(".mood-icon", b).innerHTML = (MOOD_ICON[b.dataset.mood] || Icon.work)(); });
const SET_ICON = { love: Icon.heart, mixed: Icon.meh, nope: Icon.nope };
$$("[data-set]").forEach((b) => { $(".set-icon", b).innerHTML = (SET_ICON[b.dataset.set] || Icon.meh)(); });
$("#backToPicks").innerHTML = `${Icon.arrowLeft("icon-sm")} My picks`;

(async () => {
  try {
    const data = await api("/api/visit");
    applyState(data);
    show(data.mood && data.picks.length ? "picks" : "mood");
  } catch (e) {
    toast(e.message);
  }
  renderCart();
})();
