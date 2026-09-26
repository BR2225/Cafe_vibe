(function () {
  function getCookie(name) {
    var m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
    return m ? decodeURIComponent(m[1]) : "";
  }

  function setLangCookie(lang) {
    var value = lang === "en" ? "" : "/en/" + lang;
    var host = window.location.hostname;
    document.cookie = "googtrans=; path=/; expires=Thu, 01 Jan 1970 00:00:00 UTC";
    document.cookie = "googtrans=; path=/; domain=." + host + "; expires=Thu, 01 Jan 1970 00:00:00 UTC";
    if (value) {
      document.cookie = "googtrans=" + value + "; path=/";
      document.cookie = "googtrans=" + value + "; path=/; domain=." + host;
    }
  }

  function currentLang() {
    var raw = getCookie("googtrans");
    if (!raw) return "en";
    var parts = raw.split("/");
    return parts[2] || "en";
  }

  var wrap = document.querySelector(".lang-switch");
  var topbarActions = document.querySelector(".topbar-actions");
  var topbar = document.querySelector(".topbar");
  if (wrap && topbarActions) {
    wrap.classList.add("inline");
    topbarActions.insertBefore(wrap, topbarActions.firstChild);
  } else if (wrap && topbar) {
    // Owner dashboard has no .topbar-actions: dock next to the tabs instead of floating over them.
    wrap.classList.add("inline");
    topbar.appendChild(wrap);
  }

  var select = document.getElementById("langSelect");
  if (select) {
    select.value = currentLang();
    select.addEventListener("change", function () {
      setLangCookie(select.value);
      window.location.reload();
    });
  }

  window.googleTranslateInit = function () {
    new google.translate.TranslateElement(
      {
        pageLanguage: "en",
        includedLanguages: "hi,bn,te,mr,ta,ur,gu,kn,ml,pa,or,as,ne,sd,sa,en",
        autoDisplay: false,
      },
      "google_translate_element"
    );
  };
})();
