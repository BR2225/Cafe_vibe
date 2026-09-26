// Customer page: mood -> picks -> reactions / set buttons -> menu -> cart -> order status.
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const CUR = document.body.dataset.currency || "₹";
const MOOD_ICON = { work: Icon.work, meet: Icon.meet, unwind: Icon.unwind };
const MOOD_LABEL = { work: "Working", meet: "Meeting", unwind: "Unwinding" };

let S = { picks: [], mood: null };
let menuMode = "full";
const cart = new Map(); // id -> {item, qty}
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
  const inCart = cart.has(it.id);
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
      <button class="add ${inCart ? "in-cart" : ""}" data-add="${it.id}">${inCart ? Icon.check("icon-sm") + " Added" : Icon.plus("icon-sm") + " Add"}</button>
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
    const it = S.picks.find((p) => p.id === Number(add.dataset.add));
    toggleCart(it);
    renderPicks();
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
  const inCart = cart.has(it.id);
  return `
  <div class="row ${it.available ? "" : "off"}">
    <div><b><span class="dot ${it.veg ? "" : "nonveg"}"></span>${esc(it.name)}</b>${top ? '<span class="badge">Top match</span>' : ""}${it.available ? "" : '<span class="badge soldout">Sold out</span>'}</div>
    <div class="right"><span class="price">${money(it.price)}</span>
      ${it.available ? `<button class="add ${inCart ? "in-cart" : ""}" data-add="${it.id}">${inCart ? Icon.check("icon-sm") : Icon.plus("icon-sm") + " Add"}</button>` : ""}</div>
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
  toggleCart(menuItems.find((m) => m.id === Number(add.dataset.add)));
  renderMenu();
});

// ---------- cart ----------

function toggleCart(it) {
  if (!it) return;
  if (cart.has(it.id)) cart.delete(it.id);
  else { cart.set(it.id, { item: it, qty: 1 }); toast(`${it.name} added`); }
  renderCart();
}

function cartTotal() {
  let t = 0;
  cart.forEach(({ item, qty }) => (t += (item.price || 0) * qty));
  return t;
}

function renderCart() {
  const n = [...cart.values()].reduce((a, c) => a + c.qty, 0);
  $("#cartbar").hidden = n === 0 || !$("#view-status").hidden;
  $("#cartCount").innerHTML = `${Icon.cart("icon-sm")} ${n} item${n === 1 ? "" : "s"} · Review order`;
  $("#cartTotal").textContent = money(cartTotal());
  $("#sheetTotal").textContent = money(cartTotal());
  $("#cartLines").innerHTML = [...cart.values()].map(({ item, qty }) => `
    <li><span>${esc(item.name)}<br><small class="muted">${money(item.price)}</small></span>
      <span class="qty"><button data-q="-1" data-id="${item.id}" aria-label="One less">−</button><b>${qty}</b><button data-q="1" data-id="${item.id}" aria-label="One more">+</button></span></li>`).join("");
}

$("#openCart").addEventListener("click", () => $("#cartSheet").showModal());
$("#closeCart").addEventListener("click", () => $("#cartSheet").close());
$("#cartLines").addEventListener("click", (e) => {
  const b = e.target.closest("[data-q]");
  if (!b) return;
  const line = cart.get(Number(b.dataset.id));
  line.qty += Number(b.dataset.q);
  if (line.qty <= 0) cart.delete(line.item.id);
  renderCart();
  if (!cart.size) $("#cartSheet").close();
  if (!$("#view-picks").hidden) renderPicks();
  if (!$("#view-menu").hidden) renderMenu();
});

$("#sendOrder").addEventListener("click", () =>
  busy($("#sendOrder"), async () => {
    const items = [...cart.values()].map(({ item, qty }) => ({ id: item.id, qty }));
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
  $("#statusItems").innerHTML = o.items.map((l) => `<li>${l.qty} × ${esc(l.name)}</li>`).join("");
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
