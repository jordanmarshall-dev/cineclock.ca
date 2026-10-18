// Home page hero: swipe or tap the arrows to move between highlights, and it
// wraps around. Without JavaScript the slides still scroll sideways on their own.
(() => {
  const hero = document.querySelector(".hero");
  if (!hero) return;
  const track = hero.querySelector(".hero-track");
  const slides = [...track.children];
  if (slides.length < 2) return;

  // A copy of the last slide goes before the first and a copy of the first after
  // the last, so moving past either end slides on smoothly, then quietly jumps
  // back to the real slide.
  const copy = (el) => {
    const c = el.cloneNode(true);
    c.setAttribute("aria-hidden", "true");
    c.tabIndex = -1;
    c.querySelector("img")?.removeAttribute("loading");
    return c;
  };
  track.prepend(copy(slides[slides.length - 1]));
  track.append(copy(slides[0]));
  hero.classList.add("is-carousel");

  const dots = [...hero.querySelectorAll(".hero-dots button")];
  hero.querySelectorAll("[hidden]").forEach((el) => (el.hidden = false));

  let pos = 1;
  // Slides are narrower than the hero, so move by each slide's real position.
  const place = (animate, offset = 0) => {
    track.style.transition = animate ? "" : "none";
    track.style.transform = `translateX(${offset - track.children[pos].offsetLeft}px)`;
  };
  const show = (n) => {
    pos = n;
    place(true);
    const real = (pos - 1 + slides.length) % slides.length;
    dots.forEach((d, i) => d.setAttribute("aria-current", i === real ? "true" : "false"));
  };

  track.addEventListener("transitionend", () => {
    if (pos === 0) pos = slides.length;
    else if (pos === slides.length + 1) pos = 1;
    else return;
    place(false);
  });

  hero.querySelector(".prev").addEventListener("click", () => show(pos - 1));
  hero.querySelector(".next").addEventListener("click", () => show(pos + 1));
  dots.forEach((d, i) => d.addEventListener("click", () => show(i + 1)));

  // Swipe. A drag of more than a sixth of the width turns the page; a drag of
  // any size cancels the tap, so swiping never opens a film by accident.
  let startX = null;
  let dx = 0;
  track.addEventListener("pointerdown", (e) => {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    startX = e.clientX;
    dx = 0;
  });
  track.addEventListener("pointermove", (e) => {
    if (startX === null) return;
    dx = e.clientX - startX;
    if (Math.abs(dx) > 6) place(false, dx);
  });
  const release = () => {
    if (startX === null) return;
    startX = null;
    if (Math.abs(dx) > hero.clientWidth / 6) show(pos + (dx < 0 ? 1 : -1));
    else show(pos);
  };
  track.addEventListener("pointerup", release);
  track.addEventListener("pointercancel", release);
  track.addEventListener("pointerleave", release);
  track.addEventListener("click", (e) => {
    if (Math.abs(dx) > 6) e.preventDefault();
  });
  track.addEventListener("dragstart", (e) => e.preventDefault());

  show(1);
  place(false);
  addEventListener("resize", () => place(false));
})();
